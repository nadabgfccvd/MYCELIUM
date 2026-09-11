"""Reproducible statistical benchmark executor (Hyperfine-style, Phase 1).

Runs manifest benchmark commands with warmup, paired seed control, prepare
hooks and inter-variant cleanup, then exports JSON/CSV/Markdown reports.
Benchmark records are persisted one row per ``(candidate, seed, metric)`` as
required by the paired-statistics layer.
"""
from __future__ import annotations

import csv
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .stats import compare_paired_metric
from .targets.base import ProjectTarget, TargetRunResult, Variant


@dataclass(slots=True)
class BenchmarkRun:
    candidate: str
    seed: int
    metric: str
    value: float
    seconds: float
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BenchmarkRun:
        return cls(
            candidate=str(payload["candidate"]),
            seed=int(payload["seed"]),
            metric=str(payload["metric"]),
            value=float(payload["value"]),
            seconds=float(payload["seconds"]),
            ok=bool(payload["ok"]),
        )


@dataclass(slots=True)
class CandidateSummary:
    candidate: str
    runs: list[BenchmarkRun]
    mean: float
    stddev: float
    median: float
    minimum: float
    maximum: float
    flaky: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["runs"] = [run.to_dict() for run in self.runs]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CandidateSummary:
        return cls(
            candidate=str(payload["candidate"]),
            runs=[BenchmarkRun.from_dict(r) for r in payload.get("runs", [])],
            mean=float(payload["mean"]),
            stddev=float(payload["stddev"]),
            median=float(payload["median"]),
            minimum=float(payload["minimum"]),
            maximum=float(payload["maximum"]),
            flaky=bool(payload.get("flaky", False)),
        )


class SweepInterrupted(KeyboardInterrupt):
    """Ctrl-C during a sweep, carrying the honestly-measured partial sweep.

    Subclasses KeyboardInterrupt so generic handlers still stop; handlers that
    want the partial data catch this class first (see ``accelerate_target``).
    """

    def __init__(self, sweep: BenchmarkSweep | None, raced: list[str] | None = None) -> None:
        super().__init__("sweep interrupted by user")
        self.sweep = sweep
        self.raced = list(raced) if raced else []


@dataclass(slots=True)
class BenchmarkSweep:
    target: str
    metric: str
    lower_is_better: bool
    summaries: list[CandidateSummary]
    comparisons: list[dict[str, Any]]
    started_at: float = field(default_factory=time.time)
    partial: bool = False  # Q2.1: True when Ctrl-C cut the sweep short

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "target": self.target,
            "metric": self.metric,
            "lower_is_better": self.lower_is_better,
            "started_at": self.started_at,
            "summaries": [summary.to_dict() for summary in self.summaries],
            "comparisons": self.comparisons,
        }
        if self.partial:
            payload["partial"] = True  # conditional: old files roundtrip clean
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BenchmarkSweep:
        if not isinstance(payload, dict):  # Q1.3: friendly, never AttributeError
            raise ValueError(
                f"Sweep must be a JSON object, got {type(payload).__name__}."
            )
        return cls(
            target=str(payload.get("target", "")),
            metric=str(payload.get("metric", "")),
            lower_is_better=bool(payload.get("lower_is_better", True)),
            summaries=[CandidateSummary.from_dict(s) for s in payload.get("summaries", [])],
            comparisons=list(payload.get("comparisons", [])),
            started_at=float(payload.get("started_at", 0.0)),
            partial=bool(payload.get("partial", False)),
        )


FLAKY_CV_THRESHOLD = 0.15  # API_STABLE_1.0.md §5: advisory only, never changes verdicts


def _seed_means(runs: list[BenchmarkRun]) -> list[float]:
    buckets: dict[int, list[float]] = {}
    for run in runs:
        if run.ok and math.isfinite(run.value):
            buckets.setdefault(run.seed, []).append(run.value)
    return [sum(v) / len(v) for v in buckets.values()]


ADAPTIVE_MIN_REPEATS = 2  # API_STABLE_1.0.md §6
ADAPTIVE_REL_HALFWIDTH = 0.01


