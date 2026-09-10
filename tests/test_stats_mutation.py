"""Q4/M1 — mutation-killer battery for the statistical core.

Each test here exists to kill a concrete surviving mutant from the M1
mutation run on ``mycelium_accel/stats.py`` (see docs/m1_report.md for the
full survivor ledger). Two pinning styles:

* **Golden pins**: exact-value assertions on deterministic outputs (fixed
  seeds, small Monte-Carlo budgets for speed). Any change to the algorithm
  must update these deliberately.
* **Contract pins**: structural properties (threading, determinism,
  boundary values) that survived mutants proved were untested.

Stdlib-only and fast (no scipy): this file runs in the inner loop.
"""

from __future__ import annotations

import itertools
import json
import math
import statistics
import unittest

from mycelium_accel.stats import (
    PairedComparison,
    _jackknife_acceleration,
    _quantile,
    apply_correction,
    bca_bootstrap_ci,
    compare_paired_metric,
    effect_size,
    multiple_testing_correction,
    paired_deltas,
    percentile_ci,
    sequential_racing,
    sign_flip_permutation_test,
)

# Fixed Monte-Carlo fixture: 20/20 paired samples, strong positive effect.
BASE = [
    9.105,
    9.544,
    10.554,
    10.325,
    12.282,
    10.926,
    12.292,
    12.254,
    13.664,
    12.649,
    13.374,
    13.738,
    13.93,
    13.813,
    15.053,
    14.725,
    16.115,
    15.43,
    16.291,
    16.927,
]
CAND = [
    10.491,
    9.955,
    11.025,
    11.573,
    12.607,
    12.319,
    13.28,
    12.872,
    14.969,
    13.872,
    14.086,
    15.0,
    14.478,
    14.844,
    15.985,
    15.996,
    16.793,
    16.208,
    17.514,
    17.842,
]
# Fixed null fixture: 20 deltas of pure noise (interior p-values).
NULL = [
    0.37,
    0.277,
    0.333,
    0.78,
    -0.028,
    0.337,
    -0.251,
    -0.936,
    0.508,
    -0.637,
    0.64,
    0.827,
    0.316,
    -0.66,
    -0.326,
    -0.218,
    -0.853,
    -0.086,
    0.146,
    -0.328,
]
NULL_BASE = [5.0] * 20
NULL_CAND = [5.0 + v for v in NULL]
# Integer-heavy right-skewed fixture (bootstrap ties at theta_hat).
SKEW = [0, 0, 1, 1, 2, 3, 5, 8, 13, 21]
# Exactly symmetric fixture (jackknife acceleration == 0.0 exactly).
SYM = [-2.0, -1.0, 0.0, 1.0, 2.0, -1.5, 1.5, 0.5, -0.5, 1.0, -1.0]


def _fake_comparison(p_value: float) -> PairedComparison:
    return PairedComparison(
        metric="m",
        n_pairs=4,
        mean_delta=0.5,
        median_delta=0.5,
        ci_low=0.1,
        ci_high=0.9,
        confidence=0.95,
        p_value=p_value,
        p_value_corrected=None,
        effect_dz=1.0,
        prob_superior=0.75,
        direction=1,
        deltas=[0.4, 0.5, 0.5, 0.6],
    )


class DeterminismTests(unittest.TestCase):
    """Same call twice in-process yields identical output.

    Kills the seed=None mutants (bca#21, sign_flip#50, compare#19/#27,
    racing#69): the subprocess determinism test cannot catch these because
    its children import the unmutated package (mutmut sandbox escape).
    """

    def test_bca_deterministic(self) -> None:
        first = bca_bootstrap_ci(SKEW, n_bootstrap=499, seed=7)
        second = bca_bootstrap_ci(SKEW, n_bootstrap=499, seed=7)
        self.assertEqual(first, second)

    def test_sign_flip_mc_deterministic(self) -> None:
        first = sign_flip_permutation_test(NULL, n_permutations=999, seed=7)
        second = sign_flip_permutation_test(NULL, n_permutations=999, seed=7)
        self.assertEqual(first, second)

    def test_compare_deterministic(self) -> None:
        kwargs = dict(seed=7, n_bootstrap=499, n_permutations=999)
        first = compare_paired_metric("m", BASE, CAND, **kwargs).to_dict()
        second = compare_paired_metric("m", BASE, CAND, **kwargs).to_dict()
        self.assertEqual(first, second)

    def test_racing_deterministic(self) -> None:
        candidates = {"a": lambda ri, s: 10.0, "zzz": lambda ri, s: 0.0}
        first = sequential_racing(candidates, seeds=[11, 12, 13, 14, 15]).to_dict()
        second = sequential_racing(candidates, seeds=[11, 12, 13, 14, 15]).to_dict()
        self.assertEqual(first, second)


