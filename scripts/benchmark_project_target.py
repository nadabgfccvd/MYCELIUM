#!/usr/bin/env python3
"""Drive a generic project target through the Phase-1 harness (Phase 1 + 2).

    python scripts/benchmark_project_target.py /path/to/project \
        [--manifest mycelium.target.json] [--no-apply]

Works with any manifest-driven directory: prepares, builds, tests, and
benchmarks baseline + variants under paired prime seeds, then applies the
statistically-established winner (with full rollback on failure).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.accelerate_generic import accelerate_target
from mycelium_accel.prime import is_prime


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic MYCELIUM Auto-evolve project accelerator harness")
    parser.add_argument("target", type=Path, help="project directory (with mycelium.target.json or detectable convention)")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--seeds", default="101,103,107,109,113,127,131")
    parser.add_argument("--no-apply", action="store_true")
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--correction", choices=["holm", "bh", "none"], default="holm")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    if not all(is_prime(seed) for seed in seeds):
        raise SystemExit("All seeds must be prime per project constraint.")

    from mycelium_accel.stats import AcceptancePolicy

    policy = AcceptancePolicy(confidence=args.confidence, alpha=args.alpha, correction=args.correction)
    outcome = accelerate_target(
        args.target,
        manifest_path=args.manifest,
        seeds=seeds,
        apply=not args.no_apply,
        policy=policy,
    )
    print(json.dumps(outcome.to_dict(), indent=2))


if __name__ == "__main__":
    main()
