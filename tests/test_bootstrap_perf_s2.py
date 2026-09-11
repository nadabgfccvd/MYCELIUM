"""Sessão 2, Ciclo 3 — bootstrap memoization: determinism + frozen numerics.

The decision core caches the bootstrap *index matrix* per (n, n_bootstrap,
seed) and indexes each comparison's deltas with it. These tests pin that the
optimization (a) returns bit-identical confidence intervals to the inlined
re-draw it replaced, and (b) actually memoizes (same args -> same matrix
object; the statistics remain correct for varied inputs). Values below were
captured from the pre-optimization implementation.
"""
from __future__ import annotations

import unittest

from mycelium_accel.stats import (
    _bootstrap_index_matrix,
    bca_bootstrap_ci,
    percentile_ci,
)

DATA_A = [0.10, 0.12, 0.09, 0.11, 0.13, 0.10, 0.12]
DATA_B = [-1.0, 2.0, -3.0, 4.0, -5.0]


class BitIdenticalIntervalsTests(unittest.TestCase):
    def test_bca_pinned_to_pre_optimization_values(self) -> None:
        lo, hi = bca_bootstrap_ci(DATA_A)
        self.assertEqual((lo, hi), (0.09999999999999999, 0.12))
        self.assertEqual(bca_bootstrap_ci(DATA_B), (-3.4, 2.2))

    def test_percentile_pinned_to_pre_optimization_values(self) -> None:
        self.assertEqual(percentile_ci(DATA_A), (0.1, 0.12))
        self.assertEqual(percentile_ci(DATA_B), (-3.4, 2.2))

    def test_repeated_calls_bit_identical(self) -> None:
        first = bca_bootstrap_ci(DATA_A, n_bootstrap=321, seed=7)
        second = bca_bootstrap_ci(DATA_A, n_bootstrap=321, seed=7)
        self.assertEqual(first, second)


class IndexMatrixTests(unittest.TestCase):
    def test_shape_and_range(self) -> None:
        matrix = _bootstrap_index_matrix(n=7, n_bootstrap=50, seed=13)
        self.assertEqual(len(matrix), 50)
        self.assertTrue(all(len(row) == 7 for row in matrix))
        self.assertTrue(all(0 <= j < 7 for row in matrix for j in row))

    def test_memoized_by_arguments(self) -> None:
        a = _bootstrap_index_matrix(7, 100, 13)
        b = _bootstrap_index_matrix(7, 100, 13)
        self.assertIs(a, b, "identical arguments must reuse the cached matrix")
        c = _bootstrap_index_matrix(7, 100, 14)
        self.assertIsNot(a, c, "a different RNG seed must yield a new matrix")

    def test_cached_matrix_matches_fresh_draw(self) -> None:
        # Re-draw independently with the documented RNG contract and compare.
        import random
        n, b, seed = 5, 40, 13
        rng = random.Random(seed)
        expected = tuple(tuple(rng.randrange(n) for _ in range(n)) for _ in range(b))
        self.assertEqual(_bootstrap_index_matrix(n, b, seed), expected)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
