"""Task/solution coevolution: a population of challenge environments that
itself evolves (Roadmap Phase 7 — POET/Enhanced-POET-style).

Instead of one scalar difficulty, MYCELIUM Auto-evolve keeps *families* of environments
with their own genomes. An environment survives when it sits in the
fertile band — neither trivially easy nor persistently impossible for the
current solver population — and when it creates transfer value to other
environments (cross-transfer trials). Curriculum becomes a *graph* of
useful predecessors, not a queue.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Callable

from .prime import next_prime


@dataclass(slots=True)
class EnvironmentGenome:
    """Heritable recipe for generating one family of challenges."""

    seed: int
    difficulty: int = 2
    depth_bias: float = 0.5
    const_scale: int = 6
    compositional_bias: float = 0.3
    span_bias: int = 12
    generation: int = 0

    def mutate(self, rng: random.Random) -> EnvironmentGenome:
        child = EnvironmentGenome(
            seed=next_prime(self.seed + rng.randint(1, 1000)),
            difficulty=max(1, self.difficulty + rng.choice((-1, 0, 0, 1))),
            depth_bias=min(1.0, max(0.0, self.depth_bias + rng.uniform(-0.1, 0.1))),
            const_scale=max(2, self.const_scale + rng.choice((-2, 0, 2))),
            compositional_bias=min(0.9, max(0.0, self.compositional_bias + rng.uniform(-0.08, 0.08))),
            span_bias=max(8, self.span_bias + rng.choice((-2, 0, 2))),
            generation=self.generation + 1,
        )
        return child

    def descriptor(self) -> tuple[int, ...]:
        return (
            min(9, self.difficulty),
            int(self.depth_bias * 4),
            min(4, self.const_scale // 5),
            int(self.compositional_bias * 3),
            min(5, self.span_bias // 8),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnvironmentRecord:
    genome: EnvironmentGenome
    recent_scores: list[float] = field(default_factory=list)
    solved_count: int = 0
    attempted_count: int = 0
    transfer_donations: int = 0
    transfer_receipts: int = 0
    alive: bool = True
    stagnant_rounds: int = 0

    def mean_recent_score(self) -> float:
        return sum(self.recent_scores) / len(self.recent_scores) if self.recent_scores else 0.0

    def fertilizer_score(self, novelty: float) -> float:
        """How attractive this environment is: solvability band × novelty × transfer."""
        mean = self.mean_recent_score()
        band = 1.0 - abs(mean - 0.55) / 0.55  # peak around 55% success
        band = max(0.0, min(1.0, band))
        transfer = 1.0 + 0.25 * self.transfer_donations
        return band * (0.6 + 0.4 * novelty) * transfer

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mean_recent_score"] = self.mean_recent_score()
        return payload


@dataclass(slots=True)
class MinimalCriterionBand:
    """Environments outside the band die: too easy or persistently impossible."""

    min_score: float = 0.05
    max_score: float = 0.95
    patience_rounds: int = 12

    def verdict(self, record: EnvironmentRecord) -> str:
        """"live" | "retire" — checked once a record has enough attempts."""
        if record.attempted_count < 4:
            return "live"
        mean = record.mean_recent_score()
        if self.min_score <= mean <= self.max_score:
            record.stagnant_rounds = 0
            return "live"
        record.stagnant_rounds += 1
        if record.stagnant_rounds >= self.patience_rounds:
            return "retire"
        return "live"


@dataclass
class EnvironmentEcology:
    """POET-style population of environments with cross-transfer trials."""

    capacity: int = 12
    window: int = 8
    band: MinimalCriterionBand = field(default_factory=MinimalCriterionBand)
    environments: dict[str, EnvironmentRecord] = field(default_factory=dict)
    curriculum_edges: dict[tuple[str, str], float] = field(default_factory=dict)
    rounds: int = 0

    def add_environment(self, genome: EnvironmentGenome, key: str | None = None) -> str:
        key = key or f"env_{genome.seed}"
        self.environments[key] = EnvironmentRecord(genome=genome)
        self._cap()
        return key

    def record_outcome(self, key: str, score: float, *, solved: bool) -> None:
        record = self.environments.get(key)
        if record is None:
            return
        record.attempted_count += 1
        record.solved_count += 1 if solved else 0
        record.recent_scores.append(score)
        record.recent_scores = record.recent_scores[-self.window:]

    def evolve(self, rng: random.Random) -> dict[str, Any]:
        """One ecology step: enforce the band, spawn mutants, prune."""
        self.rounds += 1
        retired: list[str] = []
        for key, record in list(self.environments.items()):
            verdict = self.band.verdict(record)
            if verdict == "retire" or len(record.recent_scores) >= self.window:
                if verdict == "retire":
                    record.alive = False
                    retired.append(key)

        descriptors = [record.genome.descriptor() for record in self.environments.values()]
        novelties: dict[str, float] = {}
        for key, record in self.environments.items():
            desc = record.genome.descriptor()
            distances = [
                sum(1 for a, b in zip(desc, other) if a != b)
                for other in descriptors
                if other != desc
            ]
            novelties[key] = (sum(distances) / len(distances) / max(1, len(desc))) if distances else 1.0

        living = [key for key, record in self.environments.items() if record.alive]
        parents = sorted(
            living,
            key=lambda key: -self.environments[key].fertilizer_score(novelties[key]),
        )[:3]
        spawned: list[str] = []
        for parent_key in parents:
            if len(self.environments) >= self.capacity:
                break
            child = self.environments[parent_key].genome.mutate(rng)
            child_key = f"env_{child.seed}"
            if child_key in self.environments:
                continue
            self.environments[child_key] = EnvironmentRecord(genome=child)
            spawned.append(child_key)

        for key in retired:
            if len(self.environments) > max(4, self.capacity // 2):
                del self.environments[key]
        return {"retired": retired, "spawned": spawned, "living": len(self.environments)}

    def record_transfer(self, source_key: str, target_key: str, *, gain: float) -> None:
        """A solution trained on `source` improved a `target` attempt."""
        source = self.environments.get(source_key)
        target = self.environments.get(target_key)
        if source is not None:
            source.transfer_donations += 1
        if target is not None:
            target.transfer_receipts += 1
        edge = (source_key, target_key)
        self.curriculum_edges[edge] = self.curriculum_edges.get(edge, 0.0) + gain

    def fertile_environments(self, count: int = 3) -> list[str]:
        living = [(key, record) for key, record in self.environments.items() if record.alive]
        ranked = sorted(living, key=lambda item: -item[1].fertilizer_score(0.5))
        return [key for key, _ in ranked[:count]]

    def curriculum_predecessors(self, key: str) -> list[tuple[str, float]]:
        predecessors = [
            (source, weight)
            for (source, target), weight in self.curriculum_edges.items()
            if target == key
        ]
        predecessors.sort(key=lambda item: -item[1])
        return predecessors

    def _cap(self) -> None:
        while len(self.environments) > self.capacity:
            weakest = min(
                self.environments.items(),
                key=lambda item: item[1].fertilizer_score(0.5),
            )
            del self.environments[weakest[0]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": self.rounds,
            "environments": {key: record.to_dict() for key, record in self.environments.items()},
            "curriculum_edges": {f"{a}->{b}": weight for (a, b), weight in self.curriculum_edges.items()},
        }


def run_cross_transfer_trials(
    ecology: EnvironmentEcology,
    evaluate: Callable[[str, str], float],
    *,
    rng: random.Random,
    trials_per_round: int = 2,
) -> list[dict[str, Any]]:
    """Try solutions of fertile envs on *other* envs; record transfer edges.

    ``evaluate(source_key, target_key)`` must return the transfer gain of the
    source's current champion evaluated on the target's task (>0 = helps).
    """
    fertile = ecology.fertile_environments(count=min(4, len(ecology.environments)))
    others = [key for key in ecology.environments if key not in fertile]
    results: list[dict[str, Any]] = []
    if not others or not fertile:
        return results
    for _ in range(trials_per_round):
        source = rng.choice(fertile)
        target = rng.choice(others)
        gain = evaluate(source, target)
        if gain > 0:
            ecology.record_transfer(source, target, gain=gain)
        results.append({"source": source, "target": target, "gain": gain})
    return results
