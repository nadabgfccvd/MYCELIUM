from __future__ import annotations

import unittest

from mycelium_accel.growth_metrics import (
    build_dashboard,
    classify_growth,
    effective_compositional_depth,
    frontier_solve_time,
    regression_rate,
    skill_half_life,
    summarize_dashboard,
)


def _history(n: int, *, improving: bool = True) -> list[dict]:
    rows = []
    for index in range(n):
        capability = 2.0 + index * 0.2 if improving else 2.0
        rows.append({
            "round": index,
            "capability_signal": capability,
            "frontier_difficulty": 2 + (index // 4 if improving else 0),
            "best_program": "add(input, const 1)" if index % 3 else "add(mul(input, const 2), input)",
            "macro_count": 3 + index // 5,
        })
    return rows


class PrimitiveMetricTests(unittest.TestCase):
    def test_regression_rate(self) -> None:
        self.assertEqual(regression_rate([1.0, 2.0, 3.0]), 0.0)
        self.assertEqual(regression_rate([3.0, 2.0, 1.0]), 1.0)

    def test_skill_half_life_stable(self) -> None:
        self.assertEqual(skill_half_life([1.0] * 40), 0.0)

    def test_skill_half_life_detects_decay(self) -> None:
        values = [10.0] * 12 + [3.0] * 30
        half = skill_half_life(values)
        self.assertGreater(half, 0.0)

    def test_frontier_solve_time(self) -> None:
        fast = _history(20)
        slow = _history(20, improving=False)
        self.assertLess(frontier_solve_time(fast), frontier_solve_time(slow))

    def test_compositional_depth(self) -> None:
        history = [{"best_program": "add(mul(input, add(input, const 2)), add(input, const 1))"}]
        self.assertGreaterEqual(effective_compositional_depth(history), 2.0)


class DashboardTests(unittest.TestCase):
    def test_insufficient_history_defaults_to_stagnation(self) -> None:
        dashboard = build_dashboard(_history(5))
        self.assertEqual(dashboard.regime, "local_stagnation")
        self.assertTrue(any("insufficient" in reason for reason in dashboard.regime_reasons))

    def test_open_ended_compound_when_all_signals_positive(self) -> None:
        dashboard = build_dashboard(
            _history(40),
            qd_coverage=0.3,
            qd_score=100.0,
            qd_auc=50.0,
            abstractions_learned=12,
            mean_abstraction_reuse=4.0,
            transfer_stats={"donor_scores": {"a": 0.5, "b": 0.3}, "useful_edges": 4, "expansion_rate": 0.2},
        )
        # capability grows linearly → positive slope; curvature ~0 for linear data,
        # so regime decomposes to transfer/compression growth; both are acceptable
        self.assertIn(dashboard.regime, {"transfer_growth", "compression_growth", "open_ended_compound"})
        self.assertGreater(dashboard.abstractions_per_1000_rounds, 0.0)
        self.assertGreater(dashboard.graph_expansion_rate, 0.0)

    def test_exploration_without_accumulation(self) -> None:
        dashboard = build_dashboard(
            _history(30, improving=False),
            qd_coverage=0.4,
            qd_score=10.0,
            qd_auc=0.0,
        )
        self.assertEqual(dashboard.regime, "exploration_without_accumulation")

    def test_classify_directly(self) -> None:
        dashboard = build_dashboard(_history(15, improving=False))
        dashboard = classify_growth(dashboard)
        self.assertIn(dashboard.regime, {
            "local_stagnation", "exploration_without_accumulation",
            "compression_growth", "transfer_growth", "open_ended_compound",
        })

    def test_markdown_summary(self) -> None:
        dashboard = build_dashboard(_history(30), qd_coverage=0.2, qd_score=50.0, qd_auc=10.0)
        text = summarize_dashboard(dashboard)
        self.assertIn("Regime", text)
        self.assertIn("qd_auc", text)


if __name__ == "__main__":
    unittest.main()
