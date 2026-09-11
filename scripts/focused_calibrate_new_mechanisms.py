from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import mycelium_accel.self_improve as self_improve_module
from mycelium_accel.config import Config
from mycelium_accel.runtime_profile import load_default_profile
from mycelium_accel.self_improve import GuardConfig, SelfImprover, compare_snapshots


def focused_generate_candidate_profiles(current: dict[str, object]) -> list[dict[str, object]]:
    novelty_weight = float(current.get("novelty_weight", 0.04))
    macro_potential_weight = float(current.get("macro_potential_weight", 0.03))
    transfer_weight = float(current.get("transfer_weight", 0.03))
    macro_support_threshold = int(current.get("macro_support_threshold", 2))
    macro_transfer_threshold = float(current.get("macro_transfer_threshold", 0.12))
    macro_retire_rounds = int(current.get("macro_retire_rounds", 12))
    compositional_challenge_rate = float(current.get("compositional_challenge_rate", 0.34))
    niche_probe_count = int(current.get("niche_probe_count", 5))
    frontier_archive_limit = int(current.get("frontier_archive_limit", 96))
    frontier_window = int(current.get("frontier_window", 12))
    gene_splice_rate = float(current.get("gene_splice_rate", 0.25))
    shrink_mutation_rate = float(current.get("shrink_mutation_rate", 0.12))
    challenges_per_round = int(current.get("challenges_per_round", 3))

    candidate_specs = [
        {},
        {"novelty_weight": max(0.0, novelty_weight - 0.01)},
        {"novelty_weight": novelty_weight + 0.01},
        {"macro_potential_weight": max(0.0, macro_potential_weight - 0.01)},
        {"macro_potential_weight": macro_potential_weight + 0.01},
        {"transfer_weight": max(0.0, transfer_weight - 0.01)},
        {"transfer_weight": transfer_weight + 0.01},
        {"macro_support_threshold": max(1, macro_support_threshold - 1)},
        {"macro_support_threshold": macro_support_threshold + 1},
        {"macro_transfer_threshold": max(0.0, macro_transfer_threshold - 0.03)},
        {"macro_transfer_threshold": macro_transfer_threshold + 0.03},
        {"macro_retire_rounds": max(1, macro_retire_rounds - 4)},
        {"macro_retire_rounds": macro_retire_rounds + 4},
        {"compositional_challenge_rate": max(0.0, compositional_challenge_rate - 0.10)},
        {"compositional_challenge_rate": min(1.0, compositional_challenge_rate + 0.10)},
        {"niche_probe_count": max(3, niche_probe_count - 1)},
        {"niche_probe_count": niche_probe_count + 2},
        {"frontier_archive_limit": max(challenges_per_round, frontier_archive_limit - 24)},
        {"frontier_archive_limit": frontier_archive_limit + 24},
        {"frontier_window": max(3, frontier_window - 3)},
        {"frontier_window": frontier_window + 3},
        {"gene_splice_rate": max(0.0, gene_splice_rate - 0.05)},
        {"gene_splice_rate": min(1.0, gene_splice_rate + 0.05)},
        {"shrink_mutation_rate": max(0.0, shrink_mutation_rate - 0.04)},
        {"shrink_mutation_rate": min(1.0, shrink_mutation_rate + 0.04)},
        {
            "novelty_weight": novelty_weight + 0.01,
            "transfer_weight": transfer_weight + 0.01,
            "compositional_challenge_rate": min(1.0, compositional_challenge_rate + 0.10),
        },
        {
            "macro_support_threshold": max(1, macro_support_threshold - 1),
            "macro_transfer_threshold": max(0.0, macro_transfer_threshold - 0.03),
            "macro_retire_rounds": macro_retire_rounds + 4,
        },
        {
            "gene_splice_rate": min(1.0, gene_splice_rate + 0.05),
            "shrink_mutation_rate": max(0.0, shrink_mutation_rate - 0.04),
            "compositional_challenge_rate": min(1.0, compositional_challenge_rate + 0.10),
        },
        {
            "niche_probe_count": niche_probe_count + 2,
            "frontier_window": frontier_window + 3,
            "novelty_weight": novelty_weight + 0.01,
        },
    ]

    def normalize(profile: dict[str, object]) -> dict[str, object]:
        profile = dict(profile)
        profile["novelty_weight"] = max(0.0, float(profile.get("novelty_weight", 0.04)))
        profile["macro_potential_weight"] = max(0.0, float(profile.get("macro_potential_weight", 0.03)))
        profile["transfer_weight"] = max(0.0, float(profile.get("transfer_weight", 0.03)))
        profile["macro_support_threshold"] = max(1, int(profile.get("macro_support_threshold", 2)))
        profile["macro_transfer_threshold"] = max(0.0, float(profile.get("macro_transfer_threshold", 0.12)))
        profile["macro_retire_rounds"] = max(1, int(profile.get("macro_retire_rounds", 12)))
        profile["compositional_challenge_rate"] = min(1.0, max(0.0, float(profile.get("compositional_challenge_rate", 0.34))))
        profile["niche_probe_count"] = max(3, int(profile.get("niche_probe_count", 5)))
        profile["frontier_archive_limit"] = max(int(profile.get("challenges_per_round", 3)), int(profile.get("frontier_archive_limit", 96)))
        profile["frontier_window"] = max(3, int(profile.get("frontier_window", 12)))
        profile["gene_splice_rate"] = min(1.0, max(0.0, float(profile.get("gene_splice_rate", 0.25))))
        profile["shrink_mutation_rate"] = min(1.0, max(0.0, float(profile.get("shrink_mutation_rate", 0.12))))
        return profile

    seen: set[tuple[tuple[str, object], ...]] = set()
    candidates: list[dict[str, object]] = []
    for overrides in candidate_specs:
        profile = dict(current)
        profile.update(overrides)
        profile = normalize(profile)
        key = tuple(sorted(profile.items()))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(profile)
    return candidates


