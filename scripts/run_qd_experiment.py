#!/usr/bin/env python3
"""Phase 6 experiment: compare QD-ecology search against the linear frontier.

Each generation, emitters (quality / novelty / recombination / simplifier)
pick parents from the archive; candidates are produced by the MYCELIUM Auto-evolve
mutation stack, evaluated on procedural challenges, and reinserted into the
grid archive. Reports coverage, QD-score and QD-AUC over generations, plus
the transfer graph accumulated between descriptor cells.

    python scripts/run_qd_experiment.py --generations 25 --seed 101
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mycelium_accel.challenge import ChallengeFactory
from mycelium_accel.dsl import Node, compile_program, mutate
from mycelium_accel.prime import next_prime
from mycelium_accel.qd_archive import (
    QDArchive,
    QDEntry,
    default_emitters,
    descriptor_from_signature,
)
from mycelium_accel.semantics import canonical_probes, safe_signature
from mycelium_accel.transfer_graph import TransferGraph

MAX_NODES = 63
MAX_ABS = 100_000
MAX_STEPS = 256


def evaluate_genome(genome: Node, challenges) -> tuple[float, tuple[int, ...] | None]:
    try:
        executor = compile_program(genome, {}, max_nodes=MAX_NODES, max_abs_value=MAX_ABS, max_steps=MAX_STEPS)
    except Exception:
        return 0.0, None
    total_exact = 0.0
    total_soft = 0.0
    count = 0
    for challenge in challenges:
        for x, expected in challenge.train_pairs + challenge.test_pairs:
            try:
                predicted = executor.run(x)
            except Exception:
                continue
            count += 1
            error = abs(predicted - expected)
            total_soft += 1.0 / (1.0 + error)
            if error == 0:
                total_exact += 1.0
    if count == 0:
        return 0.0, None
    quality = total_exact + 0.25 * (total_soft / count) - 0.002 * genome.count_nodes()
    return quality, None


def make_entry(genome: Node, quality: float, probes: tuple[int, ...], origin: str, generation: int, genomes: dict[str, Node]) -> QDEntry | None:
    signature = safe_signature(genome, {}, probes, max_nodes=MAX_NODES, max_abs_value=MAX_ABS, max_steps=MAX_STEPS)
    if signature is None:
        return None
    key = genome.render()
    genomes[key] = genome
    return QDEntry(
        key=key,
        signature=signature,
        descriptor=descriptor_from_signature(signature, node_count=genome.count_nodes()),
        quality=quality,
        cost_nodes=genome.count_nodes(),
        origin=origin,
        generation=generation,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MYCELIUM Auto-evolve QD ecology experiment")
    parser.add_argument("--generations", type=int, default=25)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--population", type=int, default=16)
    parser.add_argument("--challenge-difficulty", type=int, default=4)
    parser.add_argument("--out", default=".mycelium_qd/qd_experiment.json")
    args = parser.parse_args()

    rng = random.Random(next_prime(args.seed))
    probes = canonical_probes(7)
    factory = ChallengeFactory(
        max_program_depth=5,
        max_program_nodes=MAX_NODES,
        max_abs_value=MAX_ABS,
        max_eval_steps=MAX_STEPS,
        train_cases=8,
        test_cases=12,
    )
    challenges = [
        factory.build(next_prime(args.seed + 31 * index), args.challenge_difficulty + index)
        for index in range(3)
    ]

    archive = QDArchive(cells_capacity=256, occupants_per_cell=2)
    transfer_graph = TransferGraph()
    emitters = default_emitters()
    genomes: dict[str, Node] = {}

    # seed population
    from mycelium_accel.dsl import random_tree

    seeds_pop = [random_tree(rng, max_depth=4, constant_scale=8) for _ in range(args.population)]
    for genome in seeds_pop:
        quality, _ = evaluate_genome(genome, challenges)
        entry = make_entry(genome, quality, probes, "seed", 0, genomes)
        if entry is not None:
            archive.insert(entry)
    archive.record_generation()

    for generation in range(1, args.generations + 1):
        elites = archive.elites()
        emissions = []
        for emitter in emitters:
            emissions.extend(emitter.emit(elites, rng, {"genomes": genomes}))
        if not emissions:
            emissions = []
        accepted_this_gen = 0
        for emission in emissions:
            child = mutate(emission.genome, rng, max_depth=5, constant_scale=8 + generation)
            quality, _ = evaluate_genome(child, challenges)
            entry = make_entry(child, quality, probes, emission.source_emitter, generation, genomes)
            if entry is None:
                continue
            donors = [elite for elite in elites if elite.key == emission.genome.render()]
            inserted = archive.insert(entry)
            if inserted:
                accepted_this_gen += 1
                base_quality = donors[0].quality if donors else 0.0
                gain = quality - base_quality
                if donors and gain > 0 and donors[0].descriptor != entry.descriptor:
                    transfer_graph.record(
                        str(donors[0].descriptor),
                        str(entry.descriptor),
                        gain=gain,
                        round_index=generation,
                    )
        archive.record_generation()

    history = [snap.to_dict() for snap in archive.history]
    payload = {
        "generations": args.generations,
        "final_coverage": archive.coverage(),
        "final_qd_score": archive.qd_score(),
        "final_qd_auc": archive.qd_auc(),
        "best_ever_quality": archive.best_ever_quality,
        "total_insertions": archive.total_insertions,
        "cells_occupied": len(archive.grid),
        "useful_transfer_edges": len(transfer_graph.useful_edges()),
        "history": history,
        "transfer_graph": transfer_graph.to_dict(),
    }
    from mycelium_accel.telemetry import stamp_provenance

    stamp_provenance(payload, "run_qd_experiment")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    transfer_graph.persist(out_path.parent / "transfer_graph.json")
    print(json.dumps({key: payload[key] for key in (
        "generations", "final_coverage", "final_qd_score", "final_qd_auc",
        "best_ever_quality", "total_insertions", "cells_occupied", "useful_transfer_edges",
    )}, indent=2))
    print(f"history -> {out_path}")


if __name__ == "__main__":
    main()
