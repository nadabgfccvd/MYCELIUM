"""F1: durable telemetry — append JSONL, crash-safe readers, cap signal."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.telemetry import (
    append_metric,
    full_history,
    metrics_count,
    read_metrics,
    telemetry_path,
)


class TelemetryTests(unittest.TestCase):
    def test_append_creates_jsonl_with_one_line_per_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(append_metric(tmp, {"round": 1, "capability_signal": 2.5}))
            self.assertTrue(append_metric(tmp, {"round": 2, "capability_signal": 2.7}))
            lines = telemetry_path(tmp).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["round"], 1)

    def test_read_metrics_skips_corrupt_trailing_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            append_metric(tmp, {"round": 1})
            with telemetry_path(tmp).open("a", encoding="utf-8") as handle:
                handle.write('{"round": 2, BROKEN\n')
            append_metric(tmp, {"round": 3})
            rounds = [m["round"] for m in read_metrics(tmp)]
            self.assertEqual(rounds, [1, 3])

    def test_read_metrics_supports_limit_and_from_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(1, 11):
                append_metric(tmp, {"round": i})
            self.assertEqual(len(read_metrics(tmp, limit=3)), 3)
            self.assertEqual([m["round"] for m in read_metrics(tmp, from_round=8)], [8, 9, 10])
            self.assertEqual(metrics_count(tmp), 10)

    def test_engine_run_writes_durable_log_and_cap_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = str(Path(tmp) / "state")
            config = Config(seed=101, state_dir=state_dir)
            engine = MyceliumEngine(config)
            engine.init_state()
            engine.run(3)
            entries = read_metrics(state_dir)
            self.assertEqual(len(entries), 3)
            self.assertIn("macro_cap_saturated", entries[-1])
            self.assertIsInstance(entries[-1]["macro_cap_saturated"], bool)

    def test_full_history_prefers_durable_log_when_longer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(1, 6):
                append_metric(tmp, {"round": i, "capability_signal": float(i)})
            memory = [{"round": 4}, {"round": 5}]
            merged = full_history(memory, tmp)
            self.assertEqual(len(merged), 5)
            # missing/empty log -> falls back to memory, never raises
            self.assertEqual(full_history(memory, str(Path(tmp) / "nope")), memory)
            self.assertEqual(full_history(memory, None), memory)


if __name__ == "__main__":
    unittest.main()
