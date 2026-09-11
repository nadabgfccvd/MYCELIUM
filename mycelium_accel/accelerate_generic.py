"""Generic project acceleration orchestrator (Roadmap Phase 1 + Phase 2).

Pipeline for an arbitrary target directory:

1. load manifest / detect conventions;
2. build once (if declared);
3. run the project test suite (if declared) — variants must keep it green;
4. benchmark baseline and all variants under the *same* paired seeds;
5. decide with the paired-statistics engine (BCa CI lower bound > 0 and
   corrected permutation p <= alpha), then persist the winner (for
   file-modifying variants, re-apply and keep; everything is rolled back on
   failure, and a record is written under ``.mycelium_benchmarks/``).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .bench import BenchmarkExecutor, BenchmarkSweep, SweepInterrupted
from .prime import next_prime
from .stats import AcceptancePolicy, apply_correction, compare_paired_metric
from .targets import load_target


@dataclass(slots=True)
class GenericAccelerationOutcome:
    target: str
    baseline: str
    best_candidate: str | None
    applied: bool
    decision_reasons: list[str]
    sweep_path: str | None
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    raced_candidates: list[str] = field(default_factory=list)
    regression: bool = False
    cached: bool = False
    interrupted: bool = False  # Q2.1: Ctrl-C short-cut the sweep

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _paired_values_by_seed(sweep: BenchmarkSweep, candidate: str) -> dict[int, float]:
    for summary in sweep.summaries:
        if summary.candidate != candidate:
            continue
        buckets: dict[int, list[float]] = {}
        for run in summary.runs:
            if run.ok:
                buckets.setdefault(run.seed, []).append(run.value)
        return {seed: sum(values) / len(values) for seed, values in buckets.items()}
    return {}


def decide_best_candidate(
    sweep: BenchmarkSweep,
    baseline: str,
    *,
    policy: AcceptancePolicy | None = None,
) -> tuple[str | None, list[str], list[dict[str, Any]]]:
    """Conservative winner picking under paired statistics.

    A candidate wins only if the BCa CI lower bound of its per-seed delta
    against the baseline is strictly positive (better) AND the corrected
    permutation p-value passes alpha. Among eligible candidates the one with
    the largest CI lower bound wins.
    """
    policy = policy or AcceptancePolicy()
    baseline_values = _paired_values_by_seed(sweep, baseline)
    if not baseline_values:
        return None, [f"Baseline '{baseline}' produced no successful runs."], []

    # Ciclo 1 (S2): a baseline with zero challengers is the common first-run
    # state (auto-detected manifest). Say so, and what to do next — do not
    # pretend the comparison "lacked paired data" (there is nothing to pair).
    challengers = [s.candidate for s in sweep.summaries if s.candidate != baseline]
    if not challengers:
        return None, [
            "No variants to compare: the manifest defines only a baseline, so "
            "there is nothing to accelerate yet. Add one or more 'variants' to "
            "mycelium.target.json (or run 'mycelium-accel accelerate init' to "
            "scaffold a manifest you can edit)."
        ], []

    reasons: list[str] = []
    comparisons_payload: list[dict[str, Any]] = []
    comparisons, candidate_names = _build_challenger_comparisons(
        sweep, baseline, baseline_values, policy, reasons)

    if not comparisons:
        return None, reasons or ["No candidate had enough paired data."], comparisons_payload

    apply_correction(comparisons, method=policy.correction)
    winners: list[tuple[float, str]] = []
    for name, comparison in zip(candidate_names, comparisons):
        payload = comparison.to_dict()
        payload["candidate"] = name
        payload["baseline"] = baseline
        comparisons_payload.append(payload)
        verdict = _acceptance_verdict(name, comparison, policy)
        if verdict is not None:
            reasons.append(verdict)
            continue
        winners.append((comparison.ci_low, name))

    if not winners:
        return None, reasons, comparisons_payload
    winners.sort(reverse=True)
    best_name = winners[0][1]
    reasons.insert(0, f"{best_name} accepted: CI lower bound {winners[0][0]:.6g} > 0 with corrected p <= {policy.alpha}.")
    return best_name, reasons, comparisons_payload


def _build_challenger_comparisons(
    sweep: BenchmarkSweep,
    baseline: str,
    baseline_values: dict[int, float],
    policy: AcceptancePolicy,
    reasons: list[str],
) -> tuple[list, list[str]]:
    """Paired comparison for every challenger with enough shared seeds."""
    direction = -1 if sweep.lower_is_better else 1
    comparisons = []
    candidate_names: list[str] = []
    for summary in sweep.summaries:
        if summary.candidate == baseline:
            continue
        candidate_values = _paired_values_by_seed(sweep, summary.candidate)
        shared = sorted(set(baseline_values) & set(candidate_values))
        required = max(1, policy.min_pairs)  # M3: zero pairs never compare
        if len(shared) < required:
            reasons.append(
                f"{summary.candidate}: only {len(shared)} paired seeds (< {required}); skipped."
            )
            continue
        comparison = compare_paired_metric(
            sweep.metric,
            [baseline_values[s] for s in shared],
            [candidate_values[s] for s in shared],
            direction=direction,
            confidence=policy.confidence,
            alternative="greater",  # pre-registered directional improvement claim
        )
        comparisons.append(comparison)
        candidate_names.append(summary.candidate)
    return comparisons, candidate_names


def _acceptance_verdict(name: str, comparison: Any, policy: AcceptancePolicy) -> str | None:
    """None when the candidate passes; otherwise the human rejection reason."""
    if not (comparison.ci_low > 0.0):  # Q1.5: NaN CI never wins
        return (f"{name}: CI lower bound {comparison.ci_low:.6g} <= 0 — "
                "improvement not established.")
    corrected = comparison.p_value_corrected
    if corrected is None:
        corrected = comparison.p_value
    if corrected > policy.alpha:
        return f"{name}: corrected p-value {corrected:.4f} > alpha {policy.alpha}."
    return None


def _means_by_seed(runs: Any) -> dict[int, float]:
    buckets: dict[int, list[float]] = {}
    for run in runs:
        if run.ok:
            buckets.setdefault(run.seed, []).append(run.value)
    return {seed: sum(values) / len(values) for seed, values in buckets.items()}


def _screen_measure(
    executor: BenchmarkExecutor, candidates: dict[str, Any], screen_seeds: list[int],
) -> dict[str, list]:
    """Q3.3: 1-repeat screen measurements (repeats/warmup restored after)."""
    manifest = executor.target.manifest
    saved_repeats, saved_warmup = manifest.repeats, manifest.warmup
    manifest.repeats, manifest.warmup = 1, 0
    try:
        return {
            name: executor.benchmark_candidate(name, screen_seeds, variant=variant)
            for name, variant in candidates.items()
        }
    finally:
        manifest.repeats, manifest.warmup = saved_repeats, saved_warmup


def _screenable(runs: list, shared: list[int]) -> bool:
    """Q3.3: a screen verdict needs >=2 shared seeds and no broken runs."""
    return len(shared) >= 2 and all(r.ok for r in runs)


def _record_screen_verdict(
    name: str, variant: Any, comp: Any, race_margin: float,
    survivors: dict[str, Any], eliminated: list[str], details: list[str],
) -> None:
    """Q3.3: eliminate iff the screen CI upper bound rules out a win."""
    if comp.ci_high < race_margin:
        eliminated.append(name)
        details.append(f"{name}: eliminated by racing (screen CI_high {comp.ci_high:.4g} < {race_margin})")
    else:
        survivors[name] = variant
        details.append(f"{name}: kept (screen CI_high {comp.ci_high:.4g})")


def race_screen(
    executor: BenchmarkExecutor,
    candidates: dict[str, Any],
    seeds: list[int],
    baseline: str,
    *,
    race_seeds: int = 3,
    race_margin: float = 0.0,
    confidence: float = 0.95,
    adaptive: bool = False,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Cheap futility screen: 1 repeat on the first ``race_seeds`` seeds.
    With ``adaptive`` (S3): start with race_seeds-1 seeds, extend to
    race_seeds only when borderline (|CI_high - margin| < 25% of CI width).

    Eliminates a challenger only when its screen CI **upper** bound (delta vs
    baseline, positive = better) falls below ``race_margin`` — i.e. it cannot
    plausibly win the full sweep. Baseline is never eliminated. Broken
    candidates are never eliminated by racing (they fail loudly in the sweep).
    Returns (survivors, eliminated, detail_lines).
    """
    manifest = executor.target.manifest
    full_seeds = seeds[: max(2, race_seeds)]
    start_seeds = seeds[: max(2, race_seeds - 1)] if adaptive else full_seeds
    runs_by_name = _screen_measure(executor, candidates, start_seeds)

    direction = -1 if manifest.lower_is_better else 1

    def _screen_comp(shared, base_map, cand_map):
        return compare_paired_metric(
            manifest.metric_name,
            [base_map[s] for s in shared],
            [cand_map[s] for s in shared],
            direction=direction,
            confidence=confidence,
        )

    def _borderline(comp) -> bool:
        width = max(comp.ci_high - comp.ci_low, 1e-12)
        return abs(comp.ci_high - race_margin) < 0.25 * width

    def _extend(name, variant) -> None:
        extra = [s for s in full_seeds if s not in _means_by_seed(runs_by_name.get(name, []))]
        if not extra:
            return
        saved_r, saved_w = manifest.repeats, manifest.warmup
        manifest.repeats, manifest.warmup = 1, 0
        try:
            runs_by_name[name] += executor.benchmark_candidate(name, extra, variant=variant)
        finally:
            manifest.repeats, manifest.warmup = saved_r, saved_w

    base_map = _means_by_seed(runs_by_name.get(baseline, []))
    survivors: dict[str, Any] = {baseline: candidates[baseline]} if baseline in candidates else {}
    eliminated: list[str] = []
    details: list[str] = []
    for name, variant in candidates.items():
        if name == baseline:
            continue
        cand_map = _means_by_seed(runs_by_name.get(name, []))
        shared = sorted(set(base_map) & set(cand_map))
        if not _screenable(runs_by_name.get(name, []), shared):
            survivors[name] = variant  # not enough evidence (or broken) -> full sweep decides
            details.append(f"{name}: kept (insufficient screen evidence)")
            continue
        comp = _screen_comp(shared, base_map, cand_map)
        if adaptive and _borderline(comp):
            _extend(name, variant)
            if baseline in candidates:
                _extend(baseline, candidates[baseline])
            base_map = _means_by_seed(runs_by_name.get(baseline, []))
            cand_map = _means_by_seed(runs_by_name.get(name, []))
            shared = sorted(set(base_map) & set(cand_map))
            comp = _screen_comp(shared, base_map, cand_map)
            details.append(f"{name}: screen extended to {len(shared)} seeds (borderline)")
        _record_screen_verdict(name, variant, comp, race_margin,
                               survivors, eliminated, details)
    return survivors, eliminated, details


