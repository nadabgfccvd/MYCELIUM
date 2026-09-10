"""Q1.2 — differential validation of the statistical core vs scipy.

Two independent oracles: (1) brute-force re-implementations written in this
file (exact agreement required), (2) scipy.stats (agreement within documented
Monte-Carlo tolerance). All randomness uses fixed seeds — deterministic, never
flakes. scipy is a dev-dep; the runtime stays stdlib-only.
"""

from __future__ import annotations

import itertools
import math
import random

import numpy as np
import pytest
from scipy import stats

from mycelium_accel.stats import (
    bca_bootstrap_ci,
    multiple_testing_correction,
    sign_flip_permutation_test,
)

pytestmark = pytest.mark.slow


def _brute_sign_flip(deltas: list[float], *, two_sided: bool) -> float:
    observed = abs(sum(deltas)) if two_sided else sum(deltas)
    exceed = 0
    total = 0
    for signs in itertools.product((1.0, -1.0), repeat=len(deltas)):
        total += 1
        flipped = sum(s * v for s, v in zip(signs, deltas))
        stat = abs(flipped) if two_sided else flipped
        if stat >= observed - 1e-12:
            exceed += 1
    return exceed / total


def _brute_holm(ps: list[float]) -> list[float]:
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    out = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * ps[idx]))
        out[idx] = running
    return out


def _battery() -> list[list[float]]:
    rng = random.Random(20260910)
    out = []
    for n in (7, 8, 10, 12):
        out.append([rng.gauss(0.0, 1.0) for _ in range(n)])  # null
        out.append([rng.gauss(0.6, 1.0) for _ in range(n)])  # effect
        out.append([rng.expovariate(1.0) - 1.0 for _ in range(n)])  # skewed
    tied = [0.5, -0.5, 0.0, 0.5, -0.5, 0.0, 1.0, -1.0]
    out.append(tied)
    return out


class TestPermutationDifferential:
    def test_exact_matches_brute_force(self) -> None:
        for deltas in _battery():
            for alt, two in (("two-sided", True), ("greater", False)):
                ours = sign_flip_permutation_test(deltas, alternative=alt)
                assert ours == _brute_sign_flip(deltas, two_sided=two), (deltas, alt)

    def test_exact_matches_scipy(self) -> None:
        for i, deltas in enumerate(_battery()):
            arr = np.array(deltas)
            for alt in ("two-sided", "greater"):
                ours = sign_flip_permutation_test(deltas, alternative=alt)
                sp = stats.permutation_test(
                    (arr,),
                    lambda x: float(np.mean(x)),
                    permutation_type="samples",
                    n_resamples=4999,
                    alternative=alt,
                    random_state=1000 + i,
                )
                assert abs(ours - sp.pvalue) <= 0.02, (deltas, alt, ours, sp.pvalue)

    def test_mc_path_matches_scipy(self) -> None:
        # M2: the MC path (n<7, n>16) got 1 dataset in Q1.2; now 12 shapes.
        rng = random.Random(77)
        shapes = []
        for n in (2, 3, 5, 6, 17, 20, 30, 50):
            shapes.append([rng.gauss(0.4, 1.0) for _ in range(n)])
        shapes.append([rng.expovariate(1.0) - 0.6 for _ in range(25)])  # skewed
        shapes.append([float(rng.randint(-3, 3)) for _ in range(20)])  # discrete+ties
        shapes.append(
            [5.0 if i % 7 == 0 else rng.gauss(0, 1) for i in range(30)]
        )  # outlier
        shapes.append([1.0, -1.0])  # minimal pair
        for i, deltas in enumerate(shapes):
            ours = sign_flip_permutation_test(deltas, n_permutations=4999, seed=5)
            sp = stats.permutation_test(
                (np.array(deltas),),
                lambda x: float(np.mean(x)),
                permutation_type="samples",
                n_resamples=4999,
                alternative="two-sided",
                random_state=5,
            )
            assert abs(ours - sp.pvalue) <= 0.03, (i, len(deltas), ours, sp.pvalue)

    def test_mc_path_greater_matches_scipy(self) -> None:
        rng = random.Random(78)
        for i, n in enumerate((3, 6, 20, 40)):
            deltas = [rng.gauss(0.5, 1.0) for _ in range(n)]
            ours = sign_flip_permutation_test(
                deltas, n_permutations=4999, seed=6, alternative="greater"
            )
            sp = stats.permutation_test(
                (np.array(deltas),),
                lambda x: float(np.mean(x)),
                permutation_type="samples",
                n_resamples=4999,
                alternative="greater",
                random_state=6,
            )
            assert abs(ours - sp.pvalue) <= 0.03, (n, ours, sp.pvalue)


