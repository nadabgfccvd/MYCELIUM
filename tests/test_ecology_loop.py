"""C1: in-loop ecology primitives + engine integration (default off = no-op)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mycelium_accel.config import Config
from mycelium_accel.ecology_loop import (
    EliteArchive,
    decline_streak,
    frontier_stalled,
    novelty_boost,
)
from mycelium_accel.engine import MyceliumEngine


class EcologyLoopTests(unittest.TestCase):
    def test_archive_keeps_all_time_best(self) -> None:
        archive = EliteArchive()
        self.assertTrue(archive.note("g1", 1.0, 1))
        self.assertFalse(archive.note("g2", 0.5, 2))
        self.assertTrue(archive.note("g3", 2.0, 3))
        self.assertEqual(archive.best_score, 2.0)
        self.assertEqual(archive.elite_genome(), "g3")

    def test_decline_and_stall_detectors(self) -> None:
        self.assertTrue(decline_streak([5, 4, 4, 3], 4))
        self.assertFalse(decline_streak([5, 4, 6, 3], 4))
        self.assertFalse(decline_streak([5, 4], 4))
        self.assertTrue(frontier_stalled([2, 2, 2, 2], 4))
        self.assertFalse(frontier_stalled([2, 2, 3, 2], 4))
        self.assertEqual(novelty_boost(2, True), 3.0)
        self.assertEqual(novelty_boost(5, True), 1.0)
        self.assertEqual(novelty_boost(1, False), 1.0)

    def test_engine_flags_off_by_default_and_metrics_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(seed=101, state_dir=str(Path(tmp) / "s"))
            engine = MyceliumEngine(config)
            engine.init_state()
            engine.run(6)
            state = engine.load_or_init_state()
            last = state.metrics_history[-1]
            self.assertIn("ecology_injections", last)
            self.assertEqual(last["ecology_injections"], 0)
            self.assertEqual(last["ecology_reseeds"], 0)

    def test_anti_forgetting_injects_after_decline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(seed=101, state_dir=str(Path(tmp) / "s"),
                            anti_forgetting=True, ecology_patience=3,
                            ecology_reseed_rounds=5)
            engine = MyceliumEngine(config)
            engine.init_state()
            engine.run(40)
            state = engine.load_or_init_state()
            injections = sum(int(m.get("ecology_injections", 0)) for m in state.metrics_history)
            reseeds = sum(int(m.get("ecology_reseeds", 0)) for m in state.metrics_history)
            # mechanisms must at least fire on a 40-round window (decline/stall
            # are near-guaranteed); exact counts are seed-dependent.
            self.assertGreaterEqual(injections + reseeds, 1)


if __name__ == "__main__":
    unittest.main()