def adaptive_stop(values: list[float]) -> bool:
    """V4.2 rule: stop repeats at r>=2 when 1.96*sd/sqrt(r)/|mean| < 1%."""
    if len(values) < ADAPTIVE_MIN_REPEATS:
        return False
    mean = _mean(values)
    if mean == 0:
        return False  # never stop early on zero mean (conservative)
    hw = 1.96 * _stddev(values) / math.sqrt(len(values))
    return hw / abs(mean) < ADAPTIVE_REL_HALFWIDTH


def summarize_runs(candidate: str, runs: list[BenchmarkRun]) -> CandidateSummary:
    """Module-level summarize (pure in ``runs``) — shared by the executor,
    the V4.2 replay simulation and the cache validator."""
    values = [run.value for run in runs if run.ok]
    bad = not values or any(not run.ok for run in runs)
    if bad:
        values = [float("inf")]
    return CandidateSummary(
        candidate=candidate,
        runs=runs,
        mean=_mean(values),
        stddev=_stddev(values),
        median=_median(values),
        minimum=min(values),
        maximum=max(values),
        flaky=is_flaky(runs),
    )


def is_flaky(runs: list[BenchmarkRun]) -> bool:
    """True when the CV of per-seed means exceeds the threshold (< 3 seeds: False)."""
    means = _seed_means(runs)
    if len(means) < 3:
        return False
    mean = _mean(means)
    if mean == 0:
        return False
    return _stddev(means) / abs(mean) > FLAKY_CV_THRESHOLD


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    try:
        return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
    except OverflowError:
        return float("inf")  # M3: huge-but-finite values degrade, never crash


def _median(values: list[float]) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _as_metric_float(value: Any, parser: str) -> float:
    """Coerce a captured metric to float; a bad capture fails the run, not the
    sweep (Ciclo 4/S2: a benchmark printing ``"seconds": "fast"`` used to escape
    parse_metrics as an uncaught ValueError and traceback the whole sweep)."""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"{parser} parser captured a non-numeric metric {value!r}") from exc


def _parse_regex_metric(
    result: TargetRunResult, pattern_text: str, metric_name: str,
) -> dict[str, float]:
    """regex:<pattern> metric extraction; every failure mode is a RuntimeError
    so a bad/ungrouped pattern fails the run instead of tracebacking the sweep."""
    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        raise RuntimeError(f"invalid regex metric parser: {pattern_text!r} ({exc})") from exc
    match = pattern.search(result.stdout_tail + "\n" + result.stderr_tail)
    if not match:
        raise RuntimeError(f"regex parser did not match output: {pattern.pattern!r}")
    if match.groupdict():
        key = metric_name if metric_name in match.groupdict() else next(iter(match.groupdict()))
        return {metric_name: _as_metric_float(match.group(key), "regex")}
    try:
        captured = match.group(1)
    except IndexError as exc:  # pattern matched but has no capture group
        raise RuntimeError(
            f"regex parser {pattern.pattern!r} has no capture group for the metric") from exc
    return {metric_name: _as_metric_float(captured, "regex")}


