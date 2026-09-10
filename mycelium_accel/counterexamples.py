"""Counterexample-driven evaluation pressure (Phase 3, CDGP-style).

Whenever an elite fails a case, that case is evidence about where the search
should go next. The bank below harvests failing (input, expected) pairs from
challenges, keeps them prioritized by residual magnitude + recency, and hands
them to semantic mutations and to dynamic test-set expansion.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Sequence

from .dsl import ProgramExecutor


@dataclass(slots=True)
class Counterexample:
    x: int
    expected: int
    predicted: int
    source_seed: int
    added_round: int
    times_used: int = 0

    @property
    def residual(self) -> int:
        return abs(self.predicted - self.expected)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Counterexample:
        return cls(
            x=int(payload["x"]),
            expected=int(payload["expected"]),
            predicted=int(payload["predicted"]),
            source_seed=int(payload.get("source_seed", 0)),
            added_round=int(payload.get("added_round", 0)),
            times_used=int(payload.get("times_used", 0)),
        )


@dataclass
class CounterexampleBank:
    capacity: int = 256
    items: dict[int, Counterexample] = field(default_factory=dict)  # keyed by input x

    def add(self, example: Counterexample) -> None:
        existing = self.items.get(example.x)
        if existing is not None:
            existing.predicted = example.predicted
            existing.added_round = example.added_round
            return
        self.items[example.x] = example
        self._evict_if_needed()

    def add_batch(self, examples: Iterable[Counterexample]) -> int:
        added = 0
        for example in examples:
            before = len(self.items)
            self.add(example)
            added += 1 if len(self.items) > before or example.x in self.items else 0
        return added

    def _evict_if_needed(self) -> None:
        if len(self.items) <= self.capacity:
            return
        ranked = sorted(
            self.items.values(),
            key=lambda item: (-max(1, item.residual), -item.added_round, item.times_used),
        )
        keep = ranked[: self.capacity]
        self.items = {item.x: item for item in keep}

    def sample(self, rng: random.Random, count: int) -> list[Counterexample]:
        if not self.items:
            return []
        population = list(self.items.values())
        count = min(count, len(population))
        chosen = rng.sample(population, k=count)
        for item in chosen:
            item.times_used += 1
        return chosen

    def top(self, count: int) -> list[Counterexample]:
        ranked = sorted(self.items.values(), key=lambda item: (-max(1, item.residual), -item.added_round))
        return ranked[:count]

    def blame_pairs(self, count: int) -> list[tuple[int, int]]:
        """(x, expected) pairs for the strongest counterexamples."""
        return [(item.x, item.expected) for item in self.top(count)]

    def as_training_pairs(self, count: int, rng: random.Random | None = None) -> list[tuple[int, int]]:
        if rng is not None:
            return [(item.x, item.expected) for item in self.sample(rng, count)]
        return self.blame_pairs(count)

    def size(self) -> int:
        return len(self.items)

    def persist(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "capacity": self.capacity,
            "items": [item.to_dict() for item in self.items.values()],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> CounterexampleBank:
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        bank = cls(capacity=int(payload.get("capacity", 256)))
        for item_payload in payload.get("items", []):
            item = Counterexample.from_dict(item_payload)
            bank.items[item.x] = item
        return bank


def harvest_counterexamples(
    executor: ProgramExecutor | None,
    pairs: Sequence[tuple[int, int]],
    *,
    source_seed: int,
    round_index: int,
    limit: int = 32,
    min_residual: int = 1,
) -> list[Counterexample]:
    """Find the cases where an executor disagrees with the expected outputs."""
    if executor is None:
        return []
    found: list[Counterexample] = []
    for x, expected in pairs:
        try:
            predicted = executor.run(int(x))
        except Exception:
            continue
        residual = abs(predicted - expected)
        if residual < min_residual:
            continue
        found.append(
            Counterexample(
                x=int(x),
                expected=int(expected),
                predicted=int(predicted),
                source_seed=source_seed,
                added_round=round_index,
            )
        )
        if len(found) >= limit:
            break
    return found


def divergence_cases(
    executor_a: ProgramExecutor | None,
    executor_b: ProgramExecutor | None,
    inputs: Sequence[int],
    *,
    expected_lookup: dict[int, int] | None = None,
    source_seed: int,
    round_index: int,
    limit: int = 32,
) -> list[Counterexample]:
    """Cases where two executors diverge — cheap candidate-vs-baseline mining."""
    if executor_a is None or executor_b is None:
        return []
    found: list[Counterexample] = []
    for x in inputs:
        try:
            out_a = executor_a.run(int(x))
            out_b = executor_b.run(int(x))
        except Exception:
            continue
        if out_a == out_b:
            continue
        expected = expected_lookup.get(int(x), out_b) if expected_lookup else out_b
        found.append(
            Counterexample(
                x=int(x),
                expected=int(expected),
                predicted=int(out_a),
                source_seed=source_seed,
                added_round=round_index,
            )
        )
        if len(found) >= limit:
            break
    return found
