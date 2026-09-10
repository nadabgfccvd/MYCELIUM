from __future__ import annotations

import unittest

from mycelium_accel.stats import (
    AcceptancePolicy,
    bca_bootstrap_ci,
    compare_paired_metric,
    effect_size,
    multiple_testing_correction,
    paired_deltas,
    sequential_racing,
    sign_flip_permutation_test,
)


class PairedDeltaTests(unittest.TestCase):
    def test_deltas_sign_adjusted(self) -> None:
        self.assertEqual(paired_deltas([1, 2, 3], [2, 3, 4]), [1.0, 1.0, 1.0])
        self.assertEqual(paired_deltas([1.0, 2.0], [0.5, 1.0], direction=-1), [0.5, 1.0])

    def test_deltas_require_equal_length(self) -> None:
        with self.assertRaises(ValueError):
            paired_deltas([1.0], [1.0, 2.0])


class BootstrapTests(unittest.TestCase):
    def test_bca_ci_detects_clear_improvement(self) -> None:
        deltas = [0.10, 0.12, 0.08, 0.11, 0.09, 0.13, 0.10, 0.12]
        low, high = bca_bootstrap_ci(deltas, n_bootstrap=1000)
        self.assertGreater(low, 0.0)
        self.assertLess(low, 0.11)
        self.assertGreater(high, low)

    def test_bca_ci_includes_zero_for_noise(self) -> None:
        deltas = [0.05, -0.06, 0.03, -0.02, 0.01, -0.04, 0.06, -0.05]
        low, high = bca_bootstrap_ci(deltas, n_bootstrap=1000)
        self.assertLessEqual(low, 0.0)
        self.assertGreaterEqual(high, 0.0)

    def test_bca_ci_degenerate_single_value(self) -> None:
        low, high = bca_bootstrap_ci([0.5], n_bootstrap=100)
        self.assertEqual((low, high), (0.5, 0.5))


class PermutationTests(unittest.TestCase):
    def test_permutation_significant_for_consistent_deltas(self) -> None:
        deltas = [0.2] * 6
        p_value = sign_flip_permutation_test(deltas)
        self.assertLessEqual(p_value, 0.05)

    def test_permutation_nonsignificant_for_mixed_signs(self) -> None:
        deltas = [0.2, -0.2, 0.1, -0.1, 0.05, -0.05]
        p_value = sign_flip_permutation_test(deltas)
        self.assertGreater(p_value, 0.5)

    def test_permutation_uses_exact_enumeration_for_medium_n(self) -> None:
        deltas = [1.0] * 8
        p_value = sign_flip_permutation_test(deltas)
        self.assertAlmostEqual(p_value, 2 / 256, places=5)


class EffectSizeTests(unittest.TestCase):
    def test_effect_sizes(self) -> None:
        dz, median, prob = effect_size([1.0, 1.0, 1.0, 1.0])
        self.assertEqual(median, 1.0)
        self.assertEqual(prob, 1.0)
        self.assertEqual(dz, float("inf"))


class CorrectionTests(unittest.TestCase):
    def test_holm_monotone(self) -> None:
        corrected = multiple_testing_correction([0.01, 0.04, 0.20], method="holm")
        self.assertAlmostEqual(corrected[0], 0.03, places=6)
        self.assertAlmostEqual(corrected[1], 0.08, places=6)
        self.assertGreater(corrected[2], corrected[1])

    def test_bh(self) -> None:
        corrected = multiple_testing_correction([0.01, 0.02, 0.03], method="bh")
        self.assertAlmostEqual(corrected[0], 0.03, places=6)

    def test_invalid_method(self) -> None:
        with self.assertRaises(ValueError):
            multiple_testing_correction([0.5], method="bogus")


class ComparisonTests(unittest.TestCase):
    def test_compare_paired_metric_full_payload(self) -> None:
        comparison = compare_paired_metric(
            "speed",
            [10.0, 11.0, 9.5, 10.2, 10.1, 9.9],
            [12.0, 12.5, 11.5, 12.2, 12.0, 11.8],
            n_bootstrap=500,
        )
        self.assertGreater(comparison.ci_low, 0.0)
        self.assertLessEqual(comparison.p_value, 0.05)
        self.assertGreater(comparison.effect_dz, 0.0)
        payload = comparison.to_dict()
        self.assertIn("deltas", payload)
        self.assertEqual(len(payload["deltas"]), 6)


class SequentialRacingTests(unittest.TestCase):
    def test_racing_eliminates_obvious_losers_early(self) -> None:
        candidates = {
            "good": lambda round_index, seed: 10.0,
            "bad": lambda round_index, seed: 5.0,
            "mediocre": lambda round_index, seed: 9.0,
        }
        result = sequential_racing(candidates, seeds=[101, 103, 107, 109, 113, 127], min_rounds=3)
        self.assertEqual(result.champion, "good")
        self.assertIn("bad", result.eliminated)

    def test_racing_keeps_close_candidates_alive(self) -> None:
        candidates = {
            "a": lambda round_index, seed: 10.0,
            "b": lambda round_index, seed: 10.0,
        }
        result = sequential_racing(candidates, seeds=[101, 103, 107], min_rounds=2)
        self.assertEqual(result.eliminated, [])
        self.assertIn(result.champion, {"a", "b"})


class PolicyTests(unittest.TestCase):
    def test_policy_defaults_are_conservative(self) -> None:
        policy = AcceptancePolicy()
        self.assertEqual(policy.confidence, 0.95)
        self.assertLess(policy.alpha, policy.quality_alpha)


if __name__ == "__main__":
    unittest.main()
