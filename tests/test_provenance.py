"""Fase 1.1: ambient-artifact provenance (stamp, check, strict readers)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.telemetry import check_provenance, stamp_provenance

ROOT = Path(__file__).resolve().parents[1]


class ProvenanceTests(unittest.TestCase):
    def test_stamp_and_check_roundtrip(self) -> None:
        payload = stamp_provenance({"a": 1}, "unit-test", "state-X")
        self.assertIn("provenance", payload)
        ok, reason = check_provenance(payload, "state-X")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_missing_and_foreign_flagged(self) -> None:
        ok, reason = check_provenance({"a": 1}, "state-X")
        self.assertFalse(ok)
        self.assertIn("missing", reason)
        payload = stamp_provenance({}, "unit-test", "state-Y")
        ok, reason = check_provenance(payload, "state-X")
        self.assertFalse(ok)
        self.assertIn("foreign", reason)

    def test_growth_regime_strict_ignores_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # legacy unstamped artifact in cwd-relative spot: emulate via cwd switch
            qd_dir = tmp_path / ".mycelium_qd"
            qd_dir.mkdir()
            (qd_dir / "qd_experiment.json").write_text(
                json.dumps({"final_coverage": 0.99, "final_qd_score": 999.0}), encoding="utf-8")
            state = tmp_path / "state"
            init = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "init",
                 "--seed", "101", "--state-dir", str(state)],
                capture_output=True, text=True, cwd=tmp_path)
            self.assertEqual(init.returncode, 0, init.stderr)
            run = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "run",
                 "--seed", "101", "--state-dir", str(state), "--rounds", "6"],
                capture_output=True, text=True, cwd=tmp_path)
            self.assertEqual(run.returncode, 0, run.stderr)
            lax = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "growth-regime",
                 "--state-dir", str(state)],
                capture_output=True, text=True, cwd=tmp_path)
            self.assertEqual(lax.returncode, 0, lax.stderr)
            self.assertIn("warning", lax.stderr)
            self.assertAlmostEqual(json.loads(lax.stdout)["coverage"], 0.99)
            strict = subprocess.run(
                [sys.executable, "-m", "mycelium_accel", "growth-regime",
                 "--state-dir", str(state), "--strict"],
                capture_output=True, text=True, cwd=tmp_path)
            self.assertEqual(strict.returncode, 0, strict.stderr)
            self.assertAlmostEqual(json.loads(strict.stdout)["coverage"], 0.0)


if __name__ == "__main__":
    unittest.main()
