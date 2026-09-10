"""Q1.1 — property tests for the statistical core (hypothesis, dev-dep only).

Every property here must hold BY CONSTRUCTION. If one fails, the bug is in
``mycelium_accel/stats.py``, not in the test (inverted kill rule).

Profiles: ``fast`` (loop, ~20 examples) is the default; the full CI job sets
``HYPOTHESIS_PROFILE=ci`` (~200 examples). Statistical tests are deterministic
(fixed master seeds) so they never flake — only the tolerance can be wrong,
and tolerances are coarse by design (they catch gross errors, not drift).
"""
from __future__ import annotations

import math
import os
import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mycelium_accel.stats import (
    bca_bootstrap_ci,
    compare_paired_metric,
    effect_size,
    multiple_testing_correction,
    paired_deltas,
    percentile_ci,
    sign_flip_permutation_test,
)

settings.register_profile("fast", max_examples=20, suppress_health_check=list(HealthCheck))
settings.register_profile("ci", max_examples=200, suppress_health_check=list(HealthCheck))
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "fast"))

deltas_st = st.lists(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=20,
)
pvalues_st = st.lists(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    min_size=1,
    max_size=12,
)


class TestPairedDeltas:
    @given(st.lists(st.floats(-1e3, 1e3, allow_nan=False, allow_infinity=False), min_size=1, max_size=10))
    def test_direction_flip_negates(self, xs: list[float]) -> None:
        base = [0.0] * len(xs)
        assert paired_deltas(base, xs, direction=-1) == [-v for v in paired_deltas(base, xs, direction=1)]

    def test_rejects_mismatched_and_empty(self) -> None:
        with pytest.raises(ValueError):
            paired_deltas([1.0], [1.0, 2.0])
        with pytest.raises(ValueError):
            paired_deltas([], [])


class TestPermutation:
    @given(deltas_st)
    def test_p_in_unit_interval(self, deltas: list[float]) -> None:
        for alt in ("two-sided", "greater"):
            p = sign_flip_permutation_test(deltas, n_permutations=199, seed=7, alternative=alt)
            assert 0.0 <= p <= 1.0

    @given(st.integers(min_value=7, max_value=16))
    def test_all_positive_greater_is_exact_floor(self, n: int) -> None:
        deltas = [0.5 + i * 0.01 for i in range(n)]
        assert sign_flip_permutation_test(deltas, alternative="greater") == pytest.approx(1.0 / 2**n)

    @given(deltas_st)
    def test_exact_path_is_grid_aligned(self, deltas: list[float]) -> None:
        n = len(deltas)
        p = sign_flip_permutation_test(deltas, alternative="two-sided")
        if 7 <= n <= 16:
            grid = p * 2**n
            assert grid == pytest.approx(round(grid), abs=1e-9)

    @given(deltas_st)
    def test_all_zero_gives_one(self, deltas: list[float]) -> None:
        zeros = [0.0] * len(deltas)
        assert sign_flip_permutation_test(zeros, alternative="two-sided") == 1.0
        assert sign_flip_permutation_test(zeros, alternative="greater") == 1.0

    def test_rejects_empty_and_unknown_alternative(self) -> None:
        with pytest.raises(ValueError):
            sign_flip_permutation_test([])
        with pytest.raises(ValueError):
            sign_flip_permutation_test([1.0], alternative="less")


