"""C7 — telemetry rotates past ~1 MB; readers merge all parts transparently."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mycelium_accel.telemetry import (
    TELEMETRY_ROTATE_BYTES,
    append_metric,
    full_history,
    metrics_count,
    read_metrics,
    telemetry_path,
)


def _metric(round: int, pad: int = 0) -> dict:
    return {"round": round, "capability_signal": float(round),
            "pad": "x" * pad}


class SingleFileCompatibilityTests(unittest.TestCase):
    def test_no_rotation_small_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "s"
            for i in range(3):
                self.assertTrue(append_metric(state, _metric(i)))
            parts = list((state / "telemetry").glob("*.jsonl"))
            self.assertEqual(len(parts), 1)
            self.assertEqual(parts[0].name, "metrics.jsonl")
            got = read_metrics(state)
            self.assertEqual([m["round"] for m in got], [0, 1, 2])
            self.assertEqual(metrics_count(state), 3)
            self.assertEqual([m["round"] for m in read_metrics(state, limit=2)], [1, 2])
            self.assertEqual([m["round"] for m in read_metrics(state, from_round=2)], [2])
            self.assertEqual(len(full_history([], state)), 3)

    def test_default_threshold_is_1mb(self) -> None:
        self.assertEqual(TELEMETRY_ROTATE_BYTES, 1_000_000)


class RotationTests(unittest.TestCase):
    def test_rotates_and_merges_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "s"
            with mock.patch("mycelium_accel.telemetry.TELEMETRY_ROTATE_BYTES", 300):
                for i in range(10):
                    self.assertTrue(append_metric(state, _metric(i, pad=120)))
            parts = sorted((state / "telemetry").glob("*.jsonl"))
            self.assertGreaterEqual(len(parts), 2)
            self.assertIn("metrics.jsonl", [p.name for p in parts])
            got = read_metrics(state)
            self.assertEqual([m["round"] for m in got], list(range(10)))
            self.assertEqual(metrics_count(state), 10)
            self.assertEqual([m["round"] for m in read_metrics(state, limit=3)], [7, 8, 9])
            self.assertEqual([m["round"] for m in read_metrics(state, from_round=5)],
                             [5, 6, 7, 8, 9])
            self.assertEqual(len(full_history([], state)), 10)

    def test_rotation_failure_never_breaks_appends(self) -> None:
        def boom(src: str, dst: str) -> None:
            raise OSError("injected rotation fault")

        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "s"
            with mock.patch("mycelium_accel.telemetry.TELEMETRY_ROTATE_BYTES", 100), \
                 mock.patch("mycelium_accel.telemetry._replace", side_effect=boom):
                for i in range(5):
                    self.assertTrue(append_metric(state, _metric(i, pad=60)))
            parts = list((state / "telemetry").glob("*.jsonl"))
            self.assertEqual(len(parts), 1)  # rotation skipped, log intact
            self.assertEqual([m["round"] for m in read_metrics(state)],
                             list(range(5)))

    def test_corrupt_lines_skipped_across_parts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "s"
            with mock.patch("mycelium_accel.telemetry.TELEMETRY_ROTATE_BYTES", 200):
                for i in range(4):
                    append_metric(state, _metric(i, pad=100))
            parts = sorted((state / "telemetry").glob("*.jsonl"))
            self.assertGreaterEqual(len(parts), 2)
            for part in parts:
                with part.open("a", encoding="utf-8") as handle:
                    handle.write("{not json\n\n")
            got = read_metrics(state)
            self.assertEqual([m["round"] for m in got], [0, 1, 2, 3])

    def test_missing_state_reads_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "nope"
            self.assertEqual(read_metrics(state), [])
            self.assertEqual(metrics_count(state), 0)
            self.assertEqual(telemetry_path(state).name, "metrics.jsonl")


if __name__ == "__main__":
    unittest.main()
