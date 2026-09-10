"""V0.2: replay corpus — verdict equivalence anchor for V2/V4.

Every harness speedup must reproduce these verdicts on frozen sweep data.
Corpus: real sweeps (win, honest loss, baseline-only, flaky, raced C).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import decide_best_candidate
from mycelium_accel.bench import BenchmarkSweep

REPLAY = Path(__file__).resolve().parent / "replay"

EXPECTED = {
    "replay_win.json": "set-fastpath",
    "replay_loss.json": None,
    "replay_baseline_only.json": None,
    "replay_flaky.json": None,
    "replay_raced.json": "O3native",
}


def load(name: str) -> BenchmarkSweep:
    return BenchmarkSweep.from_dict(json.loads((REPLAY / name).read_text(encoding="utf-8")))


class VerdictEquivalenceTests(unittest.TestCase):
    def test_corpus_verdicts_frozen(self) -> None:
        for name, expected in EXPECTED.items():
            with self.subTest(sweep=name):
                sweep = load(name)
                best, _reasons, _comparisons = decide_best_candidate(sweep, "baseline")
                self.assertEqual(best, expected)

    def test_flaky_flag_survives_roundtrip(self) -> None:
        sweep = load("replay_flaky.json")
        self.assertTrue(sweep.summaries[0].flaky)

    def test_serialization_roundtrip_is_stable(self) -> None:
        for name in EXPECTED:
            with self.subTest(sweep=name):
                raw = json.loads((REPLAY / name).read_text(encoding="utf-8"))
                self.assertEqual(BenchmarkSweep.from_dict(raw).to_dict(), raw)

    def test_old_sweeps_without_flaky_default_false(self) -> None:
        sweep = BenchmarkSweep.from_dict({
            "target": "t", "metric": "s", "lower_is_better": True,
            "summaries": [{"candidate": "baseline", "runs": [], "mean": 1.0,
                           "stddev": 0.0, "median": 1.0, "minimum": 1.0, "maximum": 1.0}],
        })
        self.assertFalse(sweep.summaries[0].flaky)


if __name__ == "__main__":
    unittest.main()