def parse_metrics(result: TargetRunResult, parser: str, metric_name: str) -> dict[str, float]:
    """Extract the metric from a benchmark run according to the parser mode."""
    if parser == "time":
        return {metric_name: result.seconds}
    if parser == "json_stdout":
        for line in reversed(result.stdout_tail.strip().splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if metric_name in payload:
                return {metric_name: _as_metric_float(payload[metric_name], "json_stdout")}
        raise RuntimeError("json_stdout parser found no JSON line with the requested metric.")
    if parser.startswith("regex:"):
        return _parse_regex_metric(result, parser[len("regex:"):], metric_name)
    raise ValueError(f"Unknown metrics parser: {parser}")


class BenchmarkExecutor:
    """Hyperfine-style runner over a ProjectTarget."""

    def __init__(self, target: ProjectTarget, *, export_dir: Path | None = None) -> None:
        self.target = target
        self.export_dir = export_dir or (target.root / ".mycelium_benchmarks")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def benchmark_candidate(
        self,
        candidate: str,
        seeds: list[int],
        *,
        variant: Variant | None = None,
        adaptive_repeats: bool = False,
    ) -> list[BenchmarkRun]:
        manifest = self.target.manifest
        if not manifest.benchmark_command:
            raise RuntimeError("Target manifest has no benchmark_command.")
        runs: list[BenchmarkRun] = []
        for warmup_index in range(max(0, manifest.warmup)):
            self._run_once(candidate, warmup_index, seed=seeds[0] if seeds else 101, warmup=True, variant=variant)
        for seed in seeds:
            self.target.prepare(seed)
            seen: list[float] = []
            for _ in range(max(1, manifest.repeats)):
                run = self._run_once(candidate, seed, seed=seed, warmup=False, variant=variant)
                runs.append(run)
                if not run.ok:
                    return runs  # fail fast: no point timing a broken candidate
                seen.append(run.value)
                if adaptive_repeats and adaptive_stop(seen):
                    break  # V4.2: CI already tight for this seed; extra repeats add no information
            self.target.clean()
        return runs

    def _run_once(
        self,
        candidate: str,
        _seed_index: int,  # positional for callers; the timed seed arrives via ``seed``
        *,
        seed: int,
        warmup: bool,
        variant: Variant | None,
    ) -> BenchmarkRun:
        manifest = self.target.manifest
        command = manifest.benchmark_command or ""
        env = None
        snapshot = None
        if variant is not None and variant.mode in {"env", "args", "profile"}:
            env = self.target.variant_env(variant, seed)
            if variant.args:
                command = command + " " + " ".join(variant.args)
        elif variant is not None:
            snapshot = self.target.apply_variant(variant)
            env = self.target.build_env()
            env[manifest.seed_env_var] = str(seed)
        else:
            env = self.target.build_env()
            env[manifest.seed_env_var] = str(seed)
        try:
            result = self.target.runner.run(command, env=env, seed=None)
        finally:
            if snapshot is not None:
                self.target.revert_variant(snapshot, variant)  # type: ignore[arg-type]
        if warmup:
            return BenchmarkRun(candidate, seed, manifest.metric_name, 0.0, result.seconds, result.ok)
        if not result.ok:
            return BenchmarkRun(candidate, seed, manifest.metric_name, float("inf"), result.seconds, False)
        try:
            metrics = parse_metrics(result, manifest.metrics_parser, manifest.metric_name)
        except RuntimeError:
            return BenchmarkRun(candidate, seed, manifest.metric_name, float("inf"), result.seconds, False)
        value = metrics[manifest.metric_name]
        return BenchmarkRun(candidate, seed, manifest.metric_name, value, result.seconds, math.isfinite(value))

    def summarize(self, candidate: str, runs: list[BenchmarkRun]) -> CandidateSummary:
        return summarize_runs(candidate, runs)

    def sweep(
        self,
        candidates: dict[str, Variant | None],
        seeds: list[int],
        *,
        baseline: str | None = None,
        confidence: float = 0.95,
        adaptive_repeats: bool = False,
    ) -> BenchmarkSweep:
        """Benchmark every candidate under the same paired seeds."""
        per_candidate: dict[str, list[BenchmarkRun]] = {}
        interrupted = False
        try:
            for name, variant in candidates.items():
                runs = self.benchmark_candidate(name, seeds, variant=variant, adaptive_repeats=adaptive_repeats)
                per_candidate[name] = runs
                if any(not run.ok for run in runs):
                    break  # a broken candidate aborts the sweep early (cheap futility)
        except KeyboardInterrupt:
            interrupted = True
            if not per_candidate:
                raise  # nothing honestly measured — stay a plain interrupt
        summaries = [self.summarize(name, runs) for name, runs in per_candidate.items()]

        comparisons: list[dict[str, Any]] = []
        baseline_name = baseline or (next(iter(candidates)) if candidates else None)
        if baseline_name and baseline_name in per_candidate:
            baseline_runs = per_candidate[baseline_name]
            for name, runs in per_candidate.items():
                if name == baseline_name:
                    continue
                baseline_map = _per_seed_values(baseline_runs)
                candidate_map = _per_seed_values(runs)
                shared_seeds = sorted(set(baseline_map) & set(candidate_map))
                if len(shared_seeds) < 2:
                    continue
                comparison = compare_paired_metric(
                    self.target.manifest.metric_name,
                    [baseline_map[s] for s in shared_seeds],
                    [candidate_map[s] for s in shared_seeds],
                    direction=-1 if self.target.manifest.lower_is_better else 1,
                    confidence=confidence,
                )
                payload = comparison.to_dict()
                payload["baseline"] = baseline_name
                payload["candidate"] = name
                comparisons.append(payload)
        sweep = BenchmarkSweep(
            target=str(self.target.root),
            metric=self.target.manifest.metric_name,
            lower_is_better=self.target.manifest.lower_is_better,
            summaries=summaries,
            comparisons=comparisons,
            partial=interrupted,
        )
        if interrupted:
            raise SweepInterrupted(sweep)
        return sweep

    # -- export ----------------------------------------------------------
    def _stem(self, sweep: BenchmarkSweep) -> str:
        # microsecond resolution: fast runs (cache hits, adaptive) in the same
        # second must not clobber each other's artifacts (V4 side-effect fix).
        # Q2.2: pid suffix — concurrent accelerates on one target stay disjoint.
        import os as _os

        return f"sweep-{int(sweep.started_at * 1_000_000)}-{_os.getpid()}"

    def export_json(self, sweep: BenchmarkSweep) -> Path:
        from .sweep_cache import _atomic_write_text

        path = self.export_dir / f"{self._stem(sweep)}.json"
        _atomic_write_text(path, json.dumps(sweep.to_dict(), indent=2, sort_keys=True))
        return path

    def export_csv(self, sweep: BenchmarkSweep) -> Path:
        from .sweep_cache import _atomic_write_text
        import io

        path = self.export_dir / f"{self._stem(sweep)}.csv"
        # StringIO(newline="") preserves csv.writer's CRLF dialect on every
        # platform; the completed bytes then cross the same atomic rename
        # boundary as JSON/Markdown/HTML exports.
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["candidate", "seed", "metric", "value", "seconds", "ok"])
        for summary in sweep.summaries:
            for run in summary.runs:
                writer.writerow([run.candidate, run.seed, run.metric, run.value, run.seconds, run.ok])
        _atomic_write_text(path, buffer.getvalue())
        return path

    def export_markdown(self, sweep: BenchmarkSweep) -> Path:
        from .sweep_cache import _atomic_write_text

        path = self.export_dir / f"{self._stem(sweep)}.md"
        lines = [f"# Benchmark sweep — {sweep.target}", ""]
        lines.append(f"Metric: `{sweep.metric}` ({'lower' if sweep.lower_is_better else 'higher'} is better)")
        lines.append("")
        lines.append("| candidate | mean | stddev | median | min | max | runs |")
        lines.append("|---|---|---|---|---|---|---|")
        for summary in sorted(sweep.summaries, key=lambda s: s.mean):
            lines.append(
                f"| {summary.candidate} | {summary.mean:.6g} | {summary.stddev:.3g} | "
                f"{summary.median:.6g} | {summary.minimum:.6g} | {summary.maximum:.6g} | {len(summary.runs)} |"
            )
        if sweep.comparisons:
            lines.append("")
            lines.append("## Paired comparisons (per-seed deltas, BCa CI + sign-flip p)")
            lines.append("")
            lines.append("| candidate | mean Δ | CI low | CI high | p | p (corr) | effect dz |")
            lines.append("|---|---|---|---|---|---|---|")
            for comparison in sweep.comparisons:
                corrected = comparison.get("p_value_corrected")
                corrected_str = f"{corrected:.4f}" if isinstance(corrected, float) else "—"
                lines.append(
                    f"| {comparison['candidate']} | {comparison['mean_delta']:.6g} | "
                    f"{comparison['ci_low']:.6g} | {comparison['ci_high']:.6g} | "
                    f"{comparison['p_value']:.4f} | {corrected_str} | {comparison['effect_dz']:.3f} |"
                )
        _atomic_write_text(path, "\n".join(lines) + "\n")
        return path

    def export_html(self, sweep: BenchmarkSweep, *, verdict: str = "") -> Path:
        from .report_html import html_from_sweep
        from .sweep_cache import _atomic_write_text

        path = self.export_dir / f"{self._stem(sweep)}.html"
        _atomic_write_text(path, html_from_sweep(sweep.to_dict(), verdict=verdict))
        return path


def _per_seed_values(runs: list[BenchmarkRun]) -> dict[int, float]:
    """Mean value per seed for a candidate (repeats collapse to a per-seed mean)."""
    buckets: dict[int, list[float]] = {}
    for run in runs:
        if not run.ok:
            continue
        buckets.setdefault(run.seed, []).append(run.value)
    return {seed: _mean(values) for seed, values in buckets.items()}
