"""Q2.2 — I/O failures degrade to friendly errors, never tracebacks.

* Read-only export/cache dirs -> exit 1 with "accelerate failed: ..." (OSError).
* Cache + sweep JSON writes are atomic (tmp + rename): readers never see halves.
* `cmd | head` dies silently (SIGPIPE back to default, posix).
"""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
