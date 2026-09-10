#!/usr/bin/env python3
"""Paired baseline-vs-candidate benchmark with full statistical report (Phase 2).

Runs the MYCELIUM Auto-evolve engine for two profiles over *the same prime seeds*,
then reports per-seed deltas, BCa confidence intervals, sign-flip
permutation p-values (with correction) and effect sizes for every guard
metric — the acceptance report format the roadmap requires.

Usage:
    python scripts/benchmark_paired.py --rounds 12 --seeds 101,103,107,109,113
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.config import Config
from mycelium_accel.engine import MyceliumEngine
from mycelium_accel.prime import is_prime
from mycelium_accel.stats import apply_correction, compare_paired_metric

GUARD_METRICS = [
    ("rounds_per_second", 1),
    ("best_score", 1),
    ("best_exact_rate", 1),
    ("solved_by_best", 1),
    ("capability_signal", 1),
    ("frontier_difficulty", 1),
]


def run_profile(seed: int, profile: dict, rounds: int, state_parent: Path) -> dict[str, float]:
    state_dir = state_parent / f"state-{seed}-{abs(hash(json.dumps(profile, sort_keys=True))) % 10**8}"
    config = Config(seed=seed, state_dir=str(state_dir), **profile)
    engine = MyceliumEngine(config)
    engine.init_state()
    started = time.perf_counter()
    summary = engine.run(rounds)
    elapsed = time.perf_counter() - started
    state = engine.load_or_init_state()
    metric = state.metrics_history[-1]
    return {
        "rounds_per_second": summary.rounds_executed / max(elapsed, 1e-9),
        "best_score": float(metric["best_score"]),
        "best_exact_rate": float(metric["best_exact_rate"]),
        "solved_by_best": float(metric["solved_by_best"]),
        "capability_signal": float(metric["capability_signal"]),
        "frontier_difficulty": float(metric["frontier_difficulty"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired MYCELIUM Auto-evolve benchmark with BCa CI + permutation tests")
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--candidate-semantic-rate", type=float, default=0.55)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--correction", choices=["holm", "bh", "none"], default="holm")
    parser.add_argument("--out", default=".mycelium_benchmarks/paired_engine_report.json")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    for seed in seeds:
        if not is_prime(seed):
            raise SystemExit(f"Seed must be prime per project constraint: {seed}")

    baseline_profile: dict = {}
    candidate_profile: dict = {"semantic_mutation_rate": args.candidate_semantic_rate}

    per_seed_rows: list[dict] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        state_parent = Path(temp_dir)
        for seed in seeds:
            baseline = run_profile(seed, baseline_profile, args.rounds, state_parent / "baseline")
            candidate = run_profile(seed, candidate_profile, args.rounds, state_parent / "candidate")
            per_seed_rows.append({"seed": seed, "baseline": baseline, "candidate": candidate})

    comparisons = []
    for metric, direction in GUARD_METRICS:
        base_col = [row["baseline"][metric] for row in per_seed_rows]
        cand_col = [row["candidate"][metric] for row in per_seed_rows]
        comparison = compare_paired_metric(
            metric, base_col, cand_col, direction=direction, confidence=args.confidence,
        )
        comparisons.append(comparison)
    apply_correction(comparisons, method=args.correction)

    report = {
        "protocol": "paired-multi-seed/BCa-bootstrap/sign-flip-permutation",
        "rounds_per_seed": args.rounds,
        "seeds": seeds,
        "candidate_profile": candidate_profile,
        "confidence": args.confidence,
        "alpha": args.alpha,
        "correction": args.correction,
        "per_seed": per_seed_rows,
        "comparisons": [comparison.to_dict() for comparison in comparisons],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(out_path),
        "comparisons": [
            {
                "metric": c.metric,
                "mean_delta": round(c.mean_delta, 5),
                "ci": [round(c.ci_low, 5), round(c.ci_high, 5)],
                "p": round(c.p_value, 4),
                "p_corrected": round(c.p_value_corrected, 4) if c.p_value_corrected else None,
                "effect_dz": round(c.effect_dz, 3),
            }
            for c in comparisons
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
