#!/usr/bin/env python3
"""EC1 dogfooding (Roadmap B2): accelerate the engine itself, paired guard.

Compares the default engine profile against throughput-oriented candidate
profiles over the SAME prime seeds, then applies the product acceptance rule:
  - throughput: mean gain >= 10% AND 95% BCa CI excludes 0 AND Holm p <= 0.05
  - quality: no metric regresses (95% CI lower bound >= -tolerance)
A negative (honest) verdict is also a valid delivery (ADR-negative counts).

Profiles under test (throughput hypotheses):
  - pickle_backend: persistence_backend=pickle (less ser/de overhead)
  - light_probes:  smaller probe/rescore budgets (less eval work)
  - lazy_persist:  state_save_every/checkpoint_every raised (less IO)

Usage:
    python scripts/ec1_dogfood.py --rounds 30 --out .mycelium_benchmarks/ec1_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.config import Config  # noqa: E402
from mycelium_accel.engine import MyceliumEngine  # noqa: E402
from mycelium_accel.prime import is_prime  # noqa: E402
from mycelium_accel.stats import apply_correction, compare_paired_metric  # noqa: E402

THROUGHPUT_METRIC = "rounds_per_second"
QUALITY_METRICS = ["best_score", "best_exact_rate", "solved_by_best", "capability_signal"]

CANDIDATES: dict[str, dict] = {
    "pickle_backend": {"persistence_backend": "pickle"},
    "light_probes": {
        "probe_train_cases": 2,
        "probe_test_cases": 4,
        "full_rescore_top_k": 4,
        "full_rescore_random_k": 1,
    },
    "lazy_persist": {"state_save_every": 10, "checkpoint_every": 20},
}


def run_profile(seed: int, profile: dict, rounds: int, state_parent: Path) -> dict[str, float]:
    tag = abs(hash(json.dumps(profile, sort_keys=True))) % 10**8
    state_dir = state_parent / f"state-{seed}-{tag}"
    config = Config(seed=seed, state_dir=str(state_dir), **profile)
    engine = MyceliumEngine(config)
    engine.init_state()
    started = time.perf_counter()
    summary = engine.run(rounds)
    elapsed = time.perf_counter() - started
    state = engine.load_or_init_state()
    metric = state.metrics_history[-1]
    return {
        THROUGHPUT_METRIC: summary.rounds_executed / max(elapsed, 1e-9),
        "best_score": float(metric["best_score"]),
        "best_exact_rate": float(metric["best_exact_rate"]),
        "solved_by_best": float(metric["solved_by_best"]),
        "capability_signal": float(metric["capability_signal"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="EC1 dogfooding: paired engine speedups")
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--min-gain", type=float, default=0.10, help="min throughput gain (fraction)")
    parser.add_argument("--quality-tol", type=float, default=0.0, help="max quality CI-low drop tolerated")
    parser.add_argument("--out", default=".mycelium_benchmarks/ec1_report.json")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    for seed in seeds:
        if not is_prime(seed):
            raise SystemExit(f"Seed must be prime per project constraint: {seed}")

    with tempfile.TemporaryDirectory() as temp_dir:
        parent = Path(temp_dir)
        baselines = {seed: run_profile(seed, {}, args.rounds, parent / "baseline") for seed in seeds}
        per_candidate: dict[str, dict] = {}
        for name, profile in CANDIDATES.items():
            per_candidate[name] = {
                seed: run_profile(seed, profile, args.rounds, parent / name) for seed in seeds
            }

    all_comparisons = []
    verdicts: dict[str, dict] = {}
    for name, cand in per_candidate.items():
        base_col = [baselines[s][THROUGHPUT_METRIC] for s in seeds]
        cand_col = [cand[s][THROUGHPUT_METRIC] for s in seeds]
        thr = compare_paired_metric(THROUGHPUT_METRIC, base_col, cand_col, direction=1,
                                    confidence=args.confidence)
        all_comparisons.append(thr)
        quals = []
        for metric in QUALITY_METRICS:
            q = compare_paired_metric(metric,
                                      [baselines[s][metric] for s in seeds],
                                      [cand[s][metric] for s in seeds],
                                      direction=1, confidence=args.confidence)
            quals.append(q)
        verdicts[name] = {"throughput": thr, "quality": quals,
                          "mean_baseline_rps": sum(base_col) / len(base_col),
                          "mean_candidate_rps": sum(cand_col) / len(cand_col)}

    apply_correction(all_comparisons, method="holm")

    results = []
    for name, verdict in verdicts.items():
        thr = verdict["throughput"]
        gain = (verdict["mean_candidate_rps"] - verdict["mean_baseline_rps"]) / verdict["mean_baseline_rps"]
        thr_pass = (gain >= args.min_gain and thr.ci_low > 0
                    and (thr.p_value_corrected or 1.0) <= args.alpha)
        qual_pass = all(q.ci_low >= -args.quality_tol for q in verdict["quality"])
        accepted = bool(thr_pass and qual_pass)
        results.append({
            "candidate": name,
            "mean_gain": gain,
            "throughput": thr.to_dict(),
            "quality": [q.to_dict() for q in verdict["quality"]],
            "throughput_pass": thr_pass,
            "quality_pass": qual_pass,
            "accepted": accepted,
        })

    report = {
        "protocol": "EC1-paired/Holm/Bca95",
        "rounds_per_seed": args.rounds,
        "seeds": seeds,
        "min_gain": args.min_gain,
        "candidates": list(CANDIDATES),
        "per_seed": {
            str(seed): {"baseline": baselines[seed],
                        **{n: per_candidate[n][seed] for n in per_candidate}}
            for seed in seeds
        },
        "results": results,
        "verdict": next((r["candidate"] for r in results if r["accepted"]),
                        None),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(out),
        "verdict": report["verdict"],
        "results": [{k: r[k] for k in ("candidate", "mean_gain", "throughput_pass", "quality_pass", "accepted")} for r in results],
    }, indent=2))


if __name__ == "__main__":
    main()
