"""Q2.2 — I/O failures degrade to friendly errors, never tracebacks.

* Read-only export/cache dirs -> exit 1 with "accelerate failed: ..." (OSError).
* Cache + sweep JSON writes are atomic (tmp + rename): readers never see halves.
* Windows rename-while-locked (CI-5): cache stores back off and, if the file
  stays busy, degrade to a cache miss instead of crashing; exports and real
  I/O errors (ENOSPC, permissions) stay loud. Injected nt semantics below,
  since posix cannot reproduce a sharing violation.
* `cmd | head` dies silently (SIGPIPE back to default, posix).
"""
from __future__ import annotations

import errno
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mycelium_accel", *args],
        capture_output=True, text=True, timeout=180, cwd=cwd)


class IOFailureTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    @pytest.mark.slow  # Q2 re-tier: CLI subprocess
    @unittest.skipIf(os.name == "nt",
                     "chmod-based readonly dirs are posix semantics; "
                     "Windows ACLs ignore the unix readonly bit")
    def test_readonly_export_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            exp = root / ".mycelium_benchmarks"
            exp.mkdir()
            os.chmod(exp, 0o555)
            try:
                proc = _run_cli("accelerate", "--target", str(root), "--no-apply",
                                "--seeds", "101,103,107", cwd=self.ROOT)
            finally:
                os.chmod(exp, 0o755)
            self.assertEqual(proc.returncode, 1, proc.stderr[-1500:])
            self.assertIn("accelerate failed", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    @pytest.mark.slow  # Q2 re-tier: CLI subprocess
    @unittest.skipIf(os.name == "nt",
                     "chmod-based readonly dirs are posix semantics; "
                     "Windows ACLs ignore the unix readonly bit")
    def test_readonly_cache_dir_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            cache = root / "shared-cache"
            cache.mkdir()
            os.chmod(cache, 0o555)
            try:
                proc = _run_cli("accelerate", "--target", str(root), "--no-apply",
                                "--cache", "--cache-dir", str(cache),
                                "--seeds", "101,103,107", cwd=self.ROOT)
            finally:
                os.chmod(cache, 0o755)
            self.assertEqual(proc.returncode, 1, proc.stderr[-1500:])
            self.assertIn("accelerate failed", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_cache_store_atomic_no_tmp_residue(self) -> None:
        from mycelium_accel.sweep_cache import lookup, store

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            store(cache, "k1", {"sweep": {"a": 1}})
            self.assertEqual(lookup(cache, "k1")["sweep"], {"a": 1})
            self.assertEqual(list(cache.glob("*.tmp")), [])
            self.assertEqual(list(cache.glob(".*.tmp")), [])

    def test_export_stem_has_pid(self) -> None:
        from mycelium_accel.bench import BenchmarkExecutor, BenchmarkSweep
        from mycelium_accel.targets import load_target

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            executor = BenchmarkExecutor(load_target(root, None))
            sweep = BenchmarkSweep(target="t", metric="m", lower_is_better=True,
                                   summaries=[], comparisons=[])
            path = executor.export_json(sweep)
            self.assertIn(f"-{os.getpid()}.json", path.name)
            self.assertEqual(json.loads(path.read_text())["metric"], "m")

    @pytest.mark.skipif(os.name != "posix", reason="SIGPIPE is posix-only")
    def test_sigpipe_restored_to_default(self) -> None:
        import signal

        from mycelium_accel.__main__ import main

        old_argv = sys.argv
        sys.argv = ["mycelium-accel", "--version"]
        try:
            main()  # prints version, returns
        finally:
            sys.argv = old_argv
        self.assertEqual(signal.getsignal(signal.SIGPIPE), signal.SIG_DFL)


class WindowsLockContentionTests(unittest.TestCase):
    """CI-5: the Windows-only half of Q2.2, driven from the inside.

    On Windows ``os.replace`` is *refused* (PermissionError) while another
    thread holds the destination open; posix happily renames over an open file,
    so the failure cannot be reproduced here. We inject nt semantics instead —
    the rename seam (``_replace``) plus the classifier (``_is_lock_contention``)
    — which is exactly the code path a Windows runner takes. The guarantees
    under test are the same on every platform: readers never see halves, a
    cache never crashes a run, and a real I/O error always stays loud.
    """

    def setUp(self) -> None:
        from mycelium_accel import sweep_cache

        self.sc = sweep_cache

    def _patch_attr(self, target, attr: str, value) -> None:  # noqa: ANN001
        old = getattr(target, attr)
        self.addCleanup(setattr, target, attr, old)
        setattr(target, attr, value)

    def _as_windows(self, replace) -> None:  # noqa: ANN001
        self._patch_attr(self.sc, "_replace", replace)
        self._patch_attr(self.sc, "_is_lock_contention", lambda exc: True)
        self._patch_attr(self.sc, "REPLACE_BUDGET_SECONDS", 0.05)

    def test_lock_contention_is_judged_per_platform(self) -> None:
        import errno as _errno
        import types

        denied = PermissionError(_errno.EACCES, "Permission denied")
        # posix: a refused rename means permissions, not a busy file — stay loud.
        self.assertFalse(self.sc._is_lock_contention(denied))
        self.assertTrue(self.sc._is_lock_contention(OSError(_errno.EBUSY, "busy")))
        # nt: ERROR_ACCESS_DENIED *is* the busy-file case.
        real_os = self.sc.os
        self.addCleanup(setattr, self.sc, "os", real_os)
        self.sc.os = types.SimpleNamespace(name="nt")  # type: ignore[assignment]
        self.assertTrue(self.sc._is_lock_contention(denied))

    def test_store_backs_off_until_the_rename_lands(self) -> None:
        from mycelium_accel.sweep_cache import lookup, store

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            store(cache, "k", {"sweep": {"v": 1}})
            attempts = {"n": 0}

            def contended(src: str, dst: str) -> None:
                attempts["n"] += 1
                if attempts["n"] <= 3:  # reader + AV hold the file a few times
                    raise PermissionError(13, "Permission denied")
                os.replace(src, dst)

            self._as_windows(contended)
            store(cache, "k", {"sweep": {"v": 2}})
            self.assertEqual(lookup(cache, "k")["sweep"], {"v": 2})  # retry won
            self.assertGreaterEqual(attempts["n"], 4)
            self.assertEqual(list(cache.glob("*.tmp")), [])
            self.assertEqual(list(cache.glob(".*.tmp")), [])

    def test_exhausted_lock_budget_degrades_the_refresh_to_a_miss(self) -> None:
        from mycelium_accel.sweep_cache import lookup, store

        def blocked_forever(src: str, dst: str) -> None:
            raise PermissionError(13, "Permission denied")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            store(cache, "k", {"sweep": {"v": 1}})
            before = (cache / "k.json").read_bytes()
            self._as_windows(blocked_forever)
            store(cache, "k", {"sweep": {"v": 2}})  # must NOT raise
            self.assertEqual(lookup(cache, "k")["sweep"], {"v": 1})  # old entry serves
            self.assertEqual((cache / "k.json").read_bytes(), before)  # untouched
            self.assertEqual(list(cache.glob("*.tmp")), [])  # no residue
            self.assertEqual(list(cache.glob(".*.tmp")), [])

    def test_locked_first_store_still_raises(self) -> None:
        # Nothing on disk yet => "could not cache" is a real failure, not a miss.
        from mycelium_accel.sweep_cache import store

        def blocked_forever(src: str, dst: str) -> None:
            raise PermissionError(13, "Permission denied")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            self._as_windows(blocked_forever)
            with self.assertRaises(PermissionError):
                store(cache, "k", {"sweep": {"v": 1}})
            self.assertFalse((cache / "k.json").exists())
            self.assertEqual(list(cache.glob("*.tmp")), [])
            self.assertEqual(list(cache.glob(".*.tmp")), [])

    def test_real_io_errors_never_degrade(self) -> None:
        from mycelium_accel.sweep_cache import _atomic_write_text, store

        def no_space(src: str, dst: str) -> None:
            raise OSError(errno.ENOSPC, "No space left on device")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            export = cache / "sweep-1.json"
            _atomic_write_text(export, "first")  # before the fault is armed
            store(cache, "k", {"sweep": {"v": 1}})
            self._patch_attr(self.sc, "_replace", no_space)
            self._patch_attr(self.sc, "REPLACE_BUDGET_SECONDS", 0.05)
            # ENOSPC is not lock contention even on nt -> raises on the tolerant path
            with self.assertRaises(OSError):
                store(cache, "k", {"sweep": {"v": 2}})
            # ...and the sweep-export path (tolerate_lock=False) never swallows
            with self.assertRaises(OSError):
                _atomic_write_text(export, "second")
            self.assertEqual(export.read_text(encoding="utf-8"), "first")
            self.assertEqual(
                json.loads((cache / "k.json").read_text(encoding="utf-8"))["sweep"],
                {"v": 1})
            self.assertEqual(list(cache.glob("*.tmp")), [])

    def test_locked_contention_leaves_exports_loud(self) -> None:
        # A cache refresh may degrade; an export is the record itself.
        from mycelium_accel.sweep_cache import _atomic_write_text

        def blocked_forever(src: str, dst: str) -> None:
            raise PermissionError(13, "Permission denied")

        with tempfile.TemporaryDirectory() as temp:
            export = Path(temp) / "sweep-1.json"
            _atomic_write_text(export, "first")
            self._as_windows(blocked_forever)
            with self.assertRaises(PermissionError):
                _atomic_write_text(export, "second")  # no silent data loss
            self.assertEqual(export.read_text(encoding="utf-8"), "first")
            self.assertEqual(list(export.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
