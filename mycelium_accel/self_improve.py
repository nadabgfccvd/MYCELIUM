from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from statistics import mean
from time import monotonic, perf_counter
from typing import Any

from .acceleration import VARIANTS
from .config import Config
from .engine import MyceliumEngine
from .generated import active_variants
from .runtime_profile import load_default_profile
from .state import kill_switch_file


@dataclass(slots=True)
class GuardConfig:
    seeds: list[int]
    benchmark_rounds: int = 30
    min_speedup_ratio: float = 0.01
    max_best_score_drop: float = 0.0
    max_exact_rate_drop: float = 0.0
    max_solved_drop: float = 0.0
    max_capability_drop: float = 0.0
    max_frontier_drop: float = 0.35
    require_tests: bool = True
    parallel_workers: int = max(1, min(4, os.cpu_count() or 1))
    use_paired_stats: bool = True
    stats_confidence: float = 0.95
    stats_alpha: float = 0.05
    stats_quality_alpha: float = 0.10
    stats_min_pairs: int = 3
    stats_correction: str = "holm"
    screen_enabled: bool = True
    screen_rounds: int = 0  # 0 = auto: max(2, benchmark_rounds // 4)
    screen_seeds: int = 3
    screen_keep_top: int = 8


@dataclass(slots=True)
class BenchmarkSnapshot:
    profile: dict[str, Any]
    aggregate_variant: str
    rounds_per_second_mean: float
    best_score_mean: float
    best_exact_rate_mean: float
    solved_by_best_mean: float
    capability_signal_mean: float
    frontier_difficulty_mean: float
    active_niches_mean: float = 0.0
    diversity_entropy_mean: float = 0.0
    macro_transfer_mean: float = 0.0
    frontier_learning_progress_mean: float = 0.0
    growth_regimes: list[str] = field(default_factory=list)
    per_seed: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GuardDecision:
    accepted: bool
    reasons: list[str]
    paired_stats: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SelfImproveCycleResult:
    cycle_index: int
    rounds_executed: int
    applied: bool
    baseline: BenchmarkSnapshot
    candidate: BenchmarkSnapshot | None
    guard: GuardDecision
    # Explain every screened candidate without making the trail part of the
    # acceptance decision.  It is intentionally optional for old reports.
    screen_trail: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SelfImproveSummary:
    cycles_requested: int | None
    cycles_completed: int
    accepted_cycles: int
    rejected_cycles: int
    stopped_by_kill_switch: bool
    stopped_by_time_budget: bool
    time_budget_seconds: int | None
    elapsed_seconds: float
    report_path: str
    active_variant: str
    default_profile: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BenchmarkTask:
    project_root: str
    profile: dict[str, Any]
    aggregate_variant: str
    benchmark_rounds: int
    seed: int


def select_screen_survivors(
    screen_means: dict[Any, float],
    baseline_mean: float,
    *,
    min_speedup_ratio: float,
    keep_top: int,
) -> list[Any]:
    """Mean-based futility gate for the cheap screening stage.

    Drops candidates that cannot beat the throughput floor under the screen
    measurement, then keeps at most the fastest ``keep_top`` survivors. The
    rigorous paired-statistics guard still decides acceptance downstream —
    this stage only bounds benchmark cost (the "8h cycle" fix).
    """
    floor = baseline_mean * (1.0 + min_speedup_ratio)
    eligible = sorted(
        ((mean, key) for key, mean in screen_means.items() if mean >= floor),
        reverse=True,
    )
    return [key for _, key in eligible[: max(1, keep_top)]]


