"""Regression: the 8h calibration died because one candidate-search stage
benchmarked ~35 profiles × 7 seeds × 30 rounds with no futility screening.

The fix (tiered screening): a cheap screen stage (fewer rounds, fewer seeds,
mean-based futility) prunes the task list before the full paired benchmark,
capping confirm-stage size at guard.screen_keep_top. This keeps the paired-
statistics decision intact while bounding per-cycle cost.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from mycelium_accel.self_improve import (
    GuardConfig,
    SelfImprover,
)


def _row(seed: int, rps: float):
    return {
        "seed": seed,
        "rounds_per_second": rps,
        "best_score": 3.0,
        "best_exact_rate": 0.4,
        "solved_by_best": 1.0,
        "capability_signal": 3.0,
        "frontier_difficulty": 2.0,
        "active_niches": 5.0,
        "diversity_entropy": 1.0,
        "macro_transfer_mean": 0.1,
        "frontier_learning_progress": 0.2,
        "growth_regime": "linear",
    }


class ScreeningLogicTests(unittest.TestCase):
    def test_guardconfig_has_screening_knobs(self) -> None:
        guard = GuardConfig(seeds=[101, 103, 107])
        self.assertTrue(hasattr(guard, "screen_enabled"))
        self.assertTrue(hasattr(guard, "screen_rounds"))
        self.assertTrue(hasattr(guard, "screen_keep_top"))
        self.assertTrue(guard.screen_enabled)

    def test_screening_keeps_at_most_keep_top(self) -> None:
        """Top-K survivors retained by screen throughput; losers dropped."""
        from mycelium_accel.self_improve import select_screen_survivors

        # 20 candidates: exact rankable means 100..119 rps
        screen_means = {f"cand-{i:02d}": 100.0 + i for i in range(20)}
        baseline_mean = 90.0
        survivors = select_screen_survivors(
            screen_means,
            baseline_mean,
            min_speedup_ratio=0.0,
            keep_top=6,
        )
        self.assertEqual(len(survivors), 6)
        # survivors are the six fastest
        self.assertEqual(sorted(survivors), ["cand-14", "cand-15", "cand-16", "cand-17", "cand-18", "cand-19"])

    def test_futility_drops_everything_below_floor(self) -> None:
        from mycelium_accel.self_improve import select_screen_survivors

        screen_means = {"slow-a": 50.0, "slow-b": 55.0}
        survivors = select_screen_survivors(screen_means, 100.0, min_speedup_ratio=0.05, keep_top=4)
        self.assertEqual(survivors, [])

    def test_keep_top_larger_than_list_returns_all(self) -> None:
        from mycelium_accel.self_improve import select_screen_survivors

        screen_means = {"a": 1.0, "b": 2.0, "c": 3.0}
        survivors = select_screen_survivors(screen_means, 0.0, min_speedup_ratio=0.0, keep_top=50)
        self.assertEqual(sorted(survivors), ["a", "b", "c"])


class ScreeningIntegrationTests(unittest.TestCase):
    def test_improver_screening_method(self) -> None:
        """SelfImprover._screen_tasks prunes candidates when the list is long."""
        import tempfile
        from pathlib import Path
        from mycelium_accel.config import Config
        from mycelium_accel.runtime_profile import load_default_profile

        with tempfile.TemporaryDirectory() as temp:
            config = Config(seed=101, state_dir=str(Path(temp) / "s"))
            guard = GuardConfig(
                seeds=[101, 103, 107],
                benchmark_rounds=2,
                screen_keep_top=3,
                require_tests=False,
            )
            improver = SelfImprover(Path(temp), config, guard)
            calls = []

            def fake_run_tasks(tasks):
                # screen pass: record every task; return fast values for the
                # "fast" profile keys so screening keeps them.
                calls.append(len(tasks))
                results = []
                for task in tasks:
                    fast = "probe_train_cases" in task.profile and task.profile["probe_train_cases"] >= 99
                    results.append({
                        "seed": task.seed,
                        "profile": dict(task.profile),
                        "aggregate_variant": task.aggregate_variant,
                        "rounds_per_second": 200.0 if fast else 50.0,
                        "best_score": 3.0,
                        "best_exact_rate": 0.5,
                        "solved_by_best": 1.0,
                        "capability_signal": 3.5,
                        "frontier_difficulty": 3.0,
                        "active_niches": 5.0,
                        "diversity_entropy": 1.0,
                        "macro_transfer_mean": 0.1,
                        "frontier_learning_progress": 0.2,
                        "growth_regime": "linear",
                    })
                return results

            baseline_profile = load_default_profile()
            candidates = []
            for index in range(9):
                profile = dict(baseline_profile)
                profile["probe_train_cases"] = 99 + index  # fake fast markers
                candidates.append(("loop", profile))
            for index in range(9):
                profile = dict(baseline_profile)
                profile["probe_train_cases"] = 10 + index  # slow markers
                candidates.append(("loop", profile))

            with patch.object(improver, "_run_benchmark_tasks", side_effect=fake_run_tasks):
                survivors = improver._screen_tasks(candidates)
            self.assertEqual(len(survivors), 3)
            self.assertTrue(all(profile["probe_train_cases"] >= 99 for _, profile in survivors))


if __name__ == "__main__":
    unittest.main()