class BcaGoldenTests(unittest.TestCase):
    """Exact BCa pins (kills _adjust/alpha/z0/clamp mutants)."""

    def test_golden_skewed(self) -> None:
        # Integer data -> bootstrap ties at theta_hat, so the z0 '<' vs '<='
        # mutant (bca#35) shifts the proportion and the golden catches it.
        low, high = bca_bootstrap_ci(SKEW, n_bootstrap=499, seed=7)
        # CI-2: statistics.NormalDist.cdf drifted in 3.14 (stdlib accuracy
        # rewrite) — 1-ULP dust vs the 3.13 golden. Tolerance keeps killing
        # endpoint mutants (all macroscopic); exactness would pin a stdlib.
        self.assertAlmostEqual(low, 2.5)
        self.assertAlmostEqual(high, 11.08779770148638)

    def test_golden_symmetric(self) -> None:
        # accel == 0.0 exactly here, so 'denom == 0' -> 'denom == 1' (bca#71)
        # collapses the interval to (min, max) of the bootstraps.
        self.assertEqual(_jackknife_acceleration([float(v) for v in SYM]), 0.0)
        low, high = bca_bootstrap_ci(SYM, n_bootstrap=499, seed=7)
        self.assertAlmostEqual(low, -0.720314157793832)  # CI-2: see above
        self.assertAlmostEqual(high, 0.7272727272727273)

    def test_nesting_strict(self) -> None:
        widths = []
        for confidence in (0.50, 0.95, 0.99):
            low, high = bca_bootstrap_ci(
                SKEW, confidence=confidence, n_bootstrap=499, seed=7
            )
            widths.append(high - low)
        self.assertLess(widths[0], widths[1])
        self.assertLess(widths[1], widths[2])


