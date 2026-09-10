from __future__ import annotations

import importlib.util
import math
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Callable

from .generated import active_variants


AggregateFn = Callable[[list[float]], tuple[float, float]]


def aggregate_scores_loop(scores: list[float]) -> tuple[float, float]:
    ordered = sorted(scores, reverse=True)
    window = ordered[: min(5, len(ordered))] or [0.0]
    total = 0.0
    for value in window:
        total += value
    rounded = set()
    for value in scores:
        rounded.add(round(value, 4))
    diversity = len(rounded) / max(1, len(scores))
    return total / len(window), diversity


def aggregate_scores_pythonic(scores: list[float]) -> tuple[float, float]:
    ordered = sorted(scores, reverse=True)
    window = ordered[: min(5, len(ordered))] or [0.0]
    diversity = len({round(value, 4) for value in scores}) / max(1, len(scores))
    return sum(window) / len(window), diversity


VARIANTS: dict[str, AggregateFn] = {
    "loop": aggregate_scores_loop,
    "pythonic": aggregate_scores_pythonic,
}


def aggregate_scores(scores: list[float]) -> tuple[float, float]:
    variant_name = active_variants.AGGREGATE_SCORES_VARIANT
    function = VARIANTS.get(variant_name, aggregate_scores_loop)
    return function(scores)


@dataclass(slots=True)
class BenchmarkResult:
    variant: str
    seconds: float


@dataclass(slots=True)
class ExternalBenchmarkOutcome:
    module_path: str
    baseline: str
    best_variant: str
    timings: list[BenchmarkResult]


def _benchmark_callable(fn: Callable[..., Any], cases: list[dict[str, Any]], repeats: int) -> float:
    started = time.perf_counter()
    for _ in range(repeats):
        for case in cases:
            fn(*case.get("args", []), **case.get("kwargs", {}))
    return time.perf_counter() - started


def accelerate_self(project_root: Path, *, apply: bool = True) -> ExternalBenchmarkOutcome:
    rng = random.Random(101)
    cases = []
    for width in range(16, 128, 16):
        cases.append({"args": [[rng.random() * math.pi for _ in range(width)]], "kwargs": {}})

    timings: list[BenchmarkResult] = []
    for name, fn in VARIANTS.items():
        elapsed = _benchmark_callable(fn, cases, repeats=250)
        timings.append(BenchmarkResult(name, elapsed))

    best = min(timings, key=lambda item: item.seconds)
    generated_path = project_root / "mycelium_accel" / "generated" / "active_variants.py"
    if apply:
        generated_path.write_text(
            '"""Auto-updated by the accelerator. Commit this file so optimized choices persist."""\n\n'
            f'AGGREGATE_SCORES_VARIANT = "{best.variant}"\n',
            encoding="utf-8",
        )
    return ExternalBenchmarkOutcome(
        module_path=str(generated_path),
        baseline=active_variants.AGGREGATE_SCORES_VARIANT,
        best_variant=best.variant,
        timings=timings,
    )


def load_module_from_path(module_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"accel_target_{module_path.stem}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def accelerate_external(module_path: Path) -> ExternalBenchmarkOutcome:
    module = load_module_from_path(module_path)
    spec: dict[str, Any] = getattr(module, "BENCHMARK_SPEC")
    baseline_name = spec["baseline"]
    variant_names = spec["variants"]
    cases = spec["cases"]
    repeats = int(spec.get("repeats", 200))
    active_var_name = spec.get("active_variable", "ACTIVE_VARIANT")

    baseline_fn = getattr(module, baseline_name)
    baseline_outputs = [baseline_fn(*case.get("args", []), **case.get("kwargs", {})) for case in cases]

    timings: list[BenchmarkResult] = []
    for variant_name in variant_names:
        fn = getattr(module, variant_name)
        outputs = [fn(*case.get("args", []), **case.get("kwargs", {})) for case in cases]
        if outputs != baseline_outputs:
            continue
        elapsed = _benchmark_callable(fn, cases, repeats)
        timings.append(BenchmarkResult(variant_name, elapsed))

    if not timings:
        raise RuntimeError("No externally supplied variant matched the baseline output.")

    best = min(timings, key=lambda item: item.seconds)
    pattern = re.compile(rf"^{active_var_name}\s*=\s*['\"][^'\"]+['\"]\s*$", re.MULTILINE)
    source = module_path.read_text(encoding="utf-8")
    replacement = f'{active_var_name} = "{best.variant}"'
    if not pattern.search(source):
        raise RuntimeError(
            f"Expected a top-level assignment for {active_var_name} in {module_path}."
        )
    module_path.write_text(pattern.sub(replacement, source, count=1), encoding="utf-8")
    return ExternalBenchmarkOutcome(
        module_path=str(module_path),
        baseline=baseline_name,
        best_variant=best.variant,
        timings=timings,
    )