def mechanism_utility(baseline: self_improve_module.BenchmarkSnapshot, candidate: self_improve_module.BenchmarkSnapshot) -> float:
    return (
        12.0 * (candidate.frontier_learning_progress_mean - baseline.frontier_learning_progress_mean)
        + 5.0 * (candidate.macro_transfer_mean - baseline.macro_transfer_mean)
        + 0.04 * (candidate.active_niches_mean - baseline.active_niches_mean)
        + 0.20 * (candidate.diversity_entropy_mean - baseline.diversity_entropy_mean)
        + 1.25 * (candidate.capability_signal_mean - baseline.capability_signal_mean)
        + 0.60 * (candidate.frontier_difficulty_mean - baseline.frontier_difficulty_mean)
        + 0.40 * (candidate.best_score_mean - baseline.best_score_mean)
        + 0.05 * (candidate.best_exact_rate_mean - baseline.best_exact_rate_mean)
        + 0.01 * (candidate.rounds_per_second_mean - baseline.rounds_per_second_mean)
    )


class FocusedMechanismImprover(SelfImprover):
    def _search_best_candidate(self, baseline: self_improve_module.BenchmarkSnapshot):
        tasks = []
        seen: set[tuple[str, tuple[tuple[str, object], ...]]] = set()
        current_profile = baseline.profile
        current_variant = baseline.aggregate_variant

        for profile in focused_generate_candidate_profiles(current_profile):
            key = (current_variant, tuple(sorted(profile.items())))
            if key in seen:
                continue
            seen.add(key)
            if profile == current_profile:
                continue
            tasks.append((current_variant, profile))

        snapshots = self._benchmark_candidates_parallel(tasks)
        accepted: list[self_improve_module.BenchmarkSnapshot] = []
        for snapshot in snapshots:
            decision = compare_snapshots(baseline, snapshot, self.guard)
            if decision.accepted:
                accepted.append(snapshot)
        if not accepted:
            return None
        return max(
            accepted,
            key=lambda snapshot: (
                mechanism_utility(baseline, snapshot),
                snapshot.capability_signal_mean,
                snapshot.frontier_learning_progress_mean,
                snapshot.macro_transfer_mean,
                snapshot.rounds_per_second_mean,
            ),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Focused calibration of new MYCELIUM Auto-evolve mechanisms")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--state-dir", default=str(PROJECT_ROOT / ".mycelium_state"))
    parser.add_argument("--rounds-per-cycle", type=int, default=15)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--time-budget-seconds", type=int, default=28800)
    parser.add_argument("--benchmark-rounds", type=int, default=30)
    parser.add_argument("--benchmark-seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--guard-workers", type=int, default=4)
    parser.add_argument("--min-speedup-ratio", type=float, default=0.0)
    parser.add_argument("--max-best-score-drop", type=float, default=0.0)
    parser.add_argument("--max-exact-rate-drop", type=float, default=0.0)
    parser.add_argument("--max-solved-drop", type=float, default=0.0)
    parser.add_argument("--max-capability-drop", type=float, default=0.0)
    parser.add_argument("--max-frontier-drop", type=float, default=0.35)
    parser.add_argument("--skip-tests", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    profile = load_default_profile()
    config = Config(seed=args.seed, state_dir=args.state_dir, **profile)
    seeds = [int(item.strip()) for item in str(args.benchmark_seeds).split(",") if item.strip()]
    guard = GuardConfig(
        seeds=seeds,
        benchmark_rounds=args.benchmark_rounds,
        min_speedup_ratio=args.min_speedup_ratio,
        max_best_score_drop=args.max_best_score_drop,
        max_exact_rate_drop=args.max_exact_rate_drop,
        max_solved_drop=args.max_solved_drop,
        max_capability_drop=args.max_capability_drop,
        max_frontier_drop=args.max_frontier_drop,
        require_tests=not args.skip_tests,
        parallel_workers=max(1, int(args.guard_workers)),
    )
    self_improve_module.generate_candidate_profiles = focused_generate_candidate_profiles
    improver = FocusedMechanismImprover(project_root, config, guard)
    startup = {
        "mode": "focused_new_mechanisms_calibration",
        "project_root": str(project_root),
        "state_dir": args.state_dir,
        "rounds_per_cycle": args.rounds_per_cycle,
        "time_budget_seconds": args.time_budget_seconds,
        "max_cycles": args.max_cycles,
        "benchmark_rounds": args.benchmark_rounds,
        "benchmark_seeds": seeds,
        "guard_workers": guard.parallel_workers,
        "min_speedup_ratio": guard.min_speedup_ratio,
        "focused_keys": [
            "novelty_weight",
            "macro_potential_weight",
            "transfer_weight",
            "macro_support_threshold",
            "macro_transfer_threshold",
            "macro_retire_rounds",
            "compositional_challenge_rate",
            "niche_probe_count",
            "frontier_archive_limit",
            "frontier_window",
            "gene_splice_rate",
            "shrink_mutation_rate",
        ],
        "default_profile": profile,
    }
    print(json.dumps(startup), flush=True)
    summary = improver.run_daemon(
        args.rounds_per_cycle,
        time_budget_seconds=args.time_budget_seconds,
        sleep_seconds=args.sleep_seconds,
        max_cycles=args.max_cycles,
    )
    print(json.dumps(summary.to_dict(), indent=2), flush=True)


if __name__ == "__main__":
    main()
