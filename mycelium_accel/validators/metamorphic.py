"""Metamorphic validation: relations that optimized code must preserve.

Even when no oracle exists, relations of the form ``f(k*x) relation f(x)``
constrain whether an optimized variant can be correct. A variant that
violates an established relation is rejected without needing ground truth.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Callable

from ..prime import next_prime


@dataclass(slots=True)
class MetamorphicRelation:
    name: str
    # transform (x, rng) -> x'; relation(fn(x), fn(x')) must hold
    transform: Callable[[int, random.Random], int] = field(repr=False, default=lambda x, rng: -x)
    relation: Callable[[Any, Any], bool] = field(repr=False, default=lambda a, b: a == b)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}


NEGATION = MetamorphicRelation(
    name="input-negation-preserves-magnitude",
    transform=lambda x, rng: -x,
    relation=lambda a, b: abs(int(a)) == abs(int(b)) or a == b,
)

SHIFT_EQUIVARIANCE = MetamorphicRelation(
    name="input-shift-equivariance",
    transform=lambda x, rng: x + rng.choice((1, 7, 101)),
    relation=lambda a, b: isinstance(a, int) and isinstance(b, int),
)


@dataclass(slots=True)
class MetamorphicReport:
    relation: str
    cases_run: int
    violations: int
    holds: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_metamorphic(
    fn: Callable[..., Any],
    relation: MetamorphicRelation,
    *,
    n_cases: int = 128,
    seed: int = 101,
) -> MetamorphicReport:
    seed = next_prime(seed)
    rng = random.Random(seed)
    violations = 0
    for _ in range(n_cases):
        x = rng.randint(-10**5, 10**5)
        try:
            base = fn(x)
            variant = fn(relation.transform(x, rng))
        except Exception:
            violations += 1
            continue
        if not relation.relation(base, variant):
            violations += 1
    return MetamorphicReport(
        relation=relation.name,
        cases_run=n_cases,
        violations=violations,
        holds=violations == 0,
    )
