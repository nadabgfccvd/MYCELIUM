"""Q4/M3 — stateful fuzz of the sweep→decide→export pipeline (hypothesis).

A RuleBasedStateMachine builds a BenchmarkSweep run by run (hostile values,
hostile names, broken runs, boundary policies) and interleaves decide() and
export() calls. Invariants (roadmap M3):

* decide() never raises; verdict is None or a known candidate;
* decide() is deterministic (same sweep twice → identical outcome);
* all four exports succeed; JSON parses and roundtrips (NaN-aware);
* to_dict() is always JSON-serializable (checked after every step).

Every example starts from a dense 3-candidate × 4-seed grid (@initialize),
so decide() exercises the real paired/MC path instead of only the
no-data exits. Slow-marked (MC budgets inside decide); CI always runs all.
HYPOTHESIS_PROFILE=ci selects the exhaustive settings (mirrors
test_stats_properties.py, without touching its global profiles).
"""

from __future__ import annotations

import csv
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from mycelium_accel.accelerate_generic import decide_best_candidate
from mycelium_accel.bench import (
    BenchmarkExecutor,
    BenchmarkRun,
    BenchmarkSweep,
    summarize_runs,
)
from mycelium_accel.stats import AcceptancePolicy
from mycelium_accel.targets.base import ProjectTarget, TargetManifest

pytestmark = pytest.mark.slow

_CANDIDATES = ["baseline", "a", "b"]
# 6 seeds: the MC p-value floor (1/64) clears Holm-for-2 at alpha 0.05,
# so systematic offsets reach real wins (n <= 4 mathematically cannot).
_SEEDS = st.integers(min_value=0, max_value=5)
_HOSTILE_TEXT = st.one_of(
    st.just(""),
    st.just("../evil"),
    st.just("a/b\\c"),
    st.just("%s%s{nul}"),
    st.text(min_size=1, max_size=12),
)
_VALUES = st.one_of(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.sampled_from(
        [float("nan"), float("inf"), float("-inf"), 0.0, -0.0, 1e300, 1e-300, 5e-324]
    ),
)
_SECONDS = st.one_of(
    st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
    st.sampled_from([float("nan"), float("inf"), -1.0]),
)
# Grid noise: usually small (systematic per-candidate offsets below produce
# real wins), sometimes fully hostile (branch repetition = 3:1 weighting).
_GRID_NOISE = st.one_of(
    st.floats(min_value=-1.5, max_value=1.5, allow_nan=False),
    st.floats(min_value=-1.5, max_value=1.5, allow_nan=False),
    st.floats(min_value=-1.5, max_value=1.5, allow_nan=False),
    _VALUES,
)
_OFFSETS = {"baseline": 10.0, "a": 12.0, "b": 8.0}


def _trees_equal(left: Any, right: Any) -> bool:
    """Structural equality where NaN == NaN (JSON roundtrips preserve NaN)."""
    if isinstance(left, float) and isinstance(right, float):
        if math.isnan(left) and math.isnan(right):
            return True
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _trees_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _trees_equal(x, y) for x, y in zip(left, right)
        )
    return bool(left == right)


class SweepDecideExportMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._tmp = tempfile.TemporaryDirectory(prefix="m3-stateful-")
        root = Path(self._tmp.name) / "target"
        root.mkdir(exist_ok=True)
        target = ProjectTarget(root, TargetManifest())
        self.executor = BenchmarkExecutor(
            target, export_dir=Path(self._tmp.name) / "exports"
        )
        self.runs: dict[str, list[BenchmarkRun]] = {}
        self.target_name = "m3-target"
        self.metric = "seconds"
        self.lower_is_better = True
        self.policy = AcceptancePolicy()
        self.partial = False
        self.comparisons: list[dict[str, Any]] = []

    def teardown(self) -> None:
        self._tmp.cleanup()

    # -- model ---------------------------------------------------------
    def _build_sweep(self) -> BenchmarkSweep:
        summaries = [
            summarize_runs(candidate, runs)
            for candidate, runs in self.runs.items()
            if runs
        ]
        return BenchmarkSweep(
            target=self.target_name,
            metric=self.metric,
            lower_is_better=self.lower_is_better,
            summaries=summaries,
            comparisons=self.comparisons,
            partial=self.partial,
        )

    def _add(
        self, candidate: str, seed: int, value: float, seconds: float, ok: bool
    ) -> None:
        self.runs.setdefault(candidate, []).append(
            BenchmarkRun(
                candidate=candidate,
                seed=seed,
                metric=self.metric,
                value=value,
                seconds=seconds,
                ok=ok,
            )
        )

    def _check_verdict(self, best: str | None, reasons: list[str]) -> None:
        assert best is None or best in self.runs, (
            f"verdict {best!r} is not a known candidate"
        )
        assert isinstance(reasons, list) and reasons, "decide must explain itself"
        assert all(isinstance(item, str) for item in reasons)

    @initialize(values=st.lists(_GRID_NOISE, min_size=18, max_size=18))
    def seed_dense_grid(self, values: list[float]) -> None:
        """Dense 3×6 paired grid with systematic offsets: 'b' beats the
        baseline when lower is better, 'a' when higher is better — so
        decide() reaches real (non-None) verdicts, not just exits."""
        idx = 0
        for candidate in _CANDIDATES:
            for seed in range(6):
                self._add(candidate, seed, _OFFSETS[candidate] + values[idx], 1.0, True)
                idx += 1

    # -- sweep rules (add_run split ×3: hypothesis picks rules uniformly,
    # so one rule would starve the sweep while hostile rules dilute it) --
    @rule(seed=_SEEDS, value=_VALUES, seconds=_SECONDS, ok=st.booleans())
    def add_run_baseline(
        self, seed: int, value: float, seconds: float, ok: bool
    ) -> None:
        self._add("baseline", seed, value, seconds, ok)

    @rule(seed=_SEEDS, value=_VALUES, seconds=_SECONDS, ok=st.booleans())
    def add_run_a(self, seed: int, value: float, seconds: float, ok: bool) -> None:
        self._add("a", seed, value, seconds, ok)

    @rule(seed=_SEEDS, value=_VALUES, seconds=_SECONDS, ok=st.booleans())
    def add_run_b(self, seed: int, value: float, seconds: float, ok: bool) -> None:
        self._add("b", seed, value, seconds, ok)

    @rule(name=_HOSTILE_TEXT, seed=_SEEDS, value=_VALUES)
    def add_hostile_candidate(self, name: str, seed: int, value: float) -> None:
        if len(self.runs) >= 5:
            return
        self._add(name, seed, value, 1.0, True)

    @rule(candidate=st.sampled_from(_CANDIDATES))
    def drop_candidate(self, candidate: str) -> None:
        self.runs.pop(candidate, None)

    @rule(name=_HOSTILE_TEXT)
    def rename_target(self, name: str) -> None:
        self.target_name = name or "m3-target"

    @rule(name=_HOSTILE_TEXT)
    def rename_metric(self, name: str) -> None:
        self.metric = name or "seconds"

    @rule()
    def flip_direction(self) -> None:
        self.lower_is_better = not self.lower_is_better

    @rule()
    def mark_partial(self) -> None:
        self.partial = True

    @rule(
        min_pairs=st.integers(min_value=0, max_value=5),
        alpha=st.sampled_from([0.0, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0]),
        correction=st.sampled_from(["holm", "bh", "none"]),
        confidence=st.sampled_from([0.5, 0.9, 0.95, 0.99]),
    )
    def set_policy(
        self, min_pairs: int, alpha: float, correction: str, confidence: float
    ) -> None:
        self.policy = AcceptancePolicy(
            confidence=confidence,
            alpha=alpha,
            correction=correction,
            min_pairs=min_pairs,
        )

    # -- decide rules ---------------------------------------------------
    @rule()
    def decide(self) -> None:
        sweep = self._build_sweep()
        first = decide_best_candidate(sweep, "baseline", policy=self.policy)
        second = decide_best_candidate(sweep, "baseline", policy=self.policy)
        assert _trees_equal(first, second), "decide must be deterministic"
        best, reasons, comparisons = first
        self._check_verdict(best, reasons)
        for payload in comparisons:
            assert payload["candidate"] in self.runs
            assert payload["baseline"] == "baseline"
        # The real pipeline persists comparisons onto the sweep: model it,
        # so exports render comparison tables with hostile payloads.
        self.comparisons = comparisons

    @rule(baseline=st.one_of(st.sampled_from(["", "ghost"]), _HOSTILE_TEXT))
    def decide_unknown_baseline(self, baseline: str) -> None:
        name = baseline or "ghost"
        # CI-1: a hostile candidate may already own this name (fresh-DB CI runs
        # hit the collision ~always); without the guard the "unknown" premise is false.
        assume(name not in self.runs)
        best, reasons, comparisons = decide_best_candidate(
            self._build_sweep(), name, policy=self.policy
        )
        assert best is None
        self._check_verdict(best, reasons)
        assert comparisons == []

    # -- export rules ---------------------------------------------------
    @rule()
    def export_all(self) -> None:
        sweep = self._build_sweep()
        json_path = self.executor.export_json(sweep)
        csv_path = self.executor.export_csv(sweep)
        md_path = self.executor.export_markdown(sweep)
        html_path = self.executor.export_html(sweep, verdict="m3-fuzz")
        for path in (json_path, csv_path, md_path, html_path):
            assert path.exists(), f"export missing: {path}"
            assert path.stat().st_size > 0, f"export empty: {path}"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["target"] == sweep.target
        assert len(payload["summaries"]) == len(sweep.summaries)
        assert len(payload["comparisons"]) == len(sweep.comparisons)
        assert _trees_equal(
            BenchmarkSweep.from_dict(payload).to_dict(), sweep.to_dict()
        ), "JSON export must roundtrip"
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        total_runs = sum(len(summary.runs) for summary in sweep.summaries)
        assert len(rows) == total_runs + 1, "CSV must carry every run plus header"

    # -- cheap universal invariants --------------------------------------
    @invariant()
    def sweep_serializable(self) -> None:
        json.dumps(self._build_sweep().to_dict(), sort_keys=True)

    @invariant()
    def sweep_roundtrips(self) -> None:
        sweep = self._build_sweep()
        assert _trees_equal(
            BenchmarkSweep.from_dict(sweep.to_dict()).to_dict(), sweep.to_dict()
        )


TestPipelineStateful = SweepDecideExportMachine.TestCase
if os.environ.get("HYPOTHESIS_PROFILE") == "ci":
    TestPipelineStateful.settings = settings(
        max_examples=60,
        stateful_step_count=40,
        deadline=None,
        suppress_health_check=list(HealthCheck),
    )
else:
    TestPipelineStateful.settings = settings(
        max_examples=15,
        stateful_step_count=25,
        deadline=None,
        suppress_health_check=list(HealthCheck),
    )
