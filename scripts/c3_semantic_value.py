#!/usr/bin/env python3
"""C3 (Roadmap): semantic operators vs random mutation, COMPUTE-MATCHED.

Each seed: baseline (semantic_rate=0) runs R rounds in wall time T; the
candidate (semantic_rate=0.55) then runs *until it has spent the same T*
(rounds adapt to cost — that IS the compute matching). Quality deltas per
seed -> BCa CI + Holm. Throughput reported as context, not as gate.

Pré-registrado: VIDA iff capability_signal Δ CI excludes 0 IN FAVOR of the
candidate with Holm p <= 0.05 (across best_score/capability/solved).
MORTE -> operators stay optional default-off (already) + docs admit it.

Usage:
    python scripts/c3_semantic_value.py --rounds 60 --out .mycelium_benchmarks/c3_report.json
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

QUALITY = ["best_score", "capability_signal", "solved_by_best"]


def run_fixed(seed: int, profile: dict, rounds: int, parent: Path) -> tuple[dict, float]:
    engine = MyceliumEngine(Config(seed=seed, state_dir=str(parent / f"s{seed}"), **profile))
    engine.init_state()
    start = time.perf_counter()
    engine.run(rounds)
    elapsed = time.perf_counter() - start
    return _final_metrics(engine), elapsed


def run_budgeted(seed: int, profile: dict, budget: float, parent: Path) -> tuple[dict, int]:
    engine = MyceliumEngine(Config(seed=seed, state_dir=str(parent / f"s{seed}"), **profile))
    engine.init_state()
    spent, rounds = 0.0, 0
    while spent < budget:
        start = time.perf_counter()
        engine.run(5)
        spent += time.perf_counter() - start
        rounds += 5
    return _final_metrics(engine), rounds


def _final_metrics(engine: MyceliumEngine) -> dict[str, float]:
    metric = engine.load_or_init_state().metrics_history[-1]
    return {k: float(metric[k]) for k in QUALITY}


def main() -> None:
    parser = argparse.ArgumentParser(description="C3 compute-matched semantic value")
    parser.add_argument("--rounds", type=int, default=60)
    parser.add_argument("--seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--semantic-rate", type=float, default=0.55)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--out", default=".mycelium_benchmarks/c3_report.json")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    for seed in seeds:
        if not is_prime(seed):
            raise SystemExit(f"Seed must be prime: {seed}")

    per_seed = []
    with tempfile.TemporaryDirectory() as tmp:
        parent = Path(tmp)
        for seed in seeds:
            base, budget = run_fixed(seed, {}, args.rounds, parent / "base")
            cand, cand_rounds = run_budgeted(
                seed, {"semantic_mutation_rate": args.semantic_rate}, budget, parent / "cand")
            per_seed.append({"seed": seed, "baseline": base, "candidate": cand,
                             "budget_s": budget, "candidate_rounds": cand_rounds,
                             "baseline_rounds": args.rounds})

    comparisons = []
    for metric in QUALITY:
        comparisons.append(compare_paired_metric(
            metric, [r["baseline"][metric] for r in per_seed],
            [r["candidate"][metric] for r in per_seed],
            direction=1, confidence=args.confidence))
    apply_correction(comparisons, method="holm")

    cap = next(c for c in comparisons if c.metric == "capability_signal")
    alive = bool(cap.ci_low > 0 and (cap.p_value_corrected or 1.0) <= args.alpha)
    report = {
        "protocol": "C3-compute-matched/Holm/Bca95",
        "baseline_rounds": args.rounds,
        "semantic_rate": args.semantic_rate,
        "seeds": seeds,
        "per_seed": per_seed,
        "comparisons": [c.to_dict() for c in comparisons],
        "verdict": "VIDA" if alive else "MORTE",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "comparisons": [{k: (round(v, 4) if isinstance(v, float) else v)
                         for k, v in c.to_dict().items()
                         if k in ("metric", "mean_delta", "ci_low", "ci_high",
                                  "p_value", "p_value_corrected", "effect_dz")} for c in comparisons],
        "mean_candidate_rounds": sum(r["candidate_rounds"] for r in per_seed) / len(per_seed),
        "report": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
