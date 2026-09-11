"""Sessão 2, Ciclo 2 — defensive & boundary branches of the stats engine.

Locks down the small branches previously uncovered: the ``significant`` flag,
zero-variance effect size (infinite Cohen's dz), degenerate bootstrap inputs
(constant data, single observation, bad confidence), NaN handling in the
permutation test, multiple-testing correction invariants, exact one-sided
floor, and sequential racing elimination.
"""
from __future__ import annotations

import math
import unittest

from mycelium_accel.stats import (
    PairedComparison,
    bca_bootstrap_ci,
    effect_size,
    multiple_testing_correction,
    percentile_ci,
    sequential_racing,
    sign_flip_permutation_test,
)


def _pc(ci_low: float, ci_high: float) -> PairedComparison:
    return PairedComparison(
        metric="m", n_pairs=3, mean_delta=0.0, median_delta=0.0,
        ci_low=ci_low, ci_high=ci_high, confidence=0.95, p_value=0.1,
        p_value_corrected=None, effect_dz=0.0, prob_superior=0.5, direction=1)


class SignificantFlagTests(unittest.TestCase):
    def test_ci_excluding_zero(self) -> None:
        self.assertTrue(_pc(0.01, 0.9).significant)   # strictly positive band
        self.assertTrue(_pc(-0.9, -0.01).significant)  # strictly negative band
        self.assertFalse(_pc(-0.2, 0.2).significant)   # crosses zero
        self.assertFalse(_pc(0.0, 0.0).significant)    # touches zero -> not established


class EffectSizeTests(unittest.TestCase):
    def test_zero_variance_deltas(self) -> None:
        dz, median, prob = effect_size([0.0, 0.0, 0.0])
        self.assertEqual(dz, 0.0)
        self.assertEqual(median, 0.0)
        self.assertEqual(prob, 0.5)  # all ties
        dz2, med2, prob2 = effect_size([2.0, 2.0, 2.0, 2.0])
        self.assertTrue(math.isinf(dz2) and dz2 > 0)
        self.assertEqual(med2, 2.0)
        self.assertEqual(prob2, 1.0)  # every pair improved
        dz3, _, _ = effect_size([-3.0, -3.0])
        self.assertTrue(math.isinf(dz3) and dz3 < 0)


class BootstrapEdgeTests(unittest.TestCase):
    def test_constant_data_collapses_to_constant(self) -> None:
        lo, hi = bca_bootstrap_ci([5.0] * 5, n_bootstrap=200)
        self.assertAlmostEqual(lo, 5.0, places=6)
        self.assertAlmostEqual(hi, 5.0, places=6)
        lo, hi = percentile_ci([5.0] * 5, n_bootstrap=200)
        self.assertEqual((lo, hi), (5.0, 5.0))

    def test_single_observation(self) -> None:
        self.assertEqual(percentile_ci([7.0]), (7.0, 7.0))
        self.assertEqual(bca_bootstrap_ci([7.0]), (7.0, 7.0))

    def test_invalid_arguments(self) -> None:
        for fn in (bca_bootstrap_ci, percentile_ci):
            with self.assertRaises(ValueError):
                fn([])
            with self.assertRaises(ValueError):
                fn([1.0, 2.0], confidence=0.0)
            with self.assertRaises(ValueError):
                fn([1.0, 2.0], confidence=1.0)


class PermutationTests(unittest.TestCase):
    def test_nan_deltas_fail_to_reject(self) -> None:
        self.assertEqual(sign_flip_permutation_test([1.0, float("nan"), 2.0]), 1.0)
        self.assertEqual(sign_flip_permutation_test([float("inf"), float("nan")]), 1.0)

    def test_empty_and_unknown_alternative_raise(self) -> None:
        with self.assertRaises(ValueError):
            sign_flip_permutation_test([])
        with self.assertRaises(ValueError):
            sign_flip_permutation_test([1.0, 2.0], alternative="left")

    def test_exact_one_sided_floor_seven_pairs(self) -> None:
        # all-positive deltas: only the all-unflipped sign pattern reaches the
        # observed sum -> exact p = 1/128
        p = sign_flip_permutation_test([3.0] * 7, alternative="greater")
        self.assertAlmostEqual(p, 1.0 / 128.0, places=4)


class CorrectionTests(unittest.TestCase):
    def test_invariants(self) -> None:
        raw = [0.001, 0.02, 0.5, 0.9]
        self.assertEqual(multiple_testing_correction(raw, method="none"), raw)
        self.assertEqual(multiple_testing_correction([], method="holm"), [])
        with self.assertRaises(ValueError):
            multiple_testing_correction(raw, method="bonferroni")
        holm = multiple_testing_correction(raw, method="holm")
        self.assertEqual(len(holm), len(raw))
        for r, c in zip(raw, holm):  # correction can never shrink a p-value
            self.assertGreaterEqual(c, r - 1e-12)
            self.assertLessEqual(c, 1.0)
        bh = multiple_testing_correction(raw, method="bh")
        self.assertTrue(all(0.0 <= c <= 1.0 for c in bh))


class SequentialRacingTests(unittest.TestCase):
    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            sequential_racing({}, [101, 103])

    def test_consistent_loser_is_eliminated(self) -> None:
        def good(round_index, seed):
            return 10.0 + ((round_index + seed) % 3) * 0.01

        def bad(round_index, seed):
            return 1.0  # consistently far lower (higher is better)

        result = sequential_racing(
            {"winner": good, "loser": bad},
            [101, 103, 107, 109, 113],
            higher_is_better=True,
            min_rounds=3,
        )
        self.assertEqual(result.champion, "winner")
        self.assertIn("loser", result.eliminated)
        self.assertGreaterEqual(result.rounds_run, 4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