class SelfImprover:
    def __init__(self, project_root: Path, base_config: Config, guard: GuardConfig) -> None:
        self.project_root = project_root
        self.base_config = base_config
        self.guard = guard
        self.report_dir = project_root / ".mycelium_self_improve"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.status_path = self.report_dir / "daemon.status.json"
        self.error_path = self.report_dir / "last_error.json"
        self._last_search_trail: list[dict[str, Any]] = []

    def run(
        self,
        cycles: int,
        rounds_per_cycle: int,
        *,
        time_budget_seconds: int | None = None,
    ) -> SelfImproveSummary:
        return self._run_loop(
            cycles_limit=cycles,
            rounds_per_cycle=rounds_per_cycle,
            time_budget_seconds=time_budget_seconds,
            sleep_seconds=0.0,
            daemon=False,
        )

    def run_daemon(
        self,
        rounds_per_cycle: int,
        *,
        time_budget_seconds: int | None = None,
        sleep_seconds: float = 0.0,
        max_cycles: int | None = None,
    ) -> SelfImproveSummary:
        return self._run_loop(
            cycles_limit=max_cycles,
            rounds_per_cycle=rounds_per_cycle,
            time_budget_seconds=time_budget_seconds,
            sleep_seconds=sleep_seconds,
            daemon=True,
        )

    def _run_loop(  # noqa: C901 — Q3.2: phased round loop.
        self,
        *,
        cycles_limit: int | None,
        rounds_per_cycle: int,
        time_budget_seconds: int | None,
        sleep_seconds: float,
        daemon: bool,
    ) -> SelfImproveSummary:
        cycle_reports: list[dict[str, Any]] = []
        accepted_cycles = 0
        rejected_cycles = 0
        completed = 0
        stopped_by_kill = False
        stopped_by_time = False
        started_at = monotonic()
        deadline = started_at + time_budget_seconds if time_budget_seconds is not None else None
        self._status_time_budget = time_budget_seconds
        cycle_index = 1

        self._write_status(
            state="starting",
            phase="startup",
            cycle_index=0,
            cycles_completed=0,
            accepted_cycles=0,
            rejected_cycles=0,
            stopped_by_kill=False,
            stopped_by_time=False,
            time_budget_seconds=time_budget_seconds,
            active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
            default_profile=load_default_profile(),
        )

        try:
            while cycles_limit is None or completed < cycles_limit:
                if kill_switch_file(self.base_config.state_path).exists():
                    stopped_by_kill = True
                    break
                if deadline is not None and monotonic() >= deadline:
                    stopped_by_time = True
                    break

                result = self._run_single_cycle(cycle_index, rounds_per_cycle)
                cycle_reports.append(result.to_dict())
                completed += 1
                if result.applied:
                    accepted_cycles += 1
                else:
                    rejected_cycles += 1

                self._write_status(
                    state="running" if daemon else "completed_cycle",
                    phase="cycle_complete",
                    cycle_index=cycle_index,
                    cycles_completed=completed,
                    accepted_cycles=accepted_cycles,
                    rejected_cycles=rejected_cycles,
                    stopped_by_kill=False,
                    stopped_by_time=False,
                    time_budget_seconds=time_budget_seconds,
                    active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
                    default_profile=load_default_profile(),
                )

                cycle_index += 1
                if sleep_seconds > 0 and (cycles_limit is None or completed < cycles_limit):
                    slept = 0.0
                    while slept < sleep_seconds:
                        if kill_switch_file(self.base_config.state_path).exists():
                            stopped_by_kill = True
                            break
                        if deadline is not None and monotonic() >= deadline:
                            stopped_by_time = True
                            break
                        chunk = min(0.5, sleep_seconds - slept)
                        time.sleep(chunk)
                        slept += chunk
                    if stopped_by_kill or stopped_by_time:
                        break
        except Exception as exc:
            elapsed_seconds = monotonic() - started_at
            self._write_error(
                error_type=type(exc).__name__,
                error_message=str(exc),
                traceback_text=traceback.format_exc(),
                cycle_index=cycle_index,
                cycles_completed=completed,
                accepted_cycles=accepted_cycles,
                rejected_cycles=rejected_cycles,
                elapsed_seconds=elapsed_seconds,
            )
            self._write_status(
                state="error",
                phase="exception",
                cycle_index=cycle_index,
                cycles_completed=completed,
                accepted_cycles=accepted_cycles,
                rejected_cycles=rejected_cycles,
                stopped_by_kill=stopped_by_kill,
                stopped_by_time=stopped_by_time,
                time_budget_seconds=time_budget_seconds,
                active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
                default_profile=load_default_profile(),
                elapsed_seconds=elapsed_seconds,
                error_type=type(exc).__name__,
                error_message=str(exc),
                error_path=str(self.error_path),
            )
            raise

        elapsed_seconds = monotonic() - started_at
        report_path = self._write_report(cycle_reports)
        self._write_status(
            state="stopped",
            phase="finished",
            cycle_index=cycle_index if completed else 0,
            cycles_completed=completed,
            accepted_cycles=accepted_cycles,
            rejected_cycles=rejected_cycles,
            stopped_by_kill=stopped_by_kill,
            stopped_by_time=stopped_by_time,
            time_budget_seconds=time_budget_seconds,
            active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
            default_profile=load_default_profile(),
            report_path=str(report_path),
            elapsed_seconds=elapsed_seconds,
        )
        return SelfImproveSummary(
            cycles_requested=cycles_limit,
            cycles_completed=completed,
            accepted_cycles=accepted_cycles,
            rejected_cycles=rejected_cycles,
            stopped_by_kill_switch=stopped_by_kill,
            stopped_by_time_budget=stopped_by_time,
            time_budget_seconds=time_budget_seconds,
            elapsed_seconds=elapsed_seconds,
            report_path=str(report_path),
            active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
            default_profile=load_default_profile(),
        )

    def _run_single_cycle(self, cycle_index: int, rounds_per_cycle: int) -> SelfImproveCycleResult:
        self._write_status(
            state="running",
            phase="evolution",
            cycle_index=cycle_index,
            rounds_per_cycle=rounds_per_cycle,
            cycles_completed=max(0, cycle_index - 1),
            accepted_cycles=None,
            rejected_cycles=None,
            stopped_by_kill=False,
            stopped_by_time=False,
            time_budget_seconds=getattr(self, "_status_time_budget", None),
            active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
            default_profile=load_default_profile(),
        )
        engine = MyceliumEngine(self.base_config)
        rounds_summary = engine.run(rounds_per_cycle)

        self._write_status(
            state="running",
            phase="benchmark_baseline",
            cycle_index=cycle_index,
            rounds_per_cycle=rounds_per_cycle,
            last_rounds_executed=rounds_summary.rounds_executed,
            cycles_completed=max(0, cycle_index - 1),
            accepted_cycles=None,
            rejected_cycles=None,
            stopped_by_kill=False,
            stopped_by_time=False,
            time_budget_seconds=getattr(self, "_status_time_budget", None),
            active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
            default_profile=load_default_profile(),
        )
        baseline = self._benchmark_current_selection()

        self._write_status(
            state="running",
            phase="search_candidate",
            cycle_index=cycle_index,
            rounds_per_cycle=rounds_per_cycle,
            baseline_rounds_per_second=baseline.rounds_per_second_mean,
            baseline_capability_signal=baseline.capability_signal_mean,
            cycles_completed=max(0, cycle_index - 1),
            accepted_cycles=None,
            rejected_cycles=None,
            stopped_by_kill=False,
            stopped_by_time=False,
            time_budget_seconds=getattr(self, "_status_time_budget", None),
            active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
            default_profile=load_default_profile(),
        )
        # Reset before every search.  A mocked/short-circuited search must
        # never attach the previous cycle's explanation trail.
        self._last_search_trail = []
        candidate = self._search_best_candidate(baseline)
        if candidate is None:
            decision = GuardDecision(False, ["No candidate exceeded the guarded baseline."])
            return SelfImproveCycleResult(
                cycle_index=cycle_index,
                rounds_executed=rounds_summary.rounds_executed,
                applied=False,
                baseline=baseline,
                candidate=None,
                guard=decision,
                screen_trail=[],
            )

        decision = compare_snapshots(baseline, candidate, self.guard)
        applied = False
        if decision.accepted:
            self._write_status(
                state="running",
                phase="apply_candidate",
                cycle_index=cycle_index,
                rounds_per_cycle=rounds_per_cycle,
                candidate_profile=candidate.profile,
                candidate_rounds_per_second=candidate.rounds_per_second_mean,
                cycles_completed=max(0, cycle_index - 1),
                accepted_cycles=None,
                rejected_cycles=None,
                stopped_by_kill=False,
                stopped_by_time=False,
                time_budget_seconds=getattr(self, "_status_time_budget", None),
                active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
                default_profile=load_default_profile(),
            )
            self._persist_runtime_selection(candidate.aggregate_variant, candidate.profile)
            if self.guard.require_tests:
                self._write_status(
                    state="running",
                    phase="regression_tests",
                    cycle_index=cycle_index,
                    rounds_per_cycle=rounds_per_cycle,
                    cycles_completed=max(0, cycle_index - 1),
                    accepted_cycles=None,
                    rejected_cycles=None,
                    stopped_by_kill=False,
                    stopped_by_time=False,
                    time_budget_seconds=getattr(self, "_status_time_budget", None),
                    active_variant=active_variants.AGGREGATE_SCORES_VARIANT,
                    default_profile=load_default_profile(),
                )
                tests = self._run_regression_suite()
                if tests.returncode != 0:
                    self._restore_runtime_selection(baseline.aggregate_variant, baseline.profile)
                    decision = GuardDecision(
                        False,
                        decision.reasons + ["Regression suite failed after applying candidate."],
                    )
                else:
                    applied = True
            else:
                applied = True
        if not applied:
            self._restore_runtime_selection(baseline.aggregate_variant, baseline.profile)
        return SelfImproveCycleResult(
            cycle_index=cycle_index,
            rounds_executed=rounds_summary.rounds_executed,
            applied=applied,
            baseline=baseline,
            candidate=candidate,
            guard=decision,
            screen_trail=list(self._last_search_trail),
        )

    def _benchmark_current_selection(self) -> BenchmarkSnapshot:
        return self._benchmark_profile(load_default_profile(), active_variants.AGGREGATE_SCORES_VARIANT)

    def _search_best_candidate(self, baseline: BenchmarkSnapshot) -> BenchmarkSnapshot | None:
        tasks = []
        seen: set[tuple[str, tuple[tuple[str, Any], ...]]] = set()
        current_profile = baseline.profile
        current_variant = baseline.aggregate_variant

        for variant in VARIANTS:
            for profile in generate_candidate_profiles(current_profile):
                key = (variant, tuple(sorted(profile.items())))
                if key in seen:
                    continue
                seen.add(key)
                if variant == current_variant and profile == current_profile:
                    continue
                tasks.append((variant, profile))

        snapshots = self._benchmark_candidates_parallel(tasks)
        self._last_search_trail = []
        best_candidate: BenchmarkSnapshot | None = None
        for snapshot in snapshots:
            decision = compare_snapshots(baseline, snapshot, self.guard)
            profile_diff = {
                key: snapshot.profile.get(key)
                for key in set(baseline.profile) | set(snapshot.profile)
                if baseline.profile.get(key) != snapshot.profile.get(key)
            }
            self._last_search_trail.append({
                "variant": snapshot.aggregate_variant,
                "profile_diff": profile_diff,
                "rounds_per_second_mean": snapshot.rounds_per_second_mean,
                "accepted": decision.accepted,
                "reasons": list(decision.reasons),
            })
            if not decision.accepted:
                continue
            if best_candidate is None or snapshot.rounds_per_second_mean > best_candidate.rounds_per_second_mean:
                best_candidate = snapshot
        return best_candidate

    def _benchmark_profile(self, profile: dict[str, Any], aggregate_variant: str) -> BenchmarkSnapshot:
        tasks = [
            BenchmarkTask(
                project_root=str(self.project_root),
                profile=dict(profile),
                aggregate_variant=aggregate_variant,
                benchmark_rounds=self.guard.benchmark_rounds,
                seed=seed,
            )
            for seed in self.guard.seeds
        ]
        per_seed = self._run_benchmark_tasks(tasks)
        return _snapshot_from_results(profile, aggregate_variant, per_seed)

    def _screen_tasks(self, candidates: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
        """Cheap screening stage: prune the candidate list before full benchmarks.

        Regression for the "one cycle never finishes in 8h" failure: wide
        candidate generations (~30-40 profiles) were getting the full
        7-seed × 30-round measurement. Here we measure everything with fewer
        rounds/seeds, drop candidates under the mean-based futility floor,
        and keep at most ``guard.screen_keep_top`` survivors for the rigorous
        paired benchmark.
        """
        guard = self.guard
        candidates = list(candidates)
        if not guard.screen_enabled or len(candidates) <= guard.screen_keep_top:
            return candidates

        screen_seeds = guard.seeds[: max(1, min(guard.screen_seeds, len(guard.seeds)))]
        screen_rounds = guard.screen_rounds if guard.screen_rounds > 0 else max(2, guard.benchmark_rounds // 4)

        reference_profile = load_default_profile()
        reference_tasks = [
            BenchmarkTask(
                project_root=str(self.project_root),
                profile=dict(reference_profile),
                aggregate_variant=active_variants.AGGREGATE_SCORES_VARIANT,
                benchmark_rounds=screen_rounds,
                seed=seed,
            )
            for seed in screen_seeds
        ]
        candidate_tasks = [
            BenchmarkTask(
                project_root=str(self.project_root),
                profile=dict(profile),
                aggregate_variant=aggregate_variant,
                benchmark_rounds=screen_rounds,
                seed=seed,
            )
            for aggregate_variant, profile in candidates
            for seed in screen_seeds
        ]

        reference_results = self._run_benchmark_tasks(reference_tasks)
        candidate_results = self._run_benchmark_tasks(candidate_tasks)
        baseline_mean = mean(item["rounds_per_second"] for item in reference_results)

        grouped: dict[tuple[str, tuple[tuple[str, Any], ...]], list[float]] = {}
        for item in candidate_results:
            key = (item["aggregate_variant"], tuple(sorted(item["profile"].items())))
            grouped.setdefault(key, []).append(item["rounds_per_second"])
        screen_means = {key: mean(values) for key, values in grouped.items()}
        survivor_keys = set(
            select_screen_survivors(
                screen_means,
                baseline_mean,
                min_speedup_ratio=guard.min_speedup_ratio,
                keep_top=guard.screen_keep_top,
            )
        )
        return [
            (aggregate_variant, profile)
            for aggregate_variant, profile in candidates
            if (aggregate_variant, tuple(sorted(profile.items()))) in survivor_keys
        ]

    def _benchmark_candidates_parallel(self, candidates: list[tuple[str, dict[str, Any]]]) -> list[BenchmarkSnapshot]:
        candidates = self._screen_tasks(candidates)
        if not candidates:
            return []
        seed_count = len(self.guard.seeds)
        tasks: list[BenchmarkTask] = []
        for aggregate_variant, profile in candidates:
            for seed in self.guard.seeds:
                tasks.append(
                    BenchmarkTask(
                        project_root=str(self.project_root),
                        profile=dict(profile),
                        aggregate_variant=aggregate_variant,
                        benchmark_rounds=self.guard.benchmark_rounds,
                        seed=seed,
                    )
                )
        results = self._run_benchmark_tasks(tasks)
        grouped: dict[tuple[str, tuple[tuple[str, Any], ...]], list[dict[str, Any]]] = {}
        profile_lookup: dict[tuple[str, tuple[tuple[str, Any], ...]], dict[str, Any]] = {}
        for item in results:
            key = (item["aggregate_variant"], tuple(sorted(item["profile"].items())))
            grouped.setdefault(key, []).append(item)
            profile_lookup[key] = item["profile"]

        snapshots: list[BenchmarkSnapshot] = []
        for key, per_seed in grouped.items():
            if len(per_seed) != seed_count:
                continue
            aggregate_variant = key[0]
            profile = profile_lookup[key]
            snapshots.append(_snapshot_from_results(profile, aggregate_variant, per_seed))
        return snapshots

    def _run_benchmark_tasks(self, tasks: list[BenchmarkTask]) -> list[dict[str, Any]]:
        if not tasks:
            return []
        worker_count = max(1, min(self.guard.parallel_workers, len(tasks)))
        if worker_count == 1:
            return [_run_benchmark_task(task) for task in tasks]

        results: list[dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = [pool.submit(_run_benchmark_task, task) for task in tasks]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def _persist_runtime_selection(self, aggregate_variant: str, profile: dict[str, Any]) -> None:
        write_active_variant(self.project_root, aggregate_variant)
        write_default_profile(self.project_root, profile)
        active_variants.AGGREGATE_SCORES_VARIANT = aggregate_variant

    def _restore_runtime_selection(self, aggregate_variant: str, profile: dict[str, Any]) -> None:
        self._persist_runtime_selection(aggregate_variant, profile)

    def _run_regression_suite(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.project_root,
            check=False,
            capture_output=True,
            text=True,
        )

    def _write_report(self, cycles: list[dict[str, Any]]) -> Path:
        path = self.report_dir / f"self-improve-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "cycles": cycles,
            "active_variant": active_variants.AGGREGATE_SCORES_VARIANT,
            "default_profile": load_default_profile(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        latest = self.report_dir / "latest.json"
        latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_status(self, **payload: Any) -> None:
        status_payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            **payload,
        }
        self.status_path.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_error(self, **payload: Any) -> None:
        error_payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            **payload,
        }
        self.error_path.write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_benchmark_task(task: BenchmarkTask) -> dict[str, Any]:
    if task.project_root not in sys.path:
        sys.path.insert(0, task.project_root)
    from mycelium_accel.config import Config as WorkerConfig
    from mycelium_accel.engine import MyceliumEngine as WorkerEngine
    from mycelium_accel.generated import active_variants as worker_active_variants
    from mycelium_accel.state import load_state as worker_load_state

    worker_active_variants.AGGREGATE_SCORES_VARIANT = task.aggregate_variant
    temp_dir = tempfile.mkdtemp(prefix="mycelium-self-improve-")
    try:
        state_dir = Path(temp_dir) / "state"
        config = WorkerConfig(seed=task.seed, state_dir=str(state_dir), **task.profile)
        engine = WorkerEngine(config)
        engine.init_state()
        started = perf_counter()
        summary = engine.run(task.benchmark_rounds)
        elapsed = perf_counter() - started
        state = worker_load_state(state_dir, config.persistence_backend)
        metric = state.metrics_history[-1]
        return {
            "seed": task.seed,
            "profile": dict(task.profile),
            "aggregate_variant": task.aggregate_variant,
            "rounds_per_second": summary.rounds_executed / elapsed,
            "best_score": metric["best_score"],
            "best_exact_rate": metric["best_exact_rate"],
            "solved_by_best": metric["solved_by_best"],
            "capability_signal": metric["capability_signal"],
            "frontier_difficulty": metric["frontier_difficulty"],
            "active_niches": metric.get("active_niches", 0),
            "diversity_entropy": metric.get("diversity_entropy", 0.0),
            "macro_transfer_mean": metric.get("macro_transfer_mean", 0.0),
            "frontier_learning_progress": metric.get("frontier_learning_progress", 0.0),
            "growth_regime": summary.growth_regime,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _snapshot_from_results(
    profile: dict[str, Any],
    aggregate_variant: str,
    per_seed: list[dict[str, Any]],
) -> BenchmarkSnapshot:
    ordered = sorted(per_seed, key=lambda item: int(item["seed"]))
    return BenchmarkSnapshot(
        profile=dict(profile),
        aggregate_variant=aggregate_variant,
        rounds_per_second_mean=mean(item["rounds_per_second"] for item in ordered),
        best_score_mean=mean(item["best_score"] for item in ordered),
        best_exact_rate_mean=mean(item["best_exact_rate"] for item in ordered),
        solved_by_best_mean=mean(item["solved_by_best"] for item in ordered),
        capability_signal_mean=mean(item["capability_signal"] for item in ordered),
        frontier_difficulty_mean=mean(item["frontier_difficulty"] for item in ordered),
        active_niches_mean=mean(item.get("active_niches", 0) for item in ordered),
        diversity_entropy_mean=mean(item.get("diversity_entropy", 0.0) for item in ordered),
        macro_transfer_mean=mean(item.get("macro_transfer_mean", 0.0) for item in ordered),
        frontier_learning_progress_mean=mean(item.get("frontier_learning_progress", 0.0) for item in ordered),
        growth_regimes=[str(item["growth_regime"]) for item in ordered],
        per_seed=ordered,
    )


def compare_snapshots(baseline: BenchmarkSnapshot, candidate: BenchmarkSnapshot, guard: GuardConfig) -> GuardDecision:
    """Compare two benchmark snapshots.

    When ``guard.use_paired_stats`` is enabled and both snapshots carry at
    least ``stats_min_pairs`` *matched* per-seed rows, the decision is made by
    the paired-statistics engine (BCa bootstrap CI on per-seed deltas plus
    sign-flip permutation tests with multiple-testing correction). Otherwise
    it falls back to the legacy fixed-threshold comparison so that thin
    benchmarks still produce a decision.
    """
    baseline_seeds = {int(row["seed"]) for row in baseline.per_seed}
    candidate_seeds = {int(row["seed"]) for row in candidate.per_seed}
    shared_seeds = sorted(baseline_seeds & candidate_seeds)
    enough_pairs = len(shared_seeds) >= guard.stats_min_pairs
    if guard.use_paired_stats and enough_pairs:
        return _compare_snapshots_paired(baseline, candidate, guard, shared_seeds)
    return _compare_snapshots_fixed(baseline, candidate, guard)


def _paired_column(rows: list[dict[str, Any]], metric: str, seeds: list[int]) -> list[float]:
    by_seed = {int(row["seed"]): float(row[metric]) for row in rows}
    return [by_seed[seed] for seed in seeds]


def _compare_snapshots_paired(
    baseline: BenchmarkSnapshot,
    candidate: BenchmarkSnapshot,
    guard: GuardConfig,
    shared_seeds: list[int],
) -> GuardDecision:
    from .stats import apply_correction, compare_paired_metric

    reasons: list[str] = [f"Paired statistics over {len(shared_seeds)} matched seeds."]
    stats_payload: list[dict[str, Any]] = []

    # Primary improvement claim: relative per-seed speedup ratio vs margin.
    from .stats import sign_flip_permutation_test

    baseline_speed = _paired_column(baseline.per_seed, "rounds_per_second", shared_seeds)
    candidate_speed = _paired_column(candidate.per_seed, "rounds_per_second", shared_seeds)
    relative_speedup = [c / b - 1.0 for b, c in zip(baseline_speed, candidate_speed)]
    speed_cmp = compare_paired_metric(
        "relative_speedup",
        [0.0] * len(relative_speedup),
        relative_speedup,
        direction=1,
        confidence=guard.stats_confidence,
        alternative="greater",  # pre-registered improvement claim
    )

    quality_specs: list[tuple[str, float]] = [
        ("best_score", guard.max_best_score_drop),
        ("best_exact_rate", guard.max_exact_rate_drop),
        ("solved_by_best", guard.max_solved_drop),
        ("capability_signal", guard.max_capability_drop),
        ("frontier_difficulty", guard.max_frontier_drop),
    ]
    quality_comparisons = []
    regression_alarms: list[tuple[str, float, float]] = []  # (metric, mean_delta, p_alarm)
    for metric, max_drop in quality_specs:
        base_col = _paired_column(baseline.per_seed, metric, shared_seeds)
        cand_col = _paired_column(candidate.per_seed, metric, shared_seeds)
        comparison = compare_paired_metric(
            metric,
            base_col,
            cand_col,
            direction=1,
            confidence=guard.stats_confidence,
        )
        quality_comparisons.append((comparison, max_drop))
        # one-sided regression alarm: p that the *not negated* deltas are worse
        p_alarm = sign_flip_permutation_test(
            [-delta for delta in comparison.deltas],
            alternative="greater",
        )
        regression_alarms.append((metric, comparison.mean_delta, p_alarm))

    # The alpha-spending family is the improvement claim (correction applies
    # across candidate claims; quality guards use their own alarm alpha).
    apply_correction([speed_cmp], method=guard.stats_correction)

    throughput_ok = True
    if speed_cmp.ci_low <= guard.min_speedup_ratio:
        throughput_ok = False
        reasons.append(
            f"Throughput: CI lower bound {speed_cmp.ci_low:.4f} <= required {guard.min_speedup_ratio:.4f} relative gain."
        )
    if speed_cmp.p_value_corrected is not None and speed_cmp.p_value_corrected > guard.stats_alpha:
        throughput_ok = False
        reasons.append(
            f"Throughput: one-sided p {speed_cmp.p_value_corrected:.4f} > alpha {guard.stats_alpha}."
        )
    stats_payload.append(speed_cmp.to_dict())

    quality_ok = True
    for (comparison, max_drop), (metric, alarm_mean, p_alarm) in zip(quality_comparisons, regression_alarms):
        payload = comparison.to_dict()
        payload["p_regression_alarm"] = p_alarm
        stats_payload.append(payload)
        if comparison.ci_low < -max_drop:
            quality_ok = False
            reasons.append(
                f"{comparison.metric}: CI lower bound {comparison.ci_low:.4f} < -{max_drop:.4f} (regression not excluded)."
            )
        if alarm_mean < -max_drop and p_alarm <= guard.stats_quality_alpha:
            quality_ok = False
            reasons.append(
                f"{comparison.metric}: mean delta {alarm_mean:.4f} < -{max_drop:.4f} with one-sided regression p {p_alarm:.4f} <= {guard.stats_quality_alpha}."
            )

    accepted = throughput_ok and quality_ok
    if accepted:
        reasons.append(
            f"Candidate accepted: relative speedup CI [{speed_cmp.ci_low:.4f}, {speed_cmp.ci_high:.4f}], "
            f"corrected p {speed_cmp.p_value_corrected:.4f}; all quality guards within tolerance."
        )
    return GuardDecision(accepted=accepted, reasons=reasons, paired_stats=stats_payload)


def _compare_snapshots_fixed(baseline: BenchmarkSnapshot, candidate: BenchmarkSnapshot, guard: GuardConfig) -> GuardDecision:
    reasons: list[str] = []
    speed_floor = baseline.rounds_per_second_mean * (1.0 + guard.min_speedup_ratio)
    if candidate.rounds_per_second_mean < speed_floor:
        reasons.append(
            f"Throughput regression or insufficient gain: {candidate.rounds_per_second_mean:.2f} < {speed_floor:.2f} rounds/s required."
        )
    if candidate.best_score_mean < baseline.best_score_mean - guard.max_best_score_drop:
        reasons.append(
            f"best_score_mean regressed: {candidate.best_score_mean:.4f} < {baseline.best_score_mean - guard.max_best_score_drop:.4f}."
        )
    if candidate.best_exact_rate_mean < baseline.best_exact_rate_mean - guard.max_exact_rate_drop:
        reasons.append(
            f"best_exact_rate_mean regressed: {candidate.best_exact_rate_mean:.4f} < {baseline.best_exact_rate_mean - guard.max_exact_rate_drop:.4f}."
        )
    if candidate.solved_by_best_mean < baseline.solved_by_best_mean - guard.max_solved_drop:
        reasons.append(
            f"solved_by_best_mean regressed: {candidate.solved_by_best_mean:.4f} < {baseline.solved_by_best_mean - guard.max_solved_drop:.4f}."
        )
    if candidate.capability_signal_mean < baseline.capability_signal_mean - guard.max_capability_drop:
        reasons.append(
            f"capability_signal_mean regressed: {candidate.capability_signal_mean:.4f} < {baseline.capability_signal_mean - guard.max_capability_drop:.4f}."
        )
    if candidate.frontier_difficulty_mean < baseline.frontier_difficulty_mean - guard.max_frontier_drop:
        reasons.append(
            f"frontier_difficulty_mean regressed: {candidate.frontier_difficulty_mean:.4f} < {baseline.frontier_difficulty_mean - guard.max_frontier_drop:.4f}."
        )
    return GuardDecision(accepted=not reasons, reasons=reasons or ["Candidate passed all guard checks."])


def generate_candidate_profiles(current: dict[str, Any]) -> list[dict[str, Any]]:
    family_count = int(current["family_count"])
    family_size = int(current["family_size"])
    train_cases = int(current["train_cases"])
    test_cases = int(current["test_cases"])
    probe_train = int(current["probe_train_cases"])
    probe_test = int(current["probe_test_cases"])
    top_k = int(current["full_rescore_top_k"])
    random_k = int(current["full_rescore_random_k"])
    checkpoint_every = int(current["checkpoint_every"])
    state_save_every = int(current["state_save_every"])
    persistence_backend = str(current.get("persistence_backend", "json"))
    novelty_weight = float(current.get("novelty_weight", 0.04))
    macro_potential_weight = float(current.get("macro_potential_weight", 0.03))
    transfer_weight = float(current.get("transfer_weight", 0.03))
    macro_support_threshold = int(current.get("macro_support_threshold", 2))
    macro_transfer_threshold = float(current.get("macro_transfer_threshold", 0.12))
    compositional_challenge_rate = float(current.get("compositional_challenge_rate", 0.34))
    gene_splice_rate = float(current.get("gene_splice_rate", 0.25))
    shrink_mutation_rate = float(current.get("shrink_mutation_rate", 0.12))

    candidates: list[dict[str, Any]] = []
    candidate_specs: list[dict[str, Any]] = [
        {},
        {"checkpoint_every": max(checkpoint_every, 15), "state_save_every": max(state_save_every, 15)},
        {"checkpoint_every": max(checkpoint_every, 20), "state_save_every": max(state_save_every, 20)},
        {"probe_train_cases": max(1, probe_train - 1), "probe_test_cases": max(1, probe_test - 1)},
        {"probe_train_cases": min(train_cases, probe_train + 1), "probe_test_cases": min(test_cases, probe_test + 2)},
        {"full_rescore_top_k": max(1, top_k - 1)},
        {"full_rescore_top_k": min(family_size, top_k + 1)},
        {"full_rescore_random_k": 0},
        {"full_rescore_random_k": min(max(0, family_size - 1), random_k + 1)},
        {"family_size": max(10, family_size - 1), "full_rescore_top_k": min(max(10, family_size - 1), top_k)},
        {"family_size": family_size + 1, "full_rescore_top_k": min(family_size + 1, top_k + 1)},
        {"family_count": max(5, family_count - 1)},
        {"family_count": family_count + 1},
        {
            "family_count": max(5, family_count - 1),
            "family_size": family_size + 1,
            "full_rescore_top_k": min(family_size + 1, top_k + 1),
        },
        {
            "family_count": family_count,
            "family_size": family_size,
            "probe_train_cases": max(1, probe_train - 1),
            "probe_test_cases": max(1, probe_test - 1),
            "checkpoint_every": max(checkpoint_every, 15),
            "state_save_every": max(state_save_every, 15),
        },
        {"persistence_backend": "pickle" if persistence_backend == "json" else "json"},
        {
            "persistence_backend": "pickle" if persistence_backend == "json" else persistence_backend,
            "checkpoint_every": max(checkpoint_every, 15),
            "state_save_every": max(state_save_every, 15),
        },
        {"novelty_weight": max(0.0, novelty_weight - 0.01)},
        {"novelty_weight": novelty_weight + 0.01},
        {"macro_potential_weight": max(0.0, macro_potential_weight - 0.01)},
        {"macro_potential_weight": macro_potential_weight + 0.01},
        {"transfer_weight": max(0.0, transfer_weight - 0.01)},
        {"transfer_weight": transfer_weight + 0.01},
        {"macro_support_threshold": max(1, macro_support_threshold - 1)},
        {"macro_support_threshold": macro_support_threshold + 1},
        {"macro_transfer_threshold": max(0.0, macro_transfer_threshold - 0.03)},
        {"macro_transfer_threshold": macro_transfer_threshold + 0.03},
        {"compositional_challenge_rate": max(0.0, compositional_challenge_rate - 0.10)},
        {"compositional_challenge_rate": min(1.0, compositional_challenge_rate + 0.10)},
        {"gene_splice_rate": max(0.0, gene_splice_rate - 0.05)},
        {"gene_splice_rate": min(1.0, gene_splice_rate + 0.05)},
        {"shrink_mutation_rate": max(0.0, shrink_mutation_rate - 0.04)},
        {"shrink_mutation_rate": min(1.0, shrink_mutation_rate + 0.04)},
        {
            "persistence_backend": "pickle" if persistence_backend == "json" else persistence_backend,
            "novelty_weight": novelty_weight + 0.01,
            "transfer_weight": transfer_weight + 0.01,
            "compositional_challenge_rate": min(1.0, compositional_challenge_rate + 0.10),
        },
        {
            "gene_splice_rate": min(1.0, gene_splice_rate + 0.05),
            "shrink_mutation_rate": max(0.0, shrink_mutation_rate - 0.04),
            "macro_support_threshold": max(1, macro_support_threshold - 1),
        },
    ]

    seen: set[tuple[tuple[str, Any], ...]] = set()
    for overrides in candidate_specs:
        profile = dict(current)
        profile.update(overrides)
        profile["probe_train_cases"] = min(int(profile["probe_train_cases"]), int(profile["train_cases"]))
        profile["probe_test_cases"] = min(int(profile["probe_test_cases"]), int(profile["test_cases"]))
        profile["family_count"] = max(5, int(profile["family_count"]))
        profile["family_size"] = max(10, int(profile["family_size"]))
        profile["full_rescore_top_k"] = min(int(profile["family_size"]), max(1, int(profile["full_rescore_top_k"])))
        profile["full_rescore_random_k"] = min(max(0, int(profile["full_rescore_random_k"])), int(profile["family_size"]))
        profile["checkpoint_every"] = max(1, int(profile["checkpoint_every"]))
        profile["state_save_every"] = max(1, int(profile["state_save_every"]))
        profile["persistence_backend"] = str(profile.get("persistence_backend", "json"))
        profile["novelty_weight"] = max(0.0, float(profile.get("novelty_weight", 0.04)))
        profile["macro_potential_weight"] = max(0.0, float(profile.get("macro_potential_weight", 0.03)))
        profile["transfer_weight"] = max(0.0, float(profile.get("transfer_weight", 0.03)))
        profile["macro_support_threshold"] = max(1, int(profile.get("macro_support_threshold", 2)))
        profile["macro_transfer_threshold"] = max(0.0, float(profile.get("macro_transfer_threshold", 0.12)))
        profile["compositional_challenge_rate"] = min(1.0, max(0.0, float(profile.get("compositional_challenge_rate", 0.34))))
        profile["gene_splice_rate"] = min(1.0, max(0.0, float(profile.get("gene_splice_rate", 0.25))))
        profile["shrink_mutation_rate"] = min(1.0, max(0.0, float(profile.get("shrink_mutation_rate", 0.12))))
        key = tuple(sorted(profile.items()))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(profile)
    return candidates


def write_active_variant(project_root: Path, aggregate_variant: str) -> Path:
    path = project_root / "mycelium_accel" / "generated" / "active_variants.py"
    path.write_text(
        '"""Auto-updated by the accelerator. Commit this file so optimized choices persist."""\n\n'
        f'AGGREGATE_SCORES_VARIANT = "{aggregate_variant}"\n',
        encoding="utf-8",
    )
    return path


def write_default_profile(project_root: Path, profile: dict[str, Any]) -> Path:
    path = project_root / "mycelium_accel" / "generated" / "default_profile.py"
    lines = [
        '"""Auto-updated runtime profile selected by self-improvement mode."""',
        "",
        "DEFAULT_PROFILE = {",
    ]
    for key in sorted(profile):
        lines.append(f"    {key!r}: {profile[key]!r},")
    lines.append("}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_guard_from_args(args: Any) -> GuardConfig:
    seeds = [int(item.strip()) for item in str(args.benchmark_seeds).split(",") if item.strip()]
    return GuardConfig(
        seeds=seeds,
        benchmark_rounds=args.benchmark_rounds,
        min_speedup_ratio=args.min_speedup_ratio,
        max_best_score_drop=args.max_best_score_drop,
        max_exact_rate_drop=args.max_exact_rate_drop,
        max_solved_drop=args.max_solved_drop,
        max_capability_drop=args.max_capability_drop,
        max_frontier_drop=args.max_frontier_drop,
        require_tests=not args.skip_tests,
        parallel_workers=max(1, int(args.guard_workers)),
        use_paired_stats=not getattr(args, "no_paired_stats", False),
        stats_confidence=getattr(args, "stats_confidence", 0.95),
        stats_alpha=getattr(args, "stats_alpha", 0.05),
        stats_quality_alpha=getattr(args, "stats_quality_alpha", 0.10),
        stats_min_pairs=getattr(args, "stats_min_pairs", 3),
        stats_correction=getattr(args, "stats_correction", "holm"),
        screen_enabled=not getattr(args, "no_screen", False),
        screen_rounds=max(0, int(getattr(args, "screen_rounds", 0))),
        screen_seeds=max(1, int(getattr(args, "screen_seeds", 3))),
        screen_keep_top=max(1, int(getattr(args, "screen_keep_top", 8))),
    )
