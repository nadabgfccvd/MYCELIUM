"""C3 — advisory diagnostics: descriptive power/margin sheets, verdicts untouched.

Pins: paired_power math (null==alpha, golden, monotonic, edges),
diagnose_comparison notes/thresholds, the S1/OBF boundary derivation, and —
most importantly — that no decision-path module references the advisory API.
"""
from __future__ import annotations

import math
import unittest
from pathlib import Path
from statistics import NormalDist

from mycelium_accel.accelerate_generic import (
    SEQUENTIAL_ALPHA,
    SEQUENTIAL_CONFIDENCE,
    SEQUENTIAL_LOOK_SEEDS,
    SEQUENTIAL_TOTAL_SEEDS,
)
from mycelium_accel.stats import (
    ADVISORY_NOISY_CI_RATIO,
    ADVISORY_POWER_TARGET,
    ADVISORY_THIN_MARGIN_RATIO,
    AcceptancePolicy,
    PairedComparison,
    compare_paired_metric,
    diagnose_comparison,
    paired_power,
)

ROOT = Path(__file__).resolve().parent.parent
_NORM = NormalDist()


def _comp(**over) -> PairedComparison:
    base = dict(
        metric="m", n_pairs=7, mean_delta=1.0, median_delta=1.0,
        ci_low=0.5, ci_high=1.5, confidence=0.95, p_value=0.01,
        p_value_corrected=0.02, effect_dz=1.2, prob_superior=0.9,
        direction=1, deltas=[1.0] * 7,
    )
    base.update(over)
    return PairedComparison(**base)


class PairedPowerTests(unittest.TestCase):
    def test_null_power_equals_alpha(self) -> None:
        for alpha in (0.01, 0.05, 0.10):
            with self.subTest(alpha=alpha):
                self.assertAlmostEqual(paired_power(0.0, 7, alpha=alpha), alpha)

    def test_golden_and_sanity_band(self) -> None:
        got = paired_power(0.8, 10)
        # Independent wiring pin: same textbook formula, computed here.
        expected = _NORM.cdf(0.8 * math.sqrt(10) - _NORM.inv_cdf(0.95))
        self.assertAlmostEqual(got, expected, places=9)
        # Math-truth pin: R power.t.test(paired, n=10, d=0.8, 1-sided) ≈ 0.80;
        # the normal approximation must land in a wide band around it.
        self.assertGreater(got, 0.75)
        self.assertLess(got, 0.85)

    def test_bounded_and_monotone(self) -> None:
        for dz in (-2.0, -0.5, 0.0, 0.2, 0.8, 2.0):
            powers = [paired_power(dz, n) for n in (1, 2, 5, 7, 16, 50)]
            for p in powers:
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)
            # In n: non-decreasing for dz >= 0 (more data helps a real
            # effect), non-increasing for dz < 0 (more data kills a
            # wrong-direction fluke) — both are the textbook formula.
            for lo, hi in zip(powers, powers[1:]):
                if dz >= 0:
                    self.assertLessEqual(lo, hi + 1e-12)
                else:
                    self.assertGreaterEqual(lo, hi - 1e-12)
        for n in (3, 7, 16):
            powers = [paired_power(dz, n) for dz in (-1.0, 0.0, 0.5, 1.5)]
            for lo, hi in zip(powers, powers[1:]):
                self.assertLessEqual(lo, hi + 1e-12)

    def test_non_finite_conventions(self) -> None:
        self.assertEqual(paired_power(float("nan"), 7), 0.0)
        self.assertEqual(paired_power(float("-inf"), 7), 0.0)
        self.assertEqual(paired_power(float("inf"), 7), 1.0)

    def test_invalid_inputs_raise(self) -> None:
        for bad_alpha in (0.0, 1.0, -0.1, float("nan")):
            with self.subTest(alpha=bad_alpha), self.assertRaises(ValueError):
                paired_power(0.5, 7, alpha=bad_alpha)
        for bad_n in (0, -3, 2.5, True):
            with self.subTest(n=bad_n), self.assertRaises(ValueError):
                paired_power(0.5, bad_n)  # type: ignore[arg-type]
        for bad_dz in ("x", None, True):
            with self.subTest(dz=bad_dz), self.assertRaises(ValueError):
                paired_power(bad_dz, 7)  # type: ignore[arg-type]


