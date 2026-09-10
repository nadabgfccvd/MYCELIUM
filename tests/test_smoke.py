from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.state import load_state


class SmokeTests(unittest.TestCase):
    def test_engine_runs_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            engine = MyceliumEngine(config)

            engine.init_state()
            summary = engine.run(3)
            state = load_state(state_dir)

            self.assertEqual(summary.rounds_executed, 3)
            self.assertEqual(state.round_index, 3)
            self.assertGreaterEqual(len(state.metrics_history), 3)
            self.assertEqual(len(state.families), 5)
            self.assertTrue(state.frontier_archive)
            latest_metric = state.metrics_history[-1]
            self.assertIn("active_niches", latest_metric)
            self.assertIn("diversity_entropy", latest_metric)
            self.assertIn("frontier_status_counts", latest_metric)
            self.assertTrue((state_dir / "audit.log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