class CompareGoldenTests(unittest.TestCase):
    """Exact compare_paired_metric pins: payload fields + threading."""

    def test_golden_strong_effect(self) -> None:
        comp = compare_paired_metric(
            "m",
            BASE,
            CAND,
            seed=7,
            n_bootstrap=499,
            n_permutations=999,
            alternative="greater",
        )
        self.assertEqual(comp.metric, "m")
        self.assertEqual(comp.n_pairs, 20)
        self.assertEqual(comp.mean_delta, 0.9358999999999998)
        self.assertEqual(comp.median_delta, 0.9599999999999991)
        self.assertAlmostEqual(comp.ci_low, 0.7840073758448264)  # CI-2: see above
        self.assertAlmostEqual(comp.ci_high, 1.080054448286354)
        self.assertEqual(comp.confidence, 0.95)
        self.assertEqual(comp.p_value, 0.001)
        self.assertIsNone(comp.p_value_corrected)
        self.assertEqual(comp.effect_dz, 2.6906276091616133)
        self.assertEqual(comp.prob_superior, 1.0)
        self.assertEqual(comp.direction, 1)
        # Meaning anchors: strong positive effect, CI excludes zero.
        self.assertLessEqual(comp.p_value, 0.01)
        self.assertGreater(comp.ci_low, 0.0)

    def test_golden_null_interior_p(self) -> None:
        # Interior p: seed/n_permutations/alternative threading mutants all
        # move this value (floor p-values would hide them).
        comp = compare_paired_metric(
            "n",
            NULL_BASE,
            NULL_CAND,
            seed=7,
            n_bootstrap=499,
            n_permutations=999,
            alternative="greater",
        )
        self.assertEqual(comp.p_value, 0.472)
        # AlmostEqual: last-ulp libm dust differs on Apple silicon; places=12
        # keeps full mutant-killing power (mutants move this value by ~1e-1).
        self.assertAlmostEqual(comp.ci_low, -0.20256899453462732, places=12)
        self.assertAlmostEqual(comp.ci_high, 0.2380812849358502, places=12)
        self.assertEqual(comp.mean_delta, 0.01054999999999997)
        self.assertEqual(comp.effect_dz, 0.01998526994230381)
        self.assertEqual(comp.prob_superior, 0.5)
        self.assertGreater(comp.p_value, 0.05)

    def test_alternative_threading(self) -> None:
        # compare#32 drops alternative= -> default two-sided; the two
        # alternatives must differ here (0.472 vs 0.914).
        greater = compare_paired_metric(
            "n",
            NULL_BASE,
            NULL_CAND,
            seed=7,
            n_bootstrap=499,
            n_permutations=999,
            alternative="greater",
        ).p_value
        two_sided = compare_paired_metric(
            "n",
            NULL_BASE,
            NULL_CAND,
            seed=7,
            n_bootstrap=499,
            n_permutations=999,
            alternative="two-sided",
        ).p_value
        self.assertEqual(greater, 0.472)
        self.assertEqual(two_sided, 0.914)

    def test_direction_minus_one(self) -> None:
        # compare#65/#66 corrupt the normalized direction payload.
        comp = compare_paired_metric(
            "m",
            BASE,
            CAND,
            seed=7,
            n_bootstrap=499,
            n_permutations=999,
            direction=-1,
        )
        self.assertEqual(comp.direction, -1)
        self.assertEqual(
            comp.deltas, [-v for v in paired_deltas(BASE, CAND, direction=1)]
        )
        # Two-sided p is invariant under a global sign flip.
        plus = compare_paired_metric(
            "m",
            BASE,
            CAND,
            seed=7,
            n_bootstrap=499,
            n_permutations=999,
            direction=1,
        )
        self.assertEqual(comp.p_value, plus.p_value)

    def test_confidence_threading(self) -> None:
        # compare#21 drops confidence= -> default 0.95; widths must nest
        # strictly with the requested level.
        widths = []
        for confidence in (0.50, 0.95, 0.99):
            comp = compare_paired_metric(
                "m",
                BASE,
                CAND,
                seed=7,
                n_bootstrap=499,
                n_permutations=199,
                confidence=confidence,
            )
            self.assertEqual(comp.confidence, confidence)
            widths.append(comp.ci_high - comp.ci_low)
        self.assertLess(widths[0], widths[1])
        self.assertLess(widths[1], widths[2])


class SignFlipMcTests(unittest.TestCase):
    """Exact Monte-Carlo pins on null data (kills #38/#56/#57)."""

    def test_golden_null_greater(self) -> None:
        # Interior p on the greater branch: tolerance-1.0 (#38), dropped
        # accumulation (#56) and negated accumulation (#57) all move it.
        self.assertEqual(
            sign_flip_permutation_test(
                NULL, n_permutations=999, seed=7, alternative="greater"
            ),
            0.472,
        )

    def test_golden_null_two_sided(self) -> None:
        self.assertEqual(
            sign_flip_permutation_test(NULL, n_permutations=999, seed=7),
            0.914,
        )

    def test_strong_effect_floor(self) -> None:
        deltas = [c - b for b, c in zip(BASE, CAND)]
        for alternative in ("greater", "two-sided"):
            p_value = sign_flip_permutation_test(
                deltas, n_permutations=999, seed=7, alternative=alternative
            )
            self.assertLessEqual(p_value, 0.01)

    def test_exact_mid_matches_brute_force(self) -> None:
        # n = 10 takes the exact 2^n path: independent reimplementation.
        deltas = [0.1, -0.2, 0.15, -0.05, 0.3, -0.1, 0.25, -0.15, 0.05, -0.2]
        for two_sided in (True, False):
            alternative = "two-sided" if two_sided else "greater"
            observed = abs(sum(deltas)) if two_sided else sum(deltas)
            exceed = 0
            total = 0
            for signs in itertools.product((1.0, -1.0), repeat=len(deltas)):
                total += 1
                flipped = sum(s * v for s, v in zip(signs, deltas))
                stat = abs(flipped) if two_sided else flipped
                if stat >= observed - 1e-12:
                    exceed += 1
            self.assertEqual(
                sign_flip_permutation_test(deltas, alternative=alternative),
                exceed / total,
            )


