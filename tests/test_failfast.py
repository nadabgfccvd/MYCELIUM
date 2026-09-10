"""V2.3: fail-fast lock-in — broken candidates cost exactly 1 run.

Audit result: the sweep loop is already optimal (per-candidate return on first
bad run + sweep abort). This test locks that behavior so V2/V4 never regress it.
"""
from __future__ import annotations

import json
import tempfile
import pytest
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import accelerate_target

BENCH = (
    "import os, sys\n"
    "sys.exit(3 if os.environ.get('BREAK_ME') == '1' else 0)\n"
)
MANIFEST = {
    "benchmark_command": "python bench.py",
    "manifest_version": "1.0",
    "variants": [
        {"name": "broken", "mode": "env", "env": {"BREAK_ME": "1"}},
        {"name": "good", "mode": "env", "env": {"BREAK_ME": "0"}},
    ],
}


class FailFastTests(unittest.TestCase):
    @pytest.mark.slow
    def test_broken_costs_one_run_and_aborts_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bench.py").write_text(BENCH, encoding="utf-8")
            (root / "mycelium.target.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
            outcome = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            sweep = json.loads(Path(outcome.sweep_path).read_text(encoding="utf-8"))
            by_name = {s["candidate"]: s for s in sweep["summaries"]}
            self.assertEqual(len(by_name["broken"]["runs"]), 1)
            self.assertNotIn("good", by_name)  # sweep aborted, survivor never measured
            self.assertIsNone(outcome.best_candidate)


if __name__ == "__main__":
    unittest.main()