class TestBCaDifferential:
    def test_bca_matches_scipy(self) -> None:
        rng = np.random.default_rng(20260910)
        for i in range(6):
            shape = i % 3
            if shape == 0:
                x = rng.normal(0.0, 1.0, size=25)
            elif shape == 1:
                x = rng.normal(0.5, 2.0, size=25)
            else:
                x = rng.exponential(1.0, size=25) - 1.0
            lo, hi = bca_bootstrap_ci(list(x), n_bootstrap=1999, seed=13)
            res = stats.bootstrap(
                (x,), np.mean, method="BCa", n_resamples=1999, random_state=13
            )
            width = max(hi - lo, 1e-12)
            assert abs(lo - res.confidence_interval.low) <= 0.15 * width, i
            assert abs(hi - res.confidence_interval.high) <= 0.15 * width, i


class TestBCaShapesDifferential:
    def test_bca_hostile_shapes_match_scipy(self) -> None:
        # M2: heavy tails, skew, discreteness, tiny n — beyond Q1.2's normals.
        rng = np.random.default_rng(4242)
        datasets = [
            rng.standard_t(3, size=30),  # heavy tails
            rng.exponential(2.0, size=40) - 2.0,  # strong skew
            rng.integers(-5, 6, size=35).astype(float),  # discrete + ties
            rng.normal(0, 1, size=4),  # tiny n
            rng.normal(0, 1, size=6),  # tiny n
            rng.lognormal(0, 1.0, size=30) - np.exp(0.5),  # lognormal centered
        ]
        for i, x in enumerate(datasets):
            lo, hi = bca_bootstrap_ci(list(x), n_bootstrap=1999, seed=13)
            res = stats.bootstrap(
                (x,), np.mean, method="BCa", n_resamples=1999, random_state=13
            )
            width = max(hi - lo, 1e-12)
            assert abs(lo - res.confidence_interval.low) <= 0.20 * width, i
            assert abs(hi - res.confidence_interval.high) <= 0.20 * width, i


class TestCorrectionsDifferential:
    def test_holm_matches_brute_force(self) -> None:
        rng = random.Random(31)
        for _ in range(50):
            ps = [rng.random() ** 2 for _ in range(rng.randint(1, 10))]
            assert multiple_testing_correction(ps, method="holm") == _brute_holm(ps)

    def test_corrections_edge_cases(self) -> None:
        # M2: zeros, ones, duplicates, m=1 — exact vs scipy/brute-force.
        edge = [
            [0.0],
            [1.0],
            [0.0, 0.0, 0.0],
            [1.0, 1.0],
            [0.0, 0.5, 1.0],
            [0.03, 0.03, 0.03, 0.9],
            [1e-12, 0.999999],
        ]
        for ps in edge:
            ref_bh = [float(v) for v in stats.false_discovery_control(ps, method="bh")]
            ours_bh = multiple_testing_correction(ps, method="bh")
            assert ours_bh == ref_bh or all(
                math.isclose(a, b, rel_tol=1e-12) for a, b in zip(ours_bh, ref_bh)
            ), ps
            assert multiple_testing_correction(ps, method="holm") == _brute_holm(ps), ps

    def test_bh_matches_scipy_exactly(self) -> None:
        rng = random.Random(32)
        for _ in range(20):
            ps = [rng.random() ** 2 for _ in range(rng.randint(1, 10))]
            ours = multiple_testing_correction(ps, method="bh")
            ref = [float(v) for v in stats.false_discovery_control(ps, method="bh")]
            assert ours == ref or all(
                math.isclose(a, b, rel_tol=1e-12) for a, b in zip(ours, ref)
            )