class EffectSizeExactTests(unittest.TestCase):
    """Hand-verified effect sizes (kills variance/dz-branch mutants)."""

    def test_n1_degenerate(self) -> None:
        # eff#26 (std init 1.0) yields dz = 5.0 instead of +inf.
        dz, median, prob = effect_size([5.0])
        self.assertTrue(math.isinf(dz) and dz > 0)
        self.assertEqual(median, 5.0)
        self.assertEqual(prob, 1.0)

    def test_n2_exact(self) -> None:
        # eff#13/#14 skip the variance branch at n = 2 (-> dz = +inf).
        dz, median, prob = effect_size([1.0, 3.0])
        self.assertEqual(dz, 2.0 / math.sqrt(2.0))
        self.assertEqual(median, 2.0)  # also kills _quantile#4 (median of 2)
        self.assertEqual(prob, 1.0)

    def test_small_std_exact(self) -> None:
        # std ~= 0.064 < 1: eff#30 ('std > 1') takes the degenerate branch.
        data = [0.1, 0.2, 0.15, 0.25]
        dz, median, prob = effect_size(data)
        expected_dz = statistics.mean(data) / statistics.stdev(data)
        self.assertAlmostEqual(dz, expected_dz, places=12)
        self.assertAlmostEqual(median, 0.175, places=15)
        self.assertEqual(prob, 1.0)

    def test_variance_uses_bessel(self) -> None:
        # eff#16 ('*' (n-1)) and eff#21 ('/' (n+1)) agree with the original
        # only at n = 2; n = 4 separates all three formulas.
        dz, _, _ = effect_size([1.0, 2.0, 3.0, 4.0])
        mean = 2.5
        var = sum((v - mean) ** 2 for v in (1.0, 2.0, 3.0, 4.0)) / 3.0
        self.assertAlmostEqual(dz, mean / math.sqrt(var), places=12)


class CorrectionExactTests(unittest.TestCase):
    """Default methods + corrected-value wiring (kills #1/#2/#7/#12)."""

    def test_mtc_default_is_holm(self) -> None:
        got = multiple_testing_correction([0.01, 0.04, 0.03])
        for value, expected in zip(got, [0.03, 0.06, 0.06]):
            self.assertAlmostEqual(value, expected, places=12)

    def test_apply_default_is_holm(self) -> None:
        comps = [_fake_comparison(0.01), _fake_comparison(0.04)]
        apply_correction(comps)
        self.assertAlmostEqual(comps[0].p_value_corrected, 0.02, places=12)
        self.assertAlmostEqual(comps[1].p_value_corrected, 0.04, places=12)

    def test_apply_bh_explicit(self) -> None:
        # Data separates BH from Holm: bh -> [0.04, 0.04], holm -> [0.06, 0.06].
        comps = [_fake_comparison(0.03), _fake_comparison(0.04)]
        apply_correction(comps, method="bh")
        self.assertAlmostEqual(comps[0].p_value_corrected, 0.04, places=12)
        self.assertAlmostEqual(comps[1].p_value_corrected, 0.04, places=12)


class ConfidenceBoundaryTests(unittest.TestCase):
    """M3: confidence outside (0, 1) fails fast with ValueError (previously
    an inscrutable StatisticsError from NormalDist.inv_cdf)."""

    def test_bca_rejects_boundaries(self) -> None:
        for confidence in (0.0, 1.0, 2.0, -0.5):
            with self.assertRaises(ValueError, msg=f"confidence={confidence}"):
                bca_bootstrap_ci([1.0, 2.0, 3.0], confidence=confidence)

    def test_percentile_rejects_boundaries(self) -> None:
        for confidence in (0.0, 1.0, 2.0, -0.5):
            with self.assertRaises(ValueError, msg=f"confidence={confidence}"):
                percentile_ci([1.0, 2.0, 3.0], confidence=confidence)

    def test_compare_rejects_boundary(self) -> None:
        with self.assertRaises(ValueError):
            compare_paired_metric("m", [1.0, 2.0], [1.5, 2.5], confidence=1.0)