def _seed_means_from_dicts(runs: list[dict[str, Any]]) -> list[float]:
    buckets: dict[int, list[float]] = {}
    for run in runs:
        if run.get("ok") and isinstance(run.get("value"), (int, float)):
            buckets.setdefault(int(run["seed"]), []).append(float(run["value"]))
    return [sum(v) / len(v) for v in buckets.values()]


def check_regression(
    current_seed_means: list[float],
    reference_seed_means: list[float],
    pct: float,
    *,
    lower_is_better: bool,
) -> tuple[bool, str]:
    """Dual-criterion gate (API_STABLE_1.0.md §5): effect size + Welch CI.

    Returns (is_regression, human_reason). Uses a normal approximation for the
    Welch 95% CI — honest for gate purposes at typical n (7 seeds × repeats),
    and always paired with the effect-size threshold so borderline stats alone
    never fail a build.
    """
    import math as _math

    if len(current_seed_means) < 2 or len(reference_seed_means) < 2:
        return False, "regression gate skipped: <2 seeds per side (insufficient data)"
    ref_mean = sum(reference_seed_means) / len(reference_seed_means)
    cur_mean = sum(current_seed_means) / len(current_seed_means)
    if ref_mean == 0:
        return False, "regression gate skipped: reference mean is 0"

    def _var(values: list[float]) -> float:
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)

    diff = cur_mean - ref_mean  # >0 = worse when lower_is_better
    worse = diff if lower_is_better else -diff
    rel = worse / abs(ref_mean) * 100.0
    se = _math.sqrt(_var(current_seed_means) / len(current_seed_means)
                    + _var(reference_seed_means) / len(reference_seed_means))
    significant = abs(diff) > 1.96 * se if se > 0 else worse > 0
    if worse > 0 and rel > pct and significant:
        return True, (f"REGRESSION: baseline {rel:.1f}% worse than reference "
                      f"(>{pct:g}% and Welch 95% CI excludes 0)")
    return False, (f"no regression: baseline {rel:+.1f}% vs reference "
                   f"(gate: >{pct:g}% + significant)")


