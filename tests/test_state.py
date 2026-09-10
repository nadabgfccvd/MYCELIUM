from __future__ import annotations

import json
import pickle
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.state import load_state, state_file


class StateTests(unittest.TestCase):
    def test_state_is_saved_in_compact_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            engine = MyceliumEngine(config)

            engine.init_state()
            engine.run(2)

            payload = json.loads(state_file(state_dir).read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], 4)
            self.assertIn("families", payload)
            self.assertIsInstance(payload["families"][0], list)

    def test_state_save_every_still_flushes_final_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            config = Config(
                seed=101,
                state_dir=str(state_dir),
                family_count=5,
                family_size=10,
                state_save_every=10,
            )
            engine = MyceliumEngine(config)

            engine.init_state()
            summary = engine.run(3)
            state = load_state(state_dir)

            self.assertEqual(summary.rounds_executed, 3)
            self.assertEqual(state.round_index, 3)

    def test_pickle_state_backend_roundtrips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            config = Config(
                seed=101,
                state_dir=str(state_dir),
                family_count=5,
                family_size=10,
                persistence_backend="pickle",
            )
            engine = MyceliumEngine(config)

            engine.init_state()
            engine.run(2)
            path = state_file(state_dir, "pickle")
            self.assertTrue(path.exists())
            with path.open("rb") as handle:
                payload = pickle.load(handle)
            self.assertEqual(payload["format"], 4)
            state = load_state(state_dir, "pickle")
            self.assertEqual(state.round_index, 2)

    def test_pickle_checkpoint_supports_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            config = Config(
                seed=101,
                state_dir=str(state_dir),
                family_count=5,
                family_size=10,
                persistence_backend="pickle",
                checkpoint_every=1,
            )
            engine = MyceliumEngine(config)

            engine.init_state()
            engine.run(2)
            restored = engine.rollback(1)
            self.assertEqual(restored.round_index, 1)


if __name__ == "__main__":
    unittest.main()
