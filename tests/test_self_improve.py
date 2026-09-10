from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mycelium_accel.config import Config
from mycelium_accel.self_improve import (
    BenchmarkSnapshot,
    GuardConfig,
    SelfImprover,
    compare_snapshots,
    generate_candidate_profiles,
)


def make_snapshot(**overrides: object) -> BenchmarkSnapshot:
    payload = {
        "profile": {
            "family_count": 7,
            "family_size": 11,
            "challenges_per_round": 3,
            "train_cases": 8,
            "test_cases": 16,
            "initial_difficulty": 2,
            "max_program_depth": 5,
            "max_program_nodes": 63,
            "max_abs_value": 100000,
            "max_eval_steps": 256,
            "max_macros": 24,
            "checkpoint_every": 10,
            "state_save_every": 10,
            "probe_challenges": 2,
            "probe_train_cases": 2,
            "probe_test_cases": 4,
            "full_rescore_top_k": 4,
            "full_rescore_random_k": 1,
            "persistence_backend": "json",
            "climate_weight": 0.03,
            "novelty_weight": 0.04,
            "macro_potential_weight": 0.03,
            "transfer_weight": 0.03,
            "macro_support_threshold": 2,
            "macro_transfer_threshold": 0.12,
            "macro_retire_rounds": 12,
            "compositional_challenge_rate": 0.34,
            "niche_probe_count": 5,
            "frontier_archive_limit": 96,
            "frontier_window": 12,
            "gene_splice_rate": 0.25,
            "shrink_mutation_rate": 0.12,
        },
        "aggregate_variant": "pythonic",
        "rounds_per_second_mean": 90.0,
        "best_score_mean": 3.5,
        "best_exact_rate_mean": 0.40,
        "solved_by_best_mean": 1.0,
        "capability_signal_mean": 3.2,
        "frontier_difficulty_mean": 2.4,
        "growth_regimes": ["linear"],
        "per_seed": [],
    }
    payload.update(overrides)
    return BenchmarkSnapshot(**payload)


class SelfImproveTests(unittest.TestCase):
    def test_guard_rejects_quality_regression(self) -> None:
        baseline = make_snapshot()
        candidate = make_snapshot(rounds_per_second_mean=100.0, best_exact_rate_mean=0.39)
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=[101]))
        self.assertFalse(decision.accepted)
        self.assertTrue(any("best_exact_rate_mean" in reason for reason in decision.reasons))

    def test_guard_accepts_faster_non_regressing_candidate(self) -> None:
        baseline = make_snapshot()
        candidate = make_snapshot(
            rounds_per_second_mean=92.0,
            best_score_mean=3.7,
            best_exact_rate_mean=0.42,
            solved_by_best_mean=1.2,
            capability_signal_mean=3.3,
            frontier_difficulty_mean=2.4,
        )
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=[101]))
        self.assertTrue(decision.accepted)

    def test_candidate_generation_preserves_bounds(self) -> None:
        profile = make_snapshot().profile
        candidates = generate_candidate_profiles(profile)
        self.assertGreater(len(candidates), 1)
        backends = {candidate["persistence_backend"] for candidate in candidates}
        self.assertTrue({"json", "pickle"}.issuperset(backends))
        self.assertIn("pickle", backends)
        for candidate in candidates:
            self.assertGreaterEqual(candidate["family_count"], 5)
            self.assertGreaterEqual(candidate["family_size"], 10)
            self.assertLessEqual(candidate["probe_train_cases"], candidate["train_cases"])
            self.assertLessEqual(candidate["probe_test_cases"], candidate["test_cases"])
            self.assertLessEqual(candidate["full_rescore_top_k"], candidate["family_size"])

    def test_self_improve_writes_report_even_when_no_candidate_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            state_dir = project_root / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            improver = SelfImprover(project_root, config, GuardConfig(seeds=[101], benchmark_rounds=2, require_tests=False))
            baseline = make_snapshot()

            with patch.object(SelfImprover, "_benchmark_current_selection", return_value=baseline), patch.object(
                SelfImprover,
                "_search_best_candidate",
                return_value=None,
            ):
                summary = improver.run(cycles=1, rounds_per_cycle=1)

            self.assertEqual(summary.cycles_completed, 1)
            self.assertEqual(summary.rejected_cycles, 1)
            self.assertTrue(Path(summary.report_path).exists())

    def test_daemon_status_echoes_time_budget_mid_cycle(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            state_dir = project_root / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            improver = SelfImprover(project_root, config, GuardConfig(seeds=[101], benchmark_rounds=2, require_tests=False))
            baseline = make_snapshot()
            seen: dict[str, object] = {}

            def _spy(_baseline: object) -> None:
                payload = json.loads((project_root / ".mycelium_self_improve" / "daemon.status.json").read_text())
                seen["phase"] = payload.get("phase")
                seen["budget"] = payload.get("time_budget_seconds")
                return None

            with patch.object(SelfImprover, "_benchmark_current_selection", return_value=baseline), patch.object(
                SelfImprover, "_search_best_candidate", side_effect=_spy
            ):
                improver.run(cycles=1, rounds_per_cycle=1, time_budget_seconds=777)

            self.assertEqual(seen.get("phase"), "search_candidate")
            self.assertEqual(seen.get("budget"), 777)

    def test_self_improve_respects_time_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            state_dir = project_root / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            improver = SelfImprover(project_root, config, GuardConfig(seeds=[101], benchmark_rounds=2, require_tests=False))
            summary = improver.run(cycles=5, rounds_per_cycle=1, time_budget_seconds=0)
            self.assertEqual(summary.cycles_completed, 0)
            self.assertTrue(summary.stopped_by_time_budget)

    def test_self_improve_daemon_writes_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            state_dir = project_root / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            improver = SelfImprover(project_root, config, GuardConfig(seeds=[101], benchmark_rounds=2, require_tests=False))
            baseline = make_snapshot()

            with patch.object(SelfImprover, "_benchmark_current_selection", return_value=baseline), patch.object(
                SelfImprover,
                "_search_best_candidate",
                return_value=None,
            ):
                summary = improver.run_daemon(rounds_per_cycle=1, max_cycles=1)

            self.assertEqual(summary.cycles_completed, 1)
            self.assertTrue((project_root / ".mycelium_self_improve" / "daemon.status.json").exists())

    def test_self_improve_writes_last_error_and_error_status_on_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            state_dir = project_root / "state"
            config = Config(seed=101, state_dir=str(state_dir), family_count=5, family_size=10)
            improver = SelfImprover(project_root, config, GuardConfig(seeds=[101], benchmark_rounds=2, require_tests=False))

            with patch.object(SelfImprover, "_run_single_cycle", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    improver.run_daemon(rounds_per_cycle=1, max_cycles=1)

            error_path = project_root / ".mycelium_self_improve" / "last_error.json"
            status_path = project_root / ".mycelium_self_improve" / "daemon.status.json"
            self.assertTrue(error_path.exists())
            self.assertTrue(status_path.exists())
            self.assertIn('"error_message": "boom"', error_path.read_text(encoding="utf-8"))
            self.assertIn('"state": "error"', status_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