def load_reference_baseline(path: Path) -> tuple[list[float], str, bool]:
    """Load (seed_means, metric, lower_is_better) for the reference baseline."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read --reference {path}: {exc}") from exc
    if not isinstance(payload, dict):  # Q1.3-class: friendly, never AttributeError
        raise ValueError(f"--reference {path} is not a JSON object")
    for summary in payload.get("summaries", []):
        if summary.get("candidate") == "baseline":
            return (_seed_means_from_dicts(summary.get("runs", [])),
                    str(payload.get("metric", "")), bool(payload.get("lower_is_better", True)))
    raise ValueError(f"--reference {path} has no baseline summary")


# S1 group-sequential constants (API_STABLE_1.0.md §7, pre-registered).
# Design: K=7 max seeds, one interim look at s=6, O'Brien-Fleming two-sided
# boundary z = 1.96*sqrt(7/6) = 2.117 -> p <= 0.0342; final look p <= 0.05.
# Validated before implementation: simulated Type I 0.0335 (kill > 0.06),
# 0 flips on the replay corpus, 14.2% savings on decisive effects.
SEQUENTIAL_TOTAL_SEEDS = 7
SEQUENTIAL_LOOK_SEEDS = 6
SEQUENTIAL_ALPHA = 0.0342
SEQUENTIAL_CONFIDENCE = 0.9658


def sequential_look(sweep6: BenchmarkSweep) -> str | None:
    """S1 interim look: winner accepted at spent alpha, else None (continue)."""
    spent = AcceptancePolicy(alpha=SEQUENTIAL_ALPHA, confidence=SEQUENTIAL_CONFIDENCE)
    best, _reasons, _comparisons = decide_best_candidate(sweep6, "baseline", policy=spent)
    return best


def _interrupted_outcome(
    executor: Any, target: Any, sweep: Any, raced: list[str], started: float,
) -> GenericAccelerationOutcome:
    """Q2.1: honest partial artifacts, no decision on partial data.

    A partial sweep can still SELECT (survivor bias) — so we export what was
    measured and refuse to decide, instead of deciding on a lucky subset.
    """
    sweep_path: str | None = None
    if sweep is not None:
        sweep.comparisons = []  # informational stats stay out; decide nothing
        json_path = executor.export_json(sweep)
        executor.export_markdown(sweep)
        sweep_path = str(json_path)
        measured = [(s.candidate, len(s.runs)) for s in sweep.summaries]
    else:
        measured = []
    return GenericAccelerationOutcome(
        target=str(target.root),
        baseline="baseline",
        best_candidate=None,
        applied=False,
        decision_reasons=[
            "interrupted by user (Ctrl-C) — no decision on partial data; "
            f"measured so far: {measured or 'nothing'}; "
            f"partial sweep: {sweep_path or 'none'}.",
        ],
        sweep_path=sweep_path,
        comparisons=[],
        seconds=time.perf_counter() - started,
        raced_candidates=raced,
        regression=False,
        cached=False,
        interrupted=True,
    )


def _default_seeds(seeds: list[int] | None) -> list[int]:
    """Q3.3: prime paired seeds when the caller passes none."""
    if seeds is not None:
        return seeds
    out: list[int] = []
    base = 101
    for _ in range(5):
        base = next_prime(base)
        out.append(base)
    return out


def _lookup_cache(
    executor: BenchmarkExecutor, target: Any, manifest: Any, seeds: list[int],
    *, cache: bool, apply: bool, cache_dir: Any, race: bool, race_seeds: int,
    race_margin: float, adaptive_repeats: bool, sequential_seeds: bool,
) -> tuple[dict[str, Any] | None, str]:
    """Q3.3: read-only sweep cache probe (key computed after build)."""
    if cache and apply:
        raise ValueError("--cache requires --no-apply (measurement memoization is read-only)")
    if not (cache and not apply):
        return None, ""
    from .sweep_cache import cache_key, lookup

    key = cache_key(
        target.root, manifest.to_dict(), seeds, race=race,
        race_seeds=race_seeds, race_margin=race_margin,
        adaptive_repeats=adaptive_repeats, sequential_seeds=sequential_seeds)
    shared = cache_dir or (executor.export_dir / "cache")
    return lookup(shared, key), key


def _measure(
    executor: BenchmarkExecutor, manifest: Any, seeds: list[int],
    cache_hit: dict[str, Any] | None, policy: AcceptancePolicy,
    *, race: bool, race_seeds: int, race_margin: float, race_adaptive: bool,
    sequential_seeds: bool, adaptive_repeats: bool,
) -> tuple[BenchmarkSweep, dict[str, Any], list[str], str | None]:
    """Q3.3: race screen + paired sweep (+ S1 6+1 merge). Lets interrupts bubble."""
    candidates: dict[str, Any] = {"baseline": None}
    for variant in manifest.variants:
        candidates[variant.name] = variant
    raced: list[str] = []
    try:
        return _measure_inner(executor, manifest, seeds, cache_hit, policy, candidates,
                              race=race, race_seeds=race_seeds, race_margin=race_margin,
                              race_adaptive=race_adaptive, sequential_seeds=sequential_seeds,
                              adaptive_repeats=adaptive_repeats)
    except SweepInterrupted as exc:
        if not exc.raced:
            exc.raced = raced
        raise
    except KeyboardInterrupt:
        raise SweepInterrupted(None, raced=raced) from None


def _measure_inner(
    executor: BenchmarkExecutor, manifest: Any, seeds: list[int],
    cache_hit: dict[str, Any] | None, policy: AcceptancePolicy,
    candidates: dict[str, Any],
    *, race: bool, race_seeds: int, race_margin: float, race_adaptive: bool,
    sequential_seeds: bool, adaptive_repeats: bool,
) -> tuple[BenchmarkSweep, dict[str, Any], list[str], str | None]:
    """Q3.3: the measuring itself; _measure adds interrupt bookkeeping."""
    raced: list[str] = []
    seq_stopped: str | None = None
    if cache_hit is not None:
        sweep = BenchmarkSweep.from_dict(cache_hit["sweep"])
        raced = list(cache_hit.get("raced_candidates", []))
        return sweep, candidates, raced, seq_stopped
    if race and len(candidates) > 2:
        candidates, raced, _race_details = race_screen(
            executor, candidates, seeds, "baseline",
            race_seeds=race_seeds, race_margin=race_margin, confidence=policy.confidence,
            adaptive=race_adaptive,
        )
    if not sequential_seeds:
        sweep = executor.sweep(candidates, seeds, baseline="baseline", confidence=policy.confidence,
                               adaptive_repeats=adaptive_repeats)
        return sweep, candidates, raced, seq_stopped
    if len(seeds) != SEQUENTIAL_TOTAL_SEEDS:
        raise ValueError(
            f"--sequential-seeds requires exactly {SEQUENTIAL_TOTAL_SEEDS} seeds "
            f"(pre-registered K=7 design; got {len(seeds)})")
    sweep = executor.sweep(candidates, seeds[:SEQUENTIAL_LOOK_SEEDS],
                           baseline="baseline", confidence=SEQUENTIAL_CONFIDENCE,
                           adaptive_repeats=adaptive_repeats)
    seq_stopped = sequential_look(sweep)
    if seq_stopped is not None:
        return sweep, candidates, raced, seq_stopped
    rest = executor.sweep(candidates, seeds[SEQUENTIAL_LOOK_SEEDS:],
                          baseline="baseline", confidence=policy.confidence,
                          adaptive_repeats=adaptive_repeats)
    from .bench import summarize_runs as _summarize_runs

    rest_runs = {s.candidate: s.runs for s in rest.summaries}
    merged = [_summarize_runs(s.candidate, s.runs + rest_runs.get(s.candidate, []))
              for s in sweep.summaries]
    sweep = BenchmarkSweep(target=sweep.target, metric=sweep.metric,
                           lower_is_better=sweep.lower_is_better,
                           summaries=merged, comparisons=[],
                           started_at=sweep.started_at)
    return sweep, candidates, raced, seq_stopped


def _decide_with_reasons(
    sweep: BenchmarkSweep, policy: AcceptancePolicy, candidates: dict[str, Any],
    raced: list[str], *, race: bool, sequential_seeds: bool, seq_stopped: str | None,
) -> tuple[str | None, list[str], list[dict[str, Any]]]:
    """Q3.3: verdict + the full reason trail (order preserved)."""
    look_policy = policy
    if sequential_seeds and seq_stopped is not None:
        look_policy = AcceptancePolicy(alpha=SEQUENTIAL_ALPHA, confidence=SEQUENTIAL_CONFIDENCE)
    best, reasons, comparisons = decide_best_candidate(sweep, "baseline", policy=look_policy)
    if sequential_seeds:
        reasons.insert(0, f"sequential: {'stopped at 6/7 seeds (OBF look accepted)' if seq_stopped else 'continued to 7/7 seeds (look inconclusive)'}.")
    for summary in sweep.summaries:
        if summary.flaky:
            reasons.append(
                f"WARNING: {summary.candidate} is flaky "
                "(CV of per-seed means > 0.15) — repeat with more seeds before applying."
            )
    if race and len(candidates) <= 2 and not raced:
        reasons.append("racing skipped: fewer than 2 challengers (screen would be pure overhead).")
    for name in raced:
        reasons.append(f"{name}: eliminated by racing screen (futility, see sweep for survivors).")
    return best, reasons, comparisons


def _persist_artifacts(
    executor: BenchmarkExecutor, sweep: BenchmarkSweep, comparisons: list[dict[str, Any]],
    reasons: list[str], best: str | None, *, cache: bool, apply: bool,
    cache_hit: dict[str, Any] | None, cache_dir: Any, cache_key_value: str, raced: list[str],
) -> Path:
    """Q3.3: cache store + the four exports; returns the JSON path."""
    sweep.comparisons = comparisons
    if cache and not apply and cache_hit is None:
        from .sweep_cache import store

        store(cache_dir or (executor.export_dir / "cache"), cache_key_value, {
            "sweep": sweep.to_dict(), "raced_candidates": raced})
    json_path = executor.export_json(sweep)
    executor.export_csv(sweep)
    executor.export_markdown(sweep)
    executor.export_html(sweep, verdict="; ".join(reasons) if best else "no candidate accepted")
    return json_path


def _apply_winner(
    target: Any, manifest: Any, best: str | None, sweep: BenchmarkSweep,
    tests_pass: bool, *, apply: bool, reasons: list[str],
) -> bool:
    """Q3.3: apply + rollback safety; returns whether anything was applied."""
    if not (apply and best is not None and tests_pass):
        if apply and best is not None and not tests_pass:
            reasons.append("Project tests do not pass at baseline; refusing to apply any variant.")
        return False
    winner = next((v for v in manifest.variants if v.name == best), None)
    if winner is None:
        return False
    if winner.mode in {"env", "args", "profile"}:
        selection_path = target.root / ".mycelium_targets" / "active_variant.json"
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_path.write_text(
            json.dumps({"variant": winner.to_dict(), "metric": sweep.metric}, indent=2),
            encoding="utf-8",
        )
        return True
    snapshot = target.apply_variant(winner)
    try:
        retest = target.test()
        if retest is not None and not retest.ok:
            reasons.append(f"{best}: tests failed under variant; rolled back.")
            target.revert_variant(snapshot, winner)
            return False
        return True  # keep the transformation in place
    except Exception:
        target.revert_variant(snapshot, winner)
        raise


def _reference_gate(
    reference: Any, fail_on_regression: float | None,
    sweep: BenchmarkSweep, reasons: list[str],
) -> bool:
    """Q3.3: --reference regression gate; returns whether it tripped."""
    if reference is None or fail_on_regression is None:
        return False
    ref_means, ref_metric, ref_direction = load_reference_baseline(reference)
    if ref_metric != sweep.metric or ref_direction != sweep.lower_is_better:
        raise ValueError(
            f"--reference {reference} incompatible: metric={ref_metric!r} "
            f"direction={'lower' if ref_direction else 'higher'} vs current "
            f"metric={sweep.metric!r} direction={'lower' if sweep.lower_is_better else 'higher'}"
        )
    baseline_summary = next(s for s in sweep.summaries if s.candidate == "baseline")
    cur_means = _seed_means_from_dicts([r.to_dict() for r in baseline_summary.runs])
    regression, gate_reason = check_regression(
        cur_means, ref_means, fail_on_regression, lower_is_better=sweep.lower_is_better)
    reasons.append(gate_reason)
    return regression


def accelerate_target(
    target_root: Path,
    *,
    manifest_path: Path | None = None,
    seeds: list[int] | None = None,
    apply: bool = True,
    export_dir: Path | None = None,
    policy: AcceptancePolicy | None = None,
    race: bool = False,
    race_seeds: int = 3,
    race_margin: float = 0.0,
    race_adaptive: bool = False,
    reference: Path | None = None,
    fail_on_regression: float | None = None,
    adaptive_repeats: bool = False,
    cache: bool = False,
    cache_dir: Path | None = None,
    sequential_seeds: bool = False,
    dry_run: bool = False,
) -> GenericAccelerationOutcome:
    started = time.perf_counter()
    target = load_target(target_root, manifest_path)
    manifest = target.manifest
    seeds = _default_seeds(seeds)
    policy = policy or AcceptancePolicy()

    # A dry run validates the real target lifecycle but deliberately does not
    # construct an executor (which would create an artifacts directory), run a
    # benchmark, or write any reports.
    if dry_run:
        target.build()  # build failures remain actionable RuntimeErrors
        test_result = target.test()
        test_status = "PASS" if test_result is None or test_result.ok else "FAIL"
        return GenericAccelerationOutcome(
            target=str(target.root),
            baseline="baseline",
            best_candidate=None,
            applied=False,
            decision_reasons=[
                f"dry run: manifest valid; metric '{manifest.metric_name}'; "
                f"tests {test_status}; no measurements taken."
            ],
            sweep_path=None,
            seconds=time.perf_counter() - started,
        )

    # 1. build + test gate
    target.build()
    test_result = target.test()
    tests_pass = test_result is None or test_result.ok

    # 1b. sweep cache (V4.1: read-only runs only; key computed AFTER build)
    executor = BenchmarkExecutor(target, export_dir=export_dir)
    cache_hit, cache_key_value = _lookup_cache(
        executor, target, manifest, seeds, cache=cache, apply=apply,
        cache_dir=cache_dir, race=race, race_seeds=race_seeds,
        race_margin=race_margin, adaptive_repeats=adaptive_repeats,
        sequential_seeds=sequential_seeds)

    # 2. paired benchmark sweep (optionally preceded by a racing screen)
    try:
        sweep, candidates, raced, seq_stopped = _measure(
            executor, manifest, seeds, cache_hit, policy, race=race,
            race_seeds=race_seeds, race_margin=race_margin,
            race_adaptive=race_adaptive, sequential_seeds=sequential_seeds,
            adaptive_repeats=adaptive_repeats)
    except SweepInterrupted as exc:  # Q2.1: honest partial, no decision
        return _interrupted_outcome(executor, target, exc.sweep, exc.raced, started)

    # 3. statistics
    best, reasons, comparisons = _decide_with_reasons(
        sweep, policy, candidates, raced, race=race,
        sequential_seeds=sequential_seeds, seq_stopped=seq_stopped)

    # 4. persist artifacts
    json_path = _persist_artifacts(
        executor, sweep, comparisons, reasons, best, cache=cache, apply=apply,
        cache_hit=cache_hit, cache_dir=cache_dir, cache_key_value=cache_key_value,
        raced=raced)

    # 5. apply + rollback safety
    applied = _apply_winner(target, manifest, best, sweep, tests_pass,
                            apply=apply, reasons=reasons)

    if cache_hit is not None:
        reasons.append(
            f"cache hit: measurements reused (key {cache_key_value[:12]}…); "
            "re-run without --cache to re-measure")
    regression = _reference_gate(reference, fail_on_regression, sweep, reasons)

    return GenericAccelerationOutcome(
        target=str(target.root),
        baseline="baseline",
        best_candidate=best,
        applied=applied,
        decision_reasons=reasons,
        sweep_path=str(json_path),
        comparisons=comparisons,
        seconds=time.perf_counter() - started,
        raced_candidates=raced,
        regression=regression,
        cached=cache_hit is not None,
    )

