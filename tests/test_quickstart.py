"""H1.1: the quickstart path works end-to-end in < 5 minutes.

Follows docs/QUICKSTART.md steps 1-4 on a tiny fixture: init --yes,
doctor --target, accelerate --no-apply, HTML report exists.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET_SECONDS = 300.0


class QuickstartTests(unittest.TestCase):
    def test_four_steps_under_budget(self) -> None:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "benchmark.py").write_text("print(sum(range(1000)))\n", encoding="utf-8")
            init = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "accelerate", "init",
                 "--target", tmp, "--yes"],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(init.returncode, 0, init.stderr)
            doctor = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "doctor", "--target", tmp],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(doctor.returncode, 0, doctor.stdout)
            accel = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "accelerate",
                 "--target", tmp, "--no-apply", "--seeds", "101,103,107"],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(accel.returncode, 0, accel.stderr)
            html = sorted(Path(tmp, ".mycelium_benchmarks").glob("sweep-*.html"))
            self.assertTrue(html, "quickstart must produce an HTML report")
            self.assertIn("mycelium", html[0].read_text(encoding="utf-8").lower())
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, BUDGET_SECONDS, f"quickstart took {elapsed:.1f}s")


if __name__ == "__main__":
    unittest.main()