class MinPairsGuardTests(unittest.TestCase):
    """M3: min_pairs=0 never attempts a zero-pair comparison."""

    def test_zero_min_pairs_skips(self) -> None:
        from mycelium_accel.accelerate_generic import decide_best_candidate
        from mycelium_accel.bench import (
            BenchmarkRun,
            BenchmarkSweep,
            summarize_runs,
        )
        from mycelium_accel.stats import AcceptancePolicy

        base = [BenchmarkRun("baseline", s, "m", 10.0, 1.0, True) for s in (0, 1)]
        cand = [BenchmarkRun("a", s, "m", 12.0, 1.0, True) for s in (2, 3)]
        sweep = BenchmarkSweep(
            target="t",
            metric="m",
            lower_is_better=True,
            summaries=[summarize_runs("baseline", base), summarize_runs("a", cand)],
            comparisons=[],
        )
        best, reasons, comparisons = decide_best_candidate(
            sweep, "baseline", policy=AcceptancePolicy(min_pairs=0)
        )
        self.assertIsNone(best)
        self.assertEqual(comparisons, [])
        self.assertTrue(any("paired seeds" in reason for reason in reasons))


class QuantileGuardTests(unittest.TestCase):
    def test_empty_returns_zero(self) -> None:
        self.assertEqual(_quantile([], 0.5), 0.0)

    def test_singleton_returns_element(self) -> None:
        self.assertEqual(_quantile([2.5], 0.99), 2.5)


class JackknifeExactTests(unittest.TestCase):
    def test_acceleration_hand_computed(self) -> None:
        # Independent closed form: leave-one-out means via (S - x_i)/(n-1).
        # Scaled data keeps the denominator in (0, 1), killing jack#33
        # ('denominator > 1'); the value pin kills #19/#21/#24/#31.
        data = [0.1, 0.2, 0.4, 0.8, 0.3]
        n = len(data)
        total = sum(data)
        jack_means = [(total - x) / (n - 1) for x in data]
        center = sum(jack_means) / n
        numerator = sum((center - m) ** 3 for m in jack_means)
        denominator = 6.0 * (sum((center - m) ** 2 for m in jack_means) ** 1.5)
        self.assertGreater(denominator, 0.0)
        self.assertLess(denominator, 1.0)
        self.assertAlmostEqual(
            _jackknife_acceleration(data), numerator / denominator, places=12
        )
        self.assertAlmostEqual(
            _jackknife_acceleration(data), 0.066925194346633, places=12
        )


class PercentileBatteryTests(unittest.TestCase):
    """Percentile CI was pinned only on constant data; pin it properly."""

    def test_golden_skewed(self) -> None:
        self.assertEqual(percentile_ci(SKEW, n_bootstrap=499, seed=7), (1.9, 9.555))

    def test_n2_exact(self) -> None:
        self.assertEqual(percentile_ci([1.0, 3.0], n_bootstrap=499, seed=7), (1.0, 3.0))

    def test_n1_point(self) -> None:
        self.assertEqual(percentile_ci([4.0]), (4.0, 4.0))

    def test_ordered(self) -> None:
        # pct#28/#29 invert the interval (no swap guard here).
        low, high = percentile_ci(SKEW, n_bootstrap=499, seed=7)
        self.assertLessEqual(low, high)

    def test_nesting(self) -> None:
        widths = []
        for confidence in (0.50, 0.95, 0.99):
            low, high = percentile_ci(
                SKEW, confidence=confidence, n_bootstrap=499, seed=7
            )
            widths.append(high - low)
        self.assertLessEqual(widths[0], widths[1])
        self.assertLessEqual(widths[1], widths[2])


