"""Q1.5 — numeric edge matrix: specified behavior, pinned by tests.

Spec (conservative instrument: uninformative input never accepts):

===========  =================  ============  ===============================
input        CI                 p (signflip)  decide
===========  =================  ============  ===============================
all zeros    (0, 0)             1.0           no win (CI excludes improvement)
constant c   (c, c)             MC/exact ok   wins iff c > 0 (unanimous)
1 pair       point              1.0           skipped (min_pairs = 3)
any NaN      (nan, nan)         1.0           NEVER wins
any inf      contains inf       1.0           NEVER wins
===========  =================  ============  ===============================
"""
from __future__ import annotations

import math
import unittest

from mycelium_accel.accelerate_generic import check_regression, decide_best_candidate
from mycelium_accel.bench import BenchmarkSweep
from mycelium_accel.stats import (
    bca_bootstrap_ci,
    effect_size,
    sign_flip_permutation_test,
)

SEEDS = [101, 103, 107, 109, 113, 127, 131]


def _sweep(cand_values: list[float]) -> BenchmarkSweep:
    def runs(values: list[float], name: str) -> list[dict]:
        return [
            {"candidate": name, "seed": s, "metric": "seconds",
             "value": v, "seconds": 0.01, "ok": True}
            for s, v in zip(SEEDS, values)
        ]

    return BenchmarkSweep.from_dict({
        "target": "t", "metric": "seconds", "lower_is_better": True,
        "summaries": [
            {"candidate": "baseline", "runs": runs([1.0] * 7, "baseline"),
             "mean": 1.0, "stddev": 0.0, "median": 1.0, "minimum": 1.0, "maximum": 1.0},
            {"candidate": "cand", "runs": runs(cand_values, "cand"),
             "mean": 0.0, "stddev": 0.0, "median": 0.0, "minimum": 0.0, "maximum": 0.0},
        ],
    })


class NumericEdgeTests(unittest.TestCase):
    def test_zeros(self) -> None:
        self.assertEqual(bca_bootstrap_ci([0.0] * 7, n_bootstrap=200), (0.0, 0.0))
        self.assertEqual(sign_flip_permutation_test([0.0] * 7), 1.0)
        dz, median, prob = effect_size([0.0] * 7)
        self.assertEqual((dz, median, prob), (0.0, 0.0, 0.5))
        best, _r, _c = decide_best_candidate(_sweep([1.0] * 7), "baseline")
        self.assertIsNone(best)

    def test_constant_improvement_wins_unanimously(self) -> None:
        self.assertAlmostEqual(bca_bootstrap_ci([0.2] * 7, n_bootstrap=200)[0], 0.2)
        best, _r, _c = decide_best_candidate(_sweep([0.8] * 7), "baseline")
        self.assertEqual(best, "cand")

    def test_constant_regression_loses(self) -> None:
        best, _r, _c = decide_best_candidate(_sweep([1.2] * 7), "baseline")
        self.assertIsNone(best)

    def test_single_pair_skipped(self) -> None:
        sweep = BenchmarkSweep.from_dict({
            "target": "t", "metric": "s", "lower_is_better": True,
            "summaries": [
                {"candidate": "baseline",
                 "runs": [{"candidate": "baseline", "seed": 101, "metric": "s",
                           "value": 1.0, "seconds": 0.01, "ok": True}],
                 "mean": 1.0, "stddev": 0.0, "median": 1.0, "minimum": 1.0, "maximum": 1.0},
                {"candidate": "cand",
                 "runs": [{"candidate": "cand", "seed": 101, "metric": "s",
                           "value": 0.1, "seconds": 0.01, "ok": True}],
                 "mean": 0.1, "stddev": 0.0, "median": 0.1, "minimum": 0.1, "maximum": 0.1},
            ],
        })
        best, reasons, _c = decide_best_candidate(sweep, "baseline")
        self.assertIsNone(best)
        self.assertTrue(any("paired seeds" in r for r in reasons))

    def test_nan_never_wins(self) -> None:
        deltas = [0.2, 0.2, float("nan"), 0.2, 0.2, 0.2, 0.2]
        lo, hi = bca_bootstrap_ci(deltas, n_bootstrap=200)
        self.assertTrue(math.isnan(lo) and math.isnan(hi))
        self.assertEqual(sign_flip_permutation_test(deltas), 1.0)
        best, _r, _c = decide_best_candidate(
            _sweep([0.8, 0.8, float("nan"), 0.8, 0.8, 0.8, 0.8]), "baseline")
        self.assertIsNone(best)

    def test_inf_never_wins(self) -> None:
        deltas = [0.2, 0.2, float("inf"), 0.2, 0.2, 0.2, 0.2]
        self.assertEqual(sign_flip_permutation_test(deltas), 1.0)
        self.assertEqual(sign_flip_permutation_test([float("inf")] * 7), 1.0)
        best, _r, _c = decide_best_candidate(
            _sweep([0.8, 0.8, float("inf"), 0.8, 0.8, 0.8, 0.8]), "baseline")
        self.assertIsNone(best)

    def test_regression_gate_nan_is_conservative(self) -> None:
        bad, _reason = check_regression(
            [1.0, float("nan"), 1.0], [1.0, 1.0, 1.0], 5.0, lower_is_better=True)
        self.assertFalse(bad)


if __name__ == "__main__":
    unittest.main()
