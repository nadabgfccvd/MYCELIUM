"""Q2.5 — concurrent accelerates on one target: documented guarantees.

GUARANTEED: exports never clobber (pid in stem); cache files are always valid
JSON (atomic tmp+rename — concurrent writers, one winner, no halves).
DOCUMENTED LIMITATION: ``apply=True`` races last-writer-wins on the selection
record (no lock — concurrent applies are user error, and both decisions were
honest on their own data).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import pytest

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402


@pytest.mark.slow
class ConcurrencyTests(unittest.TestCase):
    def test_two_accelerates_same_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            procs = [
                subprocess.Popen(
                    [sys.executable, "-m", "mycelium_accel", "accelerate",
                     "--target", str(root), "--no-apply", "--seeds", "101,103,107"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    cwd=Path(__file__).resolve().parent.parent,
                )
                for _ in range(2)
            ]
            outs = [p.communicate(timeout=180) for p in procs]
            for p, (out, err) in zip(procs, outs):
                self.assertEqual(p.returncode, 0, err[-1500:])
                self.assertIn("fast-mode", out)
            sweeps = sorted((root / ".mycelium_benchmarks").glob("sweep-*.json"))
            self.assertEqual(len(sweeps), 2)
            for path in sweeps:  # both complete + valid
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(len(payload["summaries"]), 3)

    def test_concurrent_cache_store_stays_valid(self) -> None:
        from mycelium_accel.sweep_cache import lookup, store

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            errors: list[Exception] = []

            def writer(i: int) -> None:
                try:
                    for _ in range(10):
                        store(cache, "hot", {"sweep": {"writer": i}})
                        lookup(cache, "hot")
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            final = lookup(cache, "hot")
            self.assertIsNotNone(final)
            self.assertIn(final["sweep"]["writer"], (0, 1, 2, 3))
            self.assertEqual(json.loads((cache / "hot.json").read_text())["key"], "hot")


if __name__ == "__main__":
    unittest.main()