class RacingExactTests(unittest.TestCase):
    """Elimination timing via comparison n; adversarial names (best='a').

    Rounds always run all seeds, so min_rounds mutants are observed through
    the stored comparisons' n_pairs (= rounds run before elimination).
    """

    def test_golden_default_min_rounds(self) -> None:
        candidates = {
            "a": lambda ri, s: 10.0,
            "m": lambda ri, s: 5.0,
            "zzz": lambda ri, s: 0.0,
        }
        result = sequential_racing(candidates, seeds=[11, 12, 13, 14, 15])
        self.assertEqual(result.champion, "a")
        self.assertEqual(set(result.eliminated), {"m", "zzz"})
        self.assertEqual(result.rounds_run, 5)
        # Default min_rounds = max(2, min(3, 5)) = 3: elimination at round 3.
        self.assertEqual(
            {k: v.n_pairs for k, v in result.comparisons.items()},
            {"m": 3, "zzz": 3},
        )
        self.assertEqual(
            (result.comparisons["zzz"].ci_low, result.comparisons["zzz"].ci_high),
            (-10.0, -10.0),
        )
        self.assertEqual(
            (result.comparisons["m"].ci_low, result.comparisons["m"].ci_high),
            (-5.0, -5.0),
        )
        self.assertEqual(result.comparisons["zzz"].p_value, 0.2532746725327467)
        self.assertEqual(result.comparisons["zzz"].metric, "race:zzz")
        self.assertEqual(result.comparisons["zzz"].confidence, 0.95)
        # Payload must serialize (comparisons=None mutants crash here).
        json.dumps(result.to_dict())

    def test_default_min_rounds_two_seeds(self) -> None:
        # Default = max(2, min(3, 2)) = 2: elimination at round 2.
        candidates = {"a": lambda ri, s: 10.0, "zzz": lambda ri, s: 0.0}
        result = sequential_racing(candidates, seeds=[11, 12])
        self.assertEqual(result.champion, "a")
        self.assertEqual(result.eliminated, ["zzz"])
        self.assertEqual(result.comparisons["zzz"].n_pairs, 2)

    def test_explicit_min_rounds_one(self) -> None:
        # race#18 ignores an explicit min_rounds (uses the default).
        candidates = {
            "a": lambda ri, s: 10.0,
            "m": lambda ri, s: 5.0,
            "zzz": lambda ri, s: 0.0,
        }
        result = sequential_racing(candidates, seeds=[11, 12, 13, 14, 15], min_rounds=1)
        self.assertEqual(
            {k: v.n_pairs for k, v in result.comparisons.items()},
            {"m": 1, "zzz": 1},
        )

    def test_two_candidates_elimination(self) -> None:
        # race#47 ('len(alive) <= 2') skips elimination with 2 alive.
        candidates = {"a": lambda ri, s: 10.0, "zzz": lambda ri, s: 0.0}
        result = sequential_racing(
            candidates, seeds=[11, 12, 13, 14, 15], confidence=0.99
        )
        self.assertEqual(result.eliminated, ["zzz"])
        self.assertEqual(result.comparisons["zzz"].n_pairs, 3)
        # race#74 drops confidence= -> default 0.95.
        self.assertEqual(result.comparisons["zzz"].confidence, 0.99)

    def test_lower_is_better(self) -> None:
        # race#15/#73 break the direction=-1 path (untested before).
        candidates = {"a": lambda ri, s: 0.0, "zzz": lambda ri, s: 10.0}
        result = sequential_racing(
            candidates, seeds=[11, 12, 13, 14, 15], higher_is_better=False
        )
        self.assertEqual(result.champion, "a")
        self.assertEqual(set(result.eliminated), {"zzz"})
        self.assertEqual(result.comparisons["zzz"].direction, -1)

    def test_champion_with_no_elimination(self) -> None:
        # race#83/#85 (champion by NAME) need 2+ survivors: a futility margin
        # below every CI keeps all three alive, and the best is still 'a'.
        candidates = {
            "a": lambda ri, s: 10.0,
            "m": lambda ri, s: 5.0,
            "zzz": lambda ri, s: 0.0,
        }
        result = sequential_racing(
            candidates, seeds=[11, 12, 13, 14, 15], futility_margin=-100.0
        )
        self.assertEqual(result.eliminated, [])
        self.assertEqual(result.champion, "a")
        self.assertEqual(
            {k: v.n_pairs for k, v in result.comparisons.items()}, {"m": 5, "zzz": 5}
        )

    def test_candidate_receives_round_and_seed(self) -> None:
        # race#40/#41 pass None instead of (round_index, pair_seed).
        seen: list[tuple[int, int]] = []

        def recorder(round_index: int, pair_seed: int) -> float:
            seen.append((round_index, pair_seed))
            return 10.0

        sequential_racing(
            {"a": recorder, "zzz": lambda ri, s: 0.0}, seeds=[11, 12, 13, 14, 15]
        )
        self.assertEqual(seen, [(0, 11), (1, 12), (2, 13), (3, 14), (4, 15)])


if __name__ == "__main__":
    unittest.main()
