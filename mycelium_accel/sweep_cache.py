"""V4.1: content-addressed sweep cache (opt-in, read-only runs only).

Key = manifest + seeds + race/adaptive settings + python + platform + every
non-hidden file's bytes under the target root. Any change misses. Stored
payloads are version-stamped (a new mycelium-accel never trusts an old cache).
Kill: 1 hit whose verdict differs from a fresh measurement = feature removed.
"""
from __future__ import annotations

import hashlib
import os
import json
import sys
from pathlib import Path
from typing import Any


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


def _atomic_write_text(path: Path, text: str) -> None:
    """Q2.2: crash- and concurrency-safe write (tmp + rename)."""
    import tempfile as _tempfile  # local: keeps module import light

    fd, tmp_name = _tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def lookup(cache_dir: Path, key: str) -> dict[str, Any] | None:
    from . import __version__

    path = cache_dir / f"{key}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
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
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))
    return path
