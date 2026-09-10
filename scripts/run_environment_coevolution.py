#!/usr/bin/env python3
"""Phase 7 experiment: coevolve a population of challenge environments with
a small GP solver population, with cross-transfer trials and a curriculum
graph (POET-style).

    python scripts/run_environment_coevolution.py --rounds 30 --seed 101
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.challenge import ChallengeFactory
from mycelium_accel.dsl import Node, compile_program, mutate, random_tree
from mycelium_accel.environment_ecology import (
    EnvironmentEcology,
    EnvironmentGenome,
    run_cross_transfer_trials,
)
from mycelium_accel.prime import next_prime

MAX_NODES = 63
MAX_ABS = 100_000
MAX_STEPS = 256


def build_challenge(factory: ChallengeFactory, genome: EnvironmentGenome):
    return factory.build(
        genome.seed,
        genome.difficulty,
        force_compositional=genome.compositional_bias > 0.5,
    )


def score_solver(genome_tree: Node, challenge) -> tuple[float, bool]:
    try:
        executor = compile_program(genome_tree, {}, max_nodes=MAX_NODES, max_abs_value=MAX_ABS, max_steps=MAX_STEPS)
    except Exception:
        return 0.0, False
    exact = 0
    total = 0
    soft = 0.0
    for x, expected in challenge.train_pairs + challenge.test_pairs:
        try:
            predicted = executor.run(x)
        except Exception:
            continue
        total += 1
        error = abs(predicted - expected)
        soft += 1.0 / (1.0 + error)
        if error == 0:
            exact += 1
    if total == 0:
        return 0.0, False
    accuracy = exact / total
    score = 0.7 * accuracy + 0.3 * (soft / total)
    return score, accuracy >= 0.99


def main() -> None:
    parser = argparse.ArgumentParser(description="MYCELIUM Auto-evolve environment coevolution (POET-style)")
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--envs", type=int, default=6)
    parser.add_argument("--solvers-per-env", type=int, default=8)
    parser.add_argument("--out", default=".mycelium_environments/coevolution.json")
    args = parser.parse_args()

    rng = random.Random(next_prime(args.seed))
    factory = ChallengeFactory(
        max_program_depth=5,
        max_program_nodes=MAX_NODES,
        max_abs_value=MAX_ABS,
        max_eval_steps=MAX_STEPS,
        train_cases=8,
        test_cases=12,
    )
    ecology = EnvironmentEcology(capacity=max(8, args.envs * 2))

    # initial environments + one solver population per environment
    solver_pools: dict[str, list[Node]] = {}
    for index in range(args.envs):
        genome = EnvironmentGenome(
            seed=next_prime(args.seed + 101 * (index + 1)),
            difficulty=2 + index,
            compositional_bias=min(0.9, 0.15 * index),
        )
        key = ecology.add_environment(genome)
        solver_pools[key] = [random_tree(rng, max_depth=4, constant_scale=8) for _ in range(args.solvers_per_env)]

    timeline: list[dict] = []
    for round_index in range(1, args.rounds + 1):
        # each environment evaluates its pool; solvers mutate under local pressure
        for key, record in list(ecology.environments.items()):
            challenge = build_challenge(factory, record.genome)
            pool = solver_pools.setdefault(key, [random_tree(rng, max_depth=4, constant_scale=8) for _ in range(args.solvers_per_env)])
            scored = []
            for solver in pool:
                score, solved = score_solver(solver, challenge)
                scored.append((score, solved, solver))
            scored.sort(key=lambda item: -item[0])
            best_score, best_solved, _ = scored[0]
            ecology.record_outcome(key, best_score, solved=best_solved)
            survivors = [solver for _, _, solver in scored[:2]]
            while len(survivors) < args.solvers_per_env:
                parent = rng.choice(scored[:4])[2]
                survivors.append(mutate(parent, rng, max_depth=5, constant_scale=6 + record.genome.difficulty))
            solver_pools[key] = survivors

        # cross-transfer trials: fertile env champions on other envs
        def evaluate(source_key: str, target_key: str) -> float:
            source_champion = max(
                solver_pools.get(source_key, []),
                key=lambda s: score_solver(s, build_challenge(factory, ecology.environments[source_key].genome))[0],
            )
            target_challenge = build_challenge(factory, ecology.environments[target_key].genome)
            source_score, _ = score_solver(source_champion, target_challenge)
            local_best = max(
                score_solver(s, target_challenge)[0]
                for s in solver_pools.get(target_key, [])
            ) if solver_pools.get(target_key) else 0.0
            gain = source_score - local_best
            if gain > 0:
                solver_pools[target_key].append(source_champion.clone())
                solver_pools[target_key] = solver_pools[target_key][-args.solvers_per_env * 2:]
            return max(0.0, gain)

        transfers = run_cross_transfer_trials(ecology, evaluate, rng=rng, trials_per_round=2)
        step = ecology.evolve(rng)
        timeline.append({
            "round": round_index,
            "living_envs": step["living"],
            "transfers": transfers,
            "edges": len(ecology.curriculum_edges),
        })

    payload = {
        "rounds": args.rounds,
        "final_environment_count": len(ecology.environments),
        "curriculum_edge_count": len(ecology.curriculum_edges),
        "ecology": ecology.to_dict(),
        "timeline": timeline,
    }
    from mycelium_accel.telemetry import stamp_provenance

    stamp_provenance(payload, "run_environment_coevolution")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "rounds": args.rounds,
        "final_environment_count": payload["final_environment_count"],
        "curriculum_edge_count": payload["curriculum_edge_count"],
        "fertile_now": ecology.fertile_environments(),
    }, indent=2))
    print(f"details -> {out_path}")


if __name__ == "__main__":
    main()
