"""V4.1: content-addressed sweep cache (opt-in, read-only runs only).

Key = manifest + seeds + race/adaptive settings + python + platform + every
non-hidden file's bytes under the target root. Any change misses. Stored
payloads are version-stamped (a new mycelium-accel never trusts an old cache).
Kill: 1 hit whose verdict differs from a fresh measurement = feature removed.

Concurrency contract (Q2.5): a cache file is *always* valid JSON — writers go
through tmp+rename, so readers never see halves. On Windows a rename onto a
file another thread has open is refused outright (no FILE_SHARE_DELETE for
plain ``open()``, and AV scanning stretches that window to hundreds of ms), so
``store`` additionally retries with backoff and, once the budget is spent,
*degrades to a miss* instead of crashing: the valid entry already on disk keeps
serving, the refresh is simply lost. ``lookup``/``store`` never hide a real
I/O error (missing dir, ENOSPC, posix permissions) — those still raise.
"""
from __future__ import annotations

import errno
import hashlib
import os
import json
import sys
import time
from pathlib import Path
from typing import Any

# The nt-side "not now" set: Windows also surfaces sharing violations as
# PermissionError, so that one is classified separately. Everything else
# propagates immediately — a broken filesystem must not be retried into silence.
_BUSY_ERRNOS = frozenset({errno.EBUSY, errno.EAGAIN, errno.EPERM})
# Budget for one rename, not for one store: long enough to outlive a Windows
# reader/Defender window (hundreds of ms), short enough that a CLI never feels
# it. Anything still busy after this degrades (cache) or raises (exports).
REPLACE_BUDGET_SECONDS = 1.5

# Test seam: lets a test inject Windows-style contention without patching the
# global ``os`` module (which would leak into unrelated tests in the worker).
_replace = os.replace


def _is_lock_contention(exc: OSError) -> bool:
    """Is this rename failure a transient "someone else is holding it"?

    Only ``EBUSY`` qualifies on posix — a PermissionError there is a real
    permission problem (read-only cache dir), and staying loud is the
    documented Q2.2 behavior. Windows answers sharing violations with
    PermissionError (ERROR_ACCESS_DENIED), which *is* the transient case.
    """
    if os.name == "nt":
        return isinstance(exc, PermissionError) or exc.errno in _BUSY_ERRNOS
    return exc.errno == errno.EBUSY


def _hashable_files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue  # state dirs (.mycelium_*, .git) never affect measurement
        if "__pycache__" in rel.parts or path.suffix == ".pyc":
            continue
        files.append(path)
    return files


def cache_key(
    root: Path,
    manifest_dict: dict[str, Any],
    seeds: list[int],
    *,
    race: bool = False,
    race_seeds: int = 3,
    race_margin: float = 0.0,
    adaptive_repeats: bool = False,
    sequential_seeds: bool = False,
) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(manifest_dict, sort_keys=True).encode("utf-8"))
    digest.update(json.dumps({
        "seeds": seeds, "race": race, "race_seeds": race_seeds,
        "race_margin": race_margin, "adaptive_repeats": adaptive_repeats,
        "sequential_seeds": sequential_seeds,
        "python": sys.version, "platform": sys.platform,
    }, sort_keys=True).encode("utf-8"))
    for path in _hashable_files(root):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _replace_with_retry(tmp_name: str, path: Path, budget: float | None = None) -> None:
    """Rename tmp onto path, backing off while another thread holds it open.

    Uncontended cost: one syscall, no sleep. Under contention it keeps trying
    until ``budget`` seconds are spent (1 ms → 50 ms exponential), which clears
    the real-world windows we hit on CI (reader + antivirus scan) by orders of
    magnitude. Raises the last lock error if the budget runs out.
    """
    if budget is None:
        budget = REPLACE_BUDGET_SECONDS  # read at call time: tests retune it
    deadline = time.monotonic() + budget
    delay = 0.001
    while True:
        try:
            _replace(tmp_name, path)
            return
        except OSError as exc:
            if not _is_lock_contention(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.05)


def _discard(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _atomic_write_text(path: Path, text: str, *, tolerate_lock: bool = False) -> None:
    """Q2.2: crash- and concurrency-safe write (tmp + rename).

    ``tolerate_lock`` is for cache stores only: a rename still blocked by pure
    lock contention after the retry budget, *with a valid file already in
    place*, is swallowed (worst case the next run re-measures). It never
    tolerates a missing destination — that would silently mean "no cache".
    """
    import tempfile as _tempfile  # local: keeps module import light

    fd, tmp_name = _tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    except BaseException:
        _discard(tmp_name)
        raise
    try:
        _replace_with_retry(tmp_name, path)
    except OSError as exc:
        _discard(tmp_name)
        if tolerate_lock and _is_lock_contention(exc) and path.is_file():
            return
        raise


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """C4: byte-exact sibling of _atomic_write_text (for CSV).

    Text mode would translate newlines on Windows (``\\r\\n`` → ``\\r\\r\\n``);
    the CSV export keeps its csv-module bytes bit-identical on every platform
    by going through here. Exports are the record itself: never tolerant —
    any failure raises and the previous file (if any) stays intact.
    """
    import tempfile as _tempfile  # local: keeps module import light

    fd, tmp_name = _tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except BaseException:
        _discard(tmp_name)
        raise
    try:
        _replace_with_retry(tmp_name, path)
    except OSError:
        _discard(tmp_name)
        raise


def lookup(cache_dir: Path, key: str) -> dict[str, Any] | None:
    from . import __version__

    path = cache_dir / f"{key}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # Q1.3: a corrupt cache is a miss, not a crash. OSError joins the list
        # for CI-5: on Windows a cache file can be mid-scan/mid-replace, and a
        # momentary read refusal must degrade to a re-measure, never to a red run.
        return None
    if not isinstance(payload, dict):  # Q1.3: corrupt cache is a miss, not a crash
        return None
    if payload.get("key") != key or payload.get("mycelium_version") != __version__:
        return None
    if not isinstance(payload.get("sweep"), dict):
        return None
    return payload


def store(cache_dir: Path, key: str, payload: dict[str, Any]) -> Path:
    from . import __version__

    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {"key": key, "mycelium_version": __version__, **payload}
    path = cache_dir / f"{key}.json"
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True),
                       tolerate_lock=True)
    return path
