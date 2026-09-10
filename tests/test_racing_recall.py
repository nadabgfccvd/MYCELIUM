"""V2.2: racing recall harness — the screen rule must never kill a real winner.

Simulates the race_screen elimination rule on frozen replay data (first 3
seeds, first repeat each — exactly what the screen measures). Any future
change to the rule must keep 100% recall here, or die.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from mycelium_accel.bench import BenchmarkSweep
from mycelium_accel.stats import compare_paired_metric
from test_verdict_equivalence import EXPECTED

REPLAY = Path(__file__).resolve().parent / "replay"


def screen_eliminated(sweep: BenchmarkSweep, candidate: str, race_seeds: int = 3) -> bool:
    """Mirror of race_screen's rule on frozen runs (margin 0.0)."""
    base = next(s for s in sweep.summaries if s.candidate == "baseline")
    cand = next(s for s in sweep.summaries if s.candidate == candidate)

    def first_runs(summary):
        seen: dict[int, float] = {}
        for run in summary.runs:
            if run.ok and run.seed not in seen:
                seen[run.seed] = run.value
        return {s: seen[s] for s in sorted(seen)[:race_seeds]}

    base_map, cand_map = first_runs(base), first_runs(cand)
    shared = sorted(set(base_map) & set(cand_map))
    if len(shared) < 2:
        return False  # insufficient evidence -> full sweep decides
    direction = -1 if sweep.lower_is_better else 1
    comp = compare_paired_metric(
        sweep.metric, [base_map[s] for s in shared], [cand_map[s] for s in shared],
        direction=direction, confidence=0.95)
    return comp.ci_high < 0.0


class RacingRecallTests(unittest.TestCase):
    def test_historical_winners_survive_screen(self) -> None:
        checked = 0
        for name, expected_best in EXPECTED.items():
            if expected_best is None:
                continue
            sweep = BenchmarkSweep.from_dict(
                json.loads((REPLAY / name).read_text(encoding="utf-8")))
            with self.subTest(sweep=name):
                self.assertFalse(screen_eliminated(sweep, expected_best))
                checked += 1
        self.assertGreater(checked, 0)

    def test_hopeless_candidate_is_eliminated(self) -> None:
        # sensitivity of the harness itself: 5.6x-worse python-counter must trip the rule
        sweep = BenchmarkSweep.from_dict(
            json.loads((REPLAY / "replay_loss.json").read_text(encoding="utf-8")))
        self.assertTrue(screen_eliminated(sweep, "python-counter"))


if __name__ == "__main__":
    unittest.main()
