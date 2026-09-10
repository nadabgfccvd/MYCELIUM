from __future__ import annotations

import unittest

from mycelium_accel.self_improve import BenchmarkSnapshot, GuardConfig, compare_snapshots


def _row(seed: int, **overrides):
    row = {
        "seed": seed,
        "rounds_per_second": 100.0,
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
    row.update(overrides)
    return row


def _snapshot(seeds, row_factory, **mean_overrides):
    per_seed = [row_factory(seed) for seed in seeds]
    means = {
        key: sum(row[key] for row in per_seed) / len(per_seed)
        for key in (
            "rounds_per_second", "best_score", "best_exact_rate",
            "solved_by_best", "capability_signal", "frontier_difficulty",
        )
    }
    return BenchmarkSnapshot(
        profile={},
        aggregate_variant="loop",
        rounds_per_second_mean=means["rounds_per_second"],
        best_score_mean=means["best_score"],
        best_exact_rate_mean=means["best_exact_rate"],
        solved_by_best_mean=means["solved_by_best"],
        capability_signal_mean=means["capability_signal"],
        frontier_difficulty_mean=means["frontier_difficulty"],
        growth_regimes=["linear"] * len(per_seed),
        per_seed=per_seed,
    )


SEEDS = [101, 103, 107, 109, 113, 127, 131]


class PairedGuardTests(unittest.TestCase):
    def test_accepts_clear_speedup_with_paired_stats(self) -> None:
        baseline = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=100.0))
        candidate = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=115.0,))
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=SEEDS))
        self.assertTrue(decision.accepted, msg=" | ".join(decision.reasons))
        self.assertTrue(any("Paired statistics" in reason for reason in decision.reasons))
        self.assertTrue(decision.paired_stats)

    def test_rejects_noise_only_candidate(self) -> None:
        baseline = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=100.0 + (seed % 3)))
        wiggle = {101: 101.0, 103: 99.0, 107: 101.0, 109: 99.0, 113: 100.5, 127: 99.5, 131: 100.0}
        candidate = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=wiggle[seed]))
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=SEEDS))
        self.assertFalse(decision.accepted)

    def test_rejects_hidden_regression_unseen_by_means(self) -> None:
        # means look fine but per-seed deltas show consistent small regression
        baseline = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=100.0, best_exact_rate=0.400))
        candidate = _snapshot(
            SEEDS,
            lambda seed: _row(seed, rounds_per_second=112.0, best_exact_rate=0.39999),
        )
        guard = GuardConfig(seeds=SEEDS, max_exact_rate_drop=0.0)
        decision = compare_snapshots(baseline, candidate, guard)
        # tiny consistent regression on every seed → CI strictly negative → reject
        self.assertFalse(decision.accepted)

    def test_falls_back_to_fixed_thresholds_without_pairs(self) -> None:
        baseline = _snapshot(SEEDS, lambda seed: _row(seed))
        candidate = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=120.0))
        candidate.per_seed = []
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=SEEDS))
        self.assertTrue(decision.accepted)
        self.assertFalse(decision.paired_stats)

    def test_no_paired_stats_flag_disables_layer(self) -> None:
        baseline = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=100.0))
        baseline.per_seed = baseline.per_seed[:1]  # thin
        candidate = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=120.0))
        candidate.per_seed = candidate.per_seed[:1]
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=SEEDS))
        self.assertFalse(decision.paired_stats)

    def test_stats_payload_contains_ci_and_pvalues(self) -> None:
        baseline = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=100.0))
        candidate = _snapshot(SEEDS, lambda seed: _row(seed, rounds_per_second=110.0))
        decision = compare_snapshots(baseline, candidate, GuardConfig(seeds=SEEDS))
        names = {entry["metric"] for entry in decision.paired_stats}
        self.assertIn("relative_speedup", names)
        self.assertIn("best_exact_rate", names)
        for entry in decision.paired_stats:
            self.assertIn("ci_low", entry)
            self.assertIn("p_value", entry)
            self.assertIn("effect_dz", entry)


if __name__ == "__main__":
    unittest.main()