class DiagnoseComparisonTests(unittest.TestCase):
    def test_stable_keys(self) -> None:
        sheet = diagnose_comparison(_comp())
        self.assertEqual(
            sorted(sheet),
            sorted(["metric", "n_pairs", "effect_dz", "approx_power_one_sided",
                    "power_alpha", "ci_width", "margin_above_zero",
                    "rel_margin", "exact_p_floor", "notes"]),
        )
        self.assertEqual(sheet["metric"], "m")
        self.assertEqual(sheet["n_pairs"], 7)
        self.assertAlmostEqual(sheet["ci_width"], 1.0)
        self.assertAlmostEqual(sheet["margin_above_zero"], 0.5)
        self.assertAlmostEqual(sheet["rel_margin"], 0.5)
        self.assertAlmostEqual(sheet["exact_p_floor"], 1.0 / 128)

    def test_strong_win_is_quiet(self) -> None:
        sheet = diagnose_comparison(_comp())
        self.assertEqual(sheet["notes"], [])

    def test_thin_margin_note(self) -> None:
        sheet = diagnose_comparison(_comp(mean_delta=1.0, ci_low=0.05, ci_high=1.2))
        self.assertTrue(any("thin" in note for note in sheet["notes"]),
                        sheet["notes"])

    def test_noisy_ci_note(self) -> None:
        sheet = diagnose_comparison(_comp(mean_delta=1.0, ci_low=-2.0, ci_high=2.5))
        self.assertTrue(any("noisy" in note for note in sheet["notes"]),
                        sheet["notes"])

    def test_low_power_note(self) -> None:
        sheet = diagnose_comparison(_comp(effect_dz=0.1))
        self.assertTrue(any("power" in note for note in sheet["notes"]),
                        sheet["notes"])

    def test_small_n_notes(self) -> None:
        below = diagnose_comparison(_comp(n_pairs=2))
        self.assertTrue(any("min_pairs" in note for note in below["notes"]),
                        below["notes"])
        self.assertIsNone(below["exact_p_floor"])
        mc = diagnose_comparison(_comp(n_pairs=5))
        self.assertTrue(any("Monte-Carlo" in note for note in mc["notes"]),
                        mc["notes"])
        self.assertIsNone(mc["exact_p_floor"])

    def test_zero_mean_has_no_rel_margin(self) -> None:
        sheet = diagnose_comparison(_comp(mean_delta=0.0, ci_low=-0.5, ci_high=0.5))
        self.assertIsNone(sheet["rel_margin"])
        self.assertFalse(any("thin" in note for note in sheet["notes"]))

    def test_real_comparison_end_to_end(self) -> None:
        comp = compare_paired_metric("secs", [1.0] * 7, [0.8] * 7,
                                     direction=-1, alternative="greater")
        sheet = diagnose_comparison(comp)
        self.assertEqual(sheet["n_pairs"], 7)
        self.assertGreater(sheet["approx_power_one_sided"], 0.5)
        self.assertIsInstance(sheet["notes"], list)

    def test_thresholds_are_documented_constants(self) -> None:
        self.assertEqual(ADVISORY_POWER_TARGET, 0.80)
        self.assertEqual(ADVISORY_THIN_MARGIN_RATIO, 0.10)
        self.assertEqual(ADVISORY_NOISY_CI_RATIO, 2.0)


class SequentialBoundaryAuditTests(unittest.TestCase):
    def test_obf_derivation_is_pinned(self) -> None:
        self.assertEqual(SEQUENTIAL_TOTAL_SEEDS, 7)
        self.assertEqual(SEQUENTIAL_LOOK_SEEDS, 6)
        # O'Brien-Fleming two-sided at information fraction 6/7:
        # z = 1.96*sqrt(7/6); p = 2*(1-Phi(z)).
        z = 1.96 * math.sqrt(7.0 / 6.0)
        self.assertAlmostEqual(z, 2.117, places=3)
        derived_p = 2.0 * (1.0 - _NORM.cdf(z))
        # The constant is the derivation floored to 4 dp (0.034256… → 0.0342):
        # a STRICTER gate than the exact OBF number (conservative direction,
        # Type I validated by simulation). Never round it up without a
        # re-validation of the S1 kill criteria.
        self.assertLessEqual(SEQUENTIAL_ALPHA, derived_p)
        self.assertAlmostEqual(SEQUENTIAL_ALPHA, derived_p, places=3)
        self.assertEqual(SEQUENTIAL_ALPHA, 0.0342)
        self.assertAlmostEqual(
            SEQUENTIAL_CONFIDENCE, 1.0 - SEQUENTIAL_ALPHA, places=9)

    def test_policy_default_min_pairs_still_three(self) -> None:
        self.assertEqual(AcceptancePolicy().min_pairs, 3)


class AdvisoryIsolationTests(unittest.TestCase):
    """No verdict may change because of advisory code: pin the absence."""

    DECISION_MODULES = ("accelerate_generic.py", "bench.py", "__main__.py",
                        "self_improve.py")

    def test_decision_path_never_imports_advisory(self) -> None:
        for module in self.DECISION_MODULES:
            text = (ROOT / "mycelium_accel" / module).read_text(encoding="utf-8")
            with self.subTest(module=module):
                for token in ("paired_power", "diagnose_comparison", "ADVISORY_"):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
