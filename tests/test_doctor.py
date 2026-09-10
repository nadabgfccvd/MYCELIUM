"""B3: doctor checks + accelerate init scaffolding."""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.doctor import run_checks

ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def test_run_checks_no_fail_on_dev_machine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checks = run_checks(str(Path(tmp) / "state"))
        names = {c.name for c in checks}
        self.assertIn("python", names)
        self.assertIn("state_dir", names)
        fails = [c for c in checks if c.status == "FAIL"]
        self.assertEqual(fails, [])

    def test_doctor_cli_json(self) -> None:
        proc = cli("doctor", "--json")
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["checks"]), 8)

    def test_accelerate_init_detects_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "benchmark.py").write_text("print(1)\n", encoding="utf-8")
            proc = cli("accelerate", "init", "--target", tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads(Path(tmp, "mycelium.target.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "python")


if __name__ == "__main__":
    unittest.main()
