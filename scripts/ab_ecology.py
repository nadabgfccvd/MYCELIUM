#!/usr/bin/env python3
"""C1 A/B (Roadmap): engine+ecologia vs baseline, pareado por seed.

Arms:
  - baseline: flags C1 desligadas
  - ecology:  anti_forgetting + ecology_reseed_rounds=12 + adaptive_novelty

Pré-registrado (roadmap §C1):
  VIDA  iff regression_rate(ecology) < 0.35 AND final-window slope(ecology) >= 0
  MORTE caso contrário → CHANGES + horas voltam para B2/B4.

Métricas via growth_metrics.build_dashboard sobre o histórico completo
(telemetria durável F1). Escala desta sessão: --rounds/seed (default 150);
escala canônica do roadmap: 2×(4 fatias de 25 min) — mesmo script, ver DOCS.

Uso:
    python scripts/ab_ecology.py --rounds 150 --out .mycelium_benchmarks/ab_ecology.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.config import Config  # noqa: E402
from mycelium_accel.engine import MyceliumEngine  # noqa: E402
from mycelium_accel.growth_metrics import build_dashboard  # noqa: E402
from mycelium_accel.prime import is_prime  # noqa: E402
from mycelium_accel.telemetry import read_metrics  # noqa: E402

ECOLOGY_PROFILE = {
    "anti_forgetting": True,
    "ecology_reseed_rounds": 12,
    "ecology_patience": 8,
    "adaptive_novelty": True,
}


def run_arm(seed: int, profile: dict, rounds: int, parent: Path, tag: str) -> dict:
    state_dir = parent / f"{tag}-{seed}"
    engine = MyceliumEngine(Config(seed=seed, state_dir=str(state_dir), **profile))
    engine.init_state()
    summary = engine.run(rounds)
    history = read_metrics(state_dir) or engine.load_or_init_state().metrics_history
    dashboard = build_dashboard(history)
    injections = sum(int(m.get("ecology_injections", 0)) for m in history)
    reseeds = sum(int(m.get("ecology_reseeds", 0)) for m in history)
    return {
        "seed": seed,
        "rounds": rounds,
        "regression_rate": dashboard.regression_rate,
        "final_slope": dashboard.cumulative_slope,
        "curvature": dashboard.cumulative_curvature,
        "regime": dashboard.regime,
        "capability_end": float(history[-1].get("capability_signal", 0.0)) if history else 0.0,
        "capability_max": max((float(m.get("capability_signal", 0.0)) for m in history), default=0.0),
        "injections": injections,
        "reseeds": reseeds,
        "growth_regime": summary.growth_regime,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="C1 paired A/B: ecology vs baseline")
    parser.add_argument("--rounds", type=int, default=150)
    parser.add_argument("--seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--out", default=".mycelium_benchmarks/ab_ecology.json")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    for seed in seeds:
        if not is_prime(seed):
            raise SystemExit(f"Seed must be prime: {seed}")

    with tempfile.TemporaryDirectory() as temp_dir:
        parent = Path(temp_dir)
        base_rows = [run_arm(s, {}, args.rounds, parent, "base") for s in seeds]
        eco_rows = [run_arm(s, ECOLOGY_PROFILE, args.rounds, parent, "eco") for s in seeds]

    def mean(rows: list[dict], key: str) -> float:
        return sum(r[key] for r in rows) / len(rows)

    eco_reg = mean(eco_rows, "regression_rate")
    eco_slope = mean(eco_rows, "final_slope")
    alive = bool(eco_reg < 0.35 and eco_slope >= 0)

    report = {
        "protocol": "C1-paired-AB",
        "rounds_per_seed": args.rounds,
        "seeds": seeds,
        "ecology_profile": ECOLOGY_PROFILE,
        "kill_criteria": "VIDA iff regression_rate < 0.35 AND final_slope >= 0 (ecology arm)",
        "baseline": {"rows": base_rows, "mean_regression": mean(base_rows, "regression_rate"),
                     "mean_slope": mean(base_rows, "final_slope")},
        "ecology": {"rows": eco_rows, "mean_regression": eco_reg, "mean_slope": eco_slope},
        "verdict": "VIDA" if alive else "MORTE",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "baseline": {"mean_regression": round(mean(base_rows, "regression_rate"), 3),
                     "mean_slope": round(mean(base_rows, "final_slope"), 4)},
        "ecology": {"mean_regression": round(eco_reg, 3), "mean_slope": round(eco_slope, 4),
                    "injections": sum(r["injections"] for r in eco_rows),
                    "reseeds": sum(r["reseeds"] for r in eco_rows)},
        "report": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
