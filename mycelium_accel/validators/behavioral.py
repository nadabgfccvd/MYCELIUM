"""Behavioral equivalence checking by deterministic paired evaluation."""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any
from collections.abc import Callable, Sequence

from ..prime import next_prime


@dataclass(slots=True)
class EquivalenceReport:
    equivalent: bool
    cases_run: int
    mismatches: int
    first_mismatch: dict[str, Any] | None = None
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_scalar_sampler(rng: random.Random) -> list[int]:
    return [rng.randint(-10**6, 10**6)]


def verify_equivalent(
    fn_a: Callable[..., Any],
    fn_b: Callable[..., Any],
    *,
    n_cases: int = 512,
    seed: int = 101,
    arg_sampler: Callable[[random.Random], Sequence[Any]] = _default_scalar_sampler,
    compare: Callable[[Any, Any], bool] | None = None,
) -> EquivalenceReport:
    """Deterministic paired equivalence: both functions see identical args."""
    seed = next_prime(seed)
    rng = random.Random(seed)
    compare = compare or (lambda a, b: a == b)
    mismatches = 0
    first_mismatch: dict[str, Any] | None = None
    for case_index in range(n_cases):
        args = list(arg_sampler(rng))
        try:
            out_a = fn_a(*args)
        except Exception as exc:  # a crashing baseline is not "equivalent"
            out_a = ("__exception__", type(exc).__name__)
        try:
            out_b = fn_b(*args)
        except Exception as exc:
            out_b = ("__exception__", type(exc).__name__)
        if not compare(out_a, out_b):
            mismatches += 1
            if first_mismatch is None:
                first_mismatch = {"case": case_index, "args": args, "a": repr(out_a), "b": repr(out_b)}
    return EquivalenceReport(
        equivalent=mismatches == 0,
        cases_run=n_cases,
        mismatches=mismatches,
        first_mismatch=first_mismatch,
        seed=seed,
    )


def verify_equivalent_with_cases(
    fn_a: Callable[..., Any],
    fn_b: Callable[..., Any],
    cases: Sequence[Sequence[Any]],
) -> EquivalenceReport:
    """Equivalence restricted to a fixed case list (e.g. project tests)."""
    mismatches = 0
    first_mismatch: dict[str, Any] | None = None
    for case_index, args in enumerate(cases):
        out_a = fn_a(*args)
        out_b = fn_b(*args)
        if out_a != out_b:
            mismatches += 1
            if first_mismatch is None:
                first_mismatch = {"case": case_index, "args": list(args), "a": repr(out_a), "b": repr(out_b)}
    return EquivalenceReport(
        equivalent=mismatches == 0,
        cases_run=len(cases),
        mismatches=mismatches,
        first_mismatch=first_mismatch,
    )