class TestBootstrapCI:
    @given(deltas_st)
    def test_bca_ordered(self, deltas: list[float]) -> None:
        lo, hi = bca_bootstrap_ci(deltas, n_bootstrap=200, seed=7)
        assert lo <= hi

    @given(st.floats(-1e3, 1e3, allow_nan=False, allow_infinity=False), st.integers(1, 12))
    def test_constant_data_gives_point(self, c: float, n: int) -> None:
        # NOTE: exact equality is too strict — sum([c]*n)/n differs from c by
        # ~1 ulp. The honest property: degenerate input -> (near-)zero width
        # centered at c.
        deltas = [c] * n
        tol = 1e-9 * max(1.0, abs(c))
        for ci_fn in (bca_bootstrap_ci, percentile_ci):
            lo, hi = ci_fn(deltas, n_bootstrap=200, seed=7)
            assert abs(hi - lo) <= tol
            assert lo == pytest.approx(c, abs=tol)
            assert hi == pytest.approx(c, abs=tol)

    @given(deltas_st)
    def test_percentile_symmetry(self, deltas: list[float]) -> None:
        lo, hi = percentile_ci(deltas, n_bootstrap=300, seed=7)
        nlo, nhi = percentile_ci([-v for v in deltas], n_bootstrap=300, seed=7)
        assert nlo == pytest.approx(-hi, rel=1e-12)
        assert nhi == pytest.approx(-lo, rel=1e-12)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            bca_bootstrap_ci([])


class TestCorrections:
    @given(pvalues_st)
    def test_holm_bounds_and_order(self, ps: list[float]) -> None:
        corr = multiple_testing_correction(ps, method="holm")
        m = len(ps)
        for raw, adj in zip(ps, corr):
            assert raw - 1e-12 <= adj <= 1.0
            assert adj <= min(1.0, m * raw) + 1e-12  # uniformly beats Bonferroni
        order = sorted(range(m), key=lambda i: ps[i])
        for a, b in zip(order, order[1:]):
            assert corr[a] <= corr[b] + 1e-12

    @given(pvalues_st)
    def test_bh_bounds_and_order(self, ps: list[float]) -> None:
        corr = multiple_testing_correction(ps, method="bh")
        m = len(ps)
        for raw, adj in zip(ps, corr):
            assert raw - 1e-12 <= adj <= 1.0
        order = sorted(range(m), key=lambda i: ps[i])
        for a, b in zip(order, order[1:]):
            assert corr[a] <= corr[b] + 1e-12

    @given(pvalues_st)
    def test_none_is_identity(self, ps: list[float]) -> None:
        assert multiple_testing_correction(ps, method="none") == ps

    def test_empty_and_unknown(self) -> None:
        assert multiple_testing_correction([]) == []
        with pytest.raises(ValueError):
            multiple_testing_correction([0.1], method="bonferroni-typo")


class TestEffectSize:
    @given(deltas_st)
    def test_prob_superior_and_median_bounds(self, deltas: list[float]) -> None:
        dz, median, prob = effect_size(deltas)
        assert 0.0 <= prob <= 1.0
        assert min(deltas) <= median <= max(deltas)
        assert math.isfinite(dz) or math.isinf(dz)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            effect_size([])


class TestComparePaired:
    @given(deltas_st)
    def test_structural_invariants(self, deltas: list[float]) -> None:
        base = [0.0] * len(deltas)
        comp = compare_paired_metric("m", base, deltas, n_bootstrap=200, n_permutations=199, seed=7)
        assert comp.n_pairs == len(deltas)
        assert len(comp.deltas) == len(deltas)
        assert 0.0 <= comp.p_value <= 1.0
        assert comp.ci_low <= comp.ci_high
        assert comp.direction in (1, -1)


@pytest.mark.slow
class TestStatisticalValidity:
    """Deterministic statistical checks (fixed master seed — never flake)."""

    def test_p_uniform_under_null(self) -> None:
        rng = random.Random(20260910)
        ps = []
        for _ in range(200):
            deltas = [rng.gauss(0.0, 1.0) for _ in range(8)]
            ps.append(sign_flip_permutation_test(deltas, alternative="two-sided"))
        frac = sum(1 for p in ps if p < 0.05) / len(ps)
        assert frac <= 0.10, f"too many small p under H0: {frac}"

    def test_bca_coverage_normal(self) -> None:
        rng = random.Random(20260911)
        covered = 0
        trials = 120
        for _ in range(trials):
            deltas = [rng.gauss(0.0, 1.0) for _ in range(8)]
            lo, hi = bca_bootstrap_ci(deltas, confidence=0.95, n_bootstrap=500, seed=13)
            covered += lo <= 0.0 <= hi
        assert covered / trials >= 0.85, f"BCa coverage collapsed: {covered}/{trials}"
