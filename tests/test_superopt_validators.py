from __future__ import annotations

import unittest

from mycelium_accel.ast_transforms import apply_source_transforms
from mycelium_accel.superoptimize import (
    enumerate_expressions,
    postfix_to_python,
    superoptimize_function,
    superoptimize_to_lambda,
)
from mycelium_accel.validators import verify_equivalent, verify_equivalent_with_cases, verify_metamorphic
from mycelium_accel.validators.metamorphic import NEGATION


class ValidatorTests(unittest.TestCase):
    def test_verify_equivalent_identical_functions(self) -> None:
        report = verify_equivalent(lambda x: x * 2 + 1, lambda x: x + x + 1, n_cases=200)
        self.assertTrue(report.equivalent)
        self.assertEqual(report.mismatches, 0)

    def test_verify_equivalent_detects_mismatch(self) -> None:
        report = verify_equivalent(lambda x: x * 2, lambda x: x * 3, n_cases=64)
        self.assertFalse(report.equivalent)
        self.assertIsNotNone(report.first_mismatch)

    def test_verify_equivalent_with_cases(self) -> None:
        report = verify_equivalent_with_cases(lambda x: x + 1, lambda x: x - 1, [[1], [2]])
        self.assertFalse(report.equivalent)
        self.assertEqual(report.cases_run, 2)

    def test_metamorphic(self) -> None:
        report = verify_metamorphic(lambda x: x * x, NEGATION, n_cases=32)
        self.assertTrue(report.holds)


class AstTransformTests(unittest.TestCase):
    def test_constant_folding(self) -> None:
        result = apply_source_transforms("def f(x):\n    return x + 3 * 4\n")
        self.assertTrue(result.changed)
        self.assertIn("12", result.source)
        namespace = {}
        exec(result.source, namespace)
        self.assertEqual(namespace["f"](2), 14)

    def test_strength_reduction(self) -> None:
        result = apply_source_transforms("def f(x):\n    return x * 2\n")
        self.assertTrue(result.changed)
        namespace = {}
        exec(result.source, namespace)
        self.assertEqual(namespace["f"](21), 42)

    def test_invariant_hoisting_preserves_semantics(self) -> None:
        source = (
            "def f(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        k = 3 + 4\n"
            "        total += item * k\n"
            "    return total\n"
        )
        result = apply_source_transforms(source)
        namespace = {}
        exec(result.source, namespace)
        exec(source, {})
        self.assertEqual(namespace["f"]([1, 2, 3]), 42)


class SuperoptimizeTests(unittest.TestCase):
    def test_finds_cheapest_equivalent(self) -> None:
        target = lambda x: x + x + x  # 3x
        result = superoptimize_function(target, max_cost=6, timeout_seconds=10.0)
        self.assertTrue(result.equivalent)
        self.assertIsNotNone(result.expr_source)
        for x in range(-64, 65):
            from mycelium_accel.superoptimize import _eval_expr

            self.assertEqual(_eval_expr(result.expr_source, x), target(x))

    def test_postfix_to_python_compiles(self) -> None:
        python_expr = postfix_to_python("x 1 add 2 mul")
        fn = eval(f"lambda x: {python_expr}")
        self.assertEqual(fn(5), 12)  # (5+1)*2

    def test_lambda_pipeline_reverifies(self) -> None:
        result, fn = superoptimize_to_lambda(lambda x: x * 2 + 2, max_cost=6, timeout_seconds=10.0)
        self.assertTrue(result.equivalent)
        self.assertIsNotNone(fn)
        for x in range(-50, 51):
            self.assertEqual(fn(x), x * 2 + 2)

    def test_enumeration_is_cost_ordered(self) -> None:
        exprs = enumerate_expressions(4)
        from mycelium_accel.superoptimize import _expr_cost

        costs = [_expr_cost(expr) for expr in exprs]
        self.assertEqual(costs, sorted(costs))

    def test_impossible_target_returns_no_solution(self) -> None:
        # oscillating function not expressible in the small grammar
        target = lambda x: (x % 3) * x - (x % 5)
        result = superoptimize_function(target, max_cost=3, timeout_seconds=2.0)
        self.assertFalse(result.equivalent)


if __name__ == "__main__":
    unittest.main()
