"""Q1.3 — crash-freedom fuzz for loaders + the CLI parser.

Contract: hostile input may raise ValueError/TypeError/KeyError (handled by
callers with friendly messages) or SystemExit (argparse) — anything else is a
bug. Roundtrips on the replay corpus pin the serialization format.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mycelium_accel.__main__ import build_parser
from mycelium_accel.bench import BenchmarkSweep
from mycelium_accel.targets.base import TargetManifest, Variant

settings.register_profile("fast", max_examples=20, suppress_health_check=list(HealthCheck))
settings.register_profile("ci", max_examples=200, suppress_health_check=list(HealthCheck))
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "fast"))

FRIENDLY = (ValueError, TypeError, KeyError)

hostile_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(),
    st.binary(),
)
hostile = st.recursive(
    hostile_leaf,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=8), children, max_size=5),
    ),
    max_leaves=12,
)


class TestLoaderCrashFreedom:
    @given(hostile)
    def test_sweep_from_dict(self, payload: object) -> None:
        try:
            BenchmarkSweep.from_dict(payload)  # type: ignore[arg-type]
        except FRIENDLY:
            pass

    @given(hostile)
    def test_manifest_from_dict(self, payload: object) -> None:
        try:
            TargetManifest.from_dict(payload)  # type: ignore[arg-type]
        except FRIENDLY:
            pass

    @given(hostile)
    def test_variant_from_dict(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        try:
            Variant.from_dict(payload)
        except FRIENDLY:
            pass


MANIFEST_KEYS = st.sampled_from([
    "name", "kind", "benchmark_command", "metrics_parser", "metric_name",
    "lower_is_better", "variants", "warmup", "repeats", "timeout_seconds",
    "artifact_paths", "env", "files", "mode", "args",
])
SWEEP_KEYS = st.sampled_from([
    "target", "metric", "lower_is_better", "summaries", "comparisons",
    "started_at", "candidate", "runs", "mean", "stddev", "median",
    "minimum", "maximum", "flaky", "seed", "value", "seconds", "ok",
])


class TestShapedCrashFreedom:
    """Same contract, but with REAL keys — reaches the deep paths."""

    @given(st.dictionaries(MANIFEST_KEYS, hostile, max_size=8))
    def test_manifest_shaped(self, payload: dict) -> None:
        try:
            TargetManifest.from_dict(payload)
        except FRIENDLY:
            pass

    @given(st.dictionaries(SWEEP_KEYS, hostile, max_size=8))
    def test_sweep_shaped(self, payload: dict) -> None:
        try:
            BenchmarkSweep.from_dict(payload)
        except FRIENDLY:
            pass


class TestRegressionFriendlyErrors:
    """Deterministic: every path below once raised an UNFRIENDLY error."""

    def test_sweep_list_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkSweep.from_dict([1, 2])  # type: ignore[arg-type]

    def test_variant_int_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            Variant.from_dict(42)  # type: ignore[arg-type]

    def test_variant_env_int_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            Variant.from_dict({"name": "v", "env": 42})

    def test_manifest_variant_int_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            TargetManifest.from_dict({"variants": [42]})

    def test_cache_list_file_is_miss(self, tmp_path) -> None:  # noqa: ANN001
        from mycelium_accel.sweep_cache import lookup

        (tmp_path / "k.json").write_text("[1, 2]", encoding="utf-8")
        assert lookup(tmp_path, "k") is None


class TestParserCrashFreedom:
    @given(st.lists(st.text(max_size=20), min_size=0, max_size=8))
    def test_parse_args_never_tracebacks(self, tokens: list[str]) -> None:
        try:
            build_parser().parse_args(tokens)
        except SystemExit:
            pass  # argparse usage error — friendly by design

    @given(st.lists(
        st.sampled_from([
            "accelerate", "run", "--race", "--cache", "--no-apply",
            "--sequential-seeds", "--adaptive-repeats", "--race-adaptive",
            "--seeds", "101,103", "--target", "--manifest", "--race-seeds",
            "--race-margin", "--reference", "--fail-on-regression",
            "--cache-dir", "--", "-", "",
        ]),
        min_size=0, max_size=8,
    ))
    def test_parse_args_flag_soup(self, tokens: list[str]) -> None:
        try:
            build_parser().parse_args(tokens)
        except SystemExit:
            pass


class TestRoundtrips:
    @pytest.mark.parametrize("name", sorted(
        p.name for p in (Path(__file__).parent / "replay").glob("*.json")
    ))
    def test_replay_sweep_roundtrip(self, name: str, subtests) -> None:  # noqa: ANN001
        raw = json.loads((Path(__file__).parent / "replay" / name).read_text())
        once = BenchmarkSweep.from_dict(raw).to_dict()
        twice = BenchmarkSweep.from_dict(once).to_dict()
        assert twice == once

    def test_manifest_roundtrip(self) -> None:
        manifest = {
            "name": "rt", "kind": "python", "benchmark_command": "python3 bench.py",
            "metrics_parser": "json_stdout", "metric_name": "seconds",
            "variants": [{"name": "v", "mode": "env", "env": {"A": "b"}}],
        }
        once = TargetManifest.from_dict(manifest).to_dict()
        twice = TargetManifest.from_dict(once).to_dict()
        assert twice == once
