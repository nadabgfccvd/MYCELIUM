from __future__ import annotations

import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.runtime_profile import load_default_profile
from mycelium_accel.state import load_state

SEEDS = [101, 103, 107, 109, 113]
PROFILES = {
    "quality_reference": {
        "family_count": 9,
        "family_size": 15,
        "challenges_per_round": 3,
        "train_cases": 8,
        "test_cases": 16,
        "checkpoint_every": 10,
        "state_save_every": 10,
        "probe_challenges": 2,
        "probe_train_cases": 3,
        "probe_test_cases": 6,
        "full_rescore_top_k": 6,
        "full_rescore_random_k": 1,
    },
    "default": load_default_profile(),
}


def run_profile(name: str, profile: dict[str, int]) -> dict[str, object]:
    rounds_per_second: list[float] = []
    best_scores: list[float] = []
    frontier_difficulties: list[int] = []
    exact_rates: list[float] = []
    solved_counts: list[int] = []
    capability_signals: list[float] = []
    active_niches: list[int] = []
    diversity_entropies: list[float] = []
    macro_transfer_means: list[float] = []
    frontier_progress_values: list[float] = []
    regimes: list[str] = []

    for seed in SEEDS:
        temp_dir = tempfile.mkdtemp(prefix="mycelium-quality-")
        try:
            state_dir = Path(temp_dir) / "state"
            config = Config(seed=seed, state_dir=str(state_dir), **profile)
            engine = MyceliumEngine(config)
            engine.init_state()
            started = time.perf_counter()
            summary = engine.run(30)
            elapsed = time.perf_counter() - started
            state = load_state(state_dir)
            metric = state.metrics_history[-1]
            rounds_per_second.append(summary.rounds_executed / elapsed)
            best_scores.append(metric["best_score"])
            frontier_difficulties.append(metric["frontier_difficulty"])
            exact_rates.append(metric["best_exact_rate"])
            solved_counts.append(metric["solved_by_best"])
            capability_signals.append(metric["capability_signal"])
            active_niches.append(metric.get("active_niches", 0))
            diversity_entropies.append(metric.get("diversity_entropy", 0.0))
            macro_transfer_means.append(metric.get("macro_transfer_mean", 0.0))
            frontier_progress_values.append(metric.get("frontier_learning_progress", 0.0))
            regimes.append(summary.growth_regime)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "profile": name,
        "seeds": SEEDS,
        "rounds_per_second_mean": statistics.mean(rounds_per_second),
        "best_score_mean": statistics.mean(best_scores),
        "frontier_difficulty_mean": statistics.mean(frontier_difficulties),
        "best_exact_rate_mean": statistics.mean(exact_rates),
        "solved_by_best_mean": statistics.mean(solved_counts),
        "capability_signal_mean": statistics.mean(capability_signals),
        "active_niches_mean": statistics.mean(active_niches),
        "diversity_entropy_mean": statistics.mean(diversity_entropies),
        "macro_transfer_mean": statistics.mean(macro_transfer_means),
        "frontier_learning_progress_mean": statistics.mean(frontier_progress_values),
        "growth_regimes": regimes,
    }


def main() -> None:
    results = [run_profile(name, profile) for name, profile in PROFILES.items()]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
