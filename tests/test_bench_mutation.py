"""Mutation battery for ``mycelium_accel/bench.py`` (post-1.4.0 reconnaissance).

A mutmut round over bench.py (562 mutants: 331 killed, 6 no-tests,
225 survived, 59.5% excl. no-tests — below the 80% gate) identified the
survivors triaged below. This battery pins the cheap kills with stubbed
targets (no subprocesses, no sleeps): pure helpers, export goldens, and
a scripted-runner executor battery covering _run_once / benchmark_candidate
/ sweep.

Accepted survivors (NOT covered here — audited as equivalent or policy):
  messages  : parse#18/#19/#20/#21/#33, candidate#4/#5/#6/#7 (M1 policy:
              exception text is not a contract — type only is pinned).
  INF/NAN   : mean#5, median#4, run_once#75/#98, summarize#10
              (float("INF")/float("NAN") spell the same value).
  codec case: csv#14, html#14, md#66 ("UTF-8" == "utf-8" codec lookup).
  locale    : csv#5/#6/#8/#9, html#6/#8, md#58/#60 (newline/encoding
              defaults differ only off-POSIX-UTF-8; unkillable portably).
  runner default: run_once#41 (seed=None is CommandRunner.run's default).
  unused seed_index: candidate#16/#38 (parameter never read — every
              _run_once return passes the seed kwarg to BenchmarkRun).
  discarded warmup fields: candidate#15/#18/#27 (warmup runs are
              discarded; candidate/warmup flag unobservable).
  measured flag: candidate#40 (warmup=None is falsy: measured path anyway).
  unreachable gate: sweep#48 (futility break guarantees any
              <2-shared candidate is last, so continue-vs-break is dead).
  direction scale: sweep#61/#62 (compare normalizes sign: -2/-1, 2/1 same).
  float dust: adaptive#16 (`<` vs `<=` at exactly 1.00%: bit-exact 0.01
              ratio is unconstructible in binary floats — M1 dust principle).
  measure-zero: flaky#14 (CV == 0.15 exactly: tolerance-point, not a cliff).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mycelium_accel.bench import (
    BenchmarkExecutor,
    BenchmarkRun,
    BenchmarkSweep,
    CandidateSummary,
    SweepInterrupted,
    _mean,
    _median,
    _per_seed_values,
    _seed_means,
    _stddev,
    adaptive_stop,
    is_flaky,
    parse_metrics,
    summarize_runs,
)
from mycelium_accel.targets.base import TargetRunResult, Variant


def _result(seconds, *, rc=0, out="", err=""):
    return TargetRunResult(
        command=["bench"],
        returncode=rc,
        seconds=seconds,
        stdout_tail=out,
        stderr_tail=err,
    )


def _run(candidate="a", seed=1, value=1.0, *, ok=True):
    return BenchmarkRun(candidate, seed, "time", value, 0.01, ok)


class _ScriptRunner:
    """Runner replaying a scripted list; BaseExceptions in the script raise."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def run(self, command, *, env=None, timeout=None, seed=None):
        self.calls.append({"command": command, "env": dict(env or {}), "seed": seed})
        item = self._script.pop(0) if len(self._script) > 1 else self._script[0]
        if isinstance(item, BaseException):
            raise item
        return item


def _make_target(tmp, runner, **manifest_kwargs):
    manifest = SimpleNamespace(
        benchmark_command="bench --x",
        metric_name="time",
        metrics_parser="time",
        seed_env_var="MY_SEED",
        lower_is_better=True,
        warmup=0,
        repeats=1,
    )
    for key, value in manifest_kwargs.items():
        setattr(manifest, key, value)
    target = SimpleNamespace(
        manifest=manifest,
        runner=runner,
        root=tmp,
        prepare_calls=[],
        clean_calls=[],
        apply_calls=[],
        revert_calls=[],
        variant_env_calls=[],
        build_env_calls=[],
    )
    target.prepare = lambda seed: target.prepare_calls.append(seed)
    target.clean = lambda: target.clean_calls.append(1)
    target.variant_env = lambda variant, seed: (
        target.variant_env_calls.append((variant, seed))
        or {"V_MODE": variant.mode, "V_SEED": str(seed)}
    )
    target.build_env = lambda: target.build_env_calls.append(1) or {"BASE": "1"}
    target.apply_variant = lambda variant: target.apply_calls.append(variant) or "SNAP"
    target.revert_variant = lambda snapshot, variant: target.revert_calls.append(
        (snapshot, variant)
    )
    return target


def _make_executor(tmp, runner, **manifest_kwargs):
    target = _make_target(tmp, runner, **manifest_kwargs)
    return BenchmarkExecutor(target, export_dir=tmp / "out"), target


def _sweep_fixture(**kwargs):
    run_a1 = BenchmarkRun("a", 1, "time", 1.0, 0.01, True)
    run_a2 = BenchmarkRun("a", 2, "time", 3.0, 0.01, True)
    run_b1 = BenchmarkRun("b", 1, "time", 2.0, 0.01, True)
    summary_a = CandidateSummary(
        "a", [run_a1, run_a2], 2.0, 1.4142135623730951, 2.0, 1.0, 3.0, False
    )
    summary_b = CandidateSummary("b", [run_b1], 2.0, 0.0, 2.0, 2.0, 2.0, False)
    payload = {
        "target": "t",
        "metric": "m",
        "lower_is_better": True,
        "summaries": [summary_a, summary_b],
        "comparisons": [],
        "started_at": 100.0,
    }
    payload.update(kwargs)
    return BenchmarkSweep(**payload)


class HelperTests(unittest.TestCase):
    def test_mean_exact_and_empty(self):
        self.assertEqual(_mean([1.0, 2.0, 3.0]), 2.0)
        self.assertTrue(_mean([]) != _mean([]))  # NaN

    def test_median_odd_even_empty(self):
        self.assertEqual(_median([3.0, 1.0, 2.0]), 2.0)
        self.assertEqual(_median([4.0, 1.0, 3.0, 2.0]), 2.5)
        self.assertTrue(_median([]) != _median([]))  # NaN

    def test_stddev_bessel_and_degenerate(self):
        self.assertEqual(_stddev([1.0, 2.0, 3.0]), 1.0)  # /(n-1), not /n
        self.assertEqual(_stddev([5.0]), 0.0)
        self.assertEqual(_stddev([]), 0.0)

    def test_stddev_overflow_degrades_to_inf(self):
        self.assertEqual(_stddev([1e308, -1e308]), float("inf"))  # M3: no crash

    def test_seed_means_mixed(self):
        runs = [
            _run("a", 1, 1.0),
            _run("a", 1, 3.0),
            _run("a", 2, 2.0),
            _run("a", 3, 9.0, ok=False),
            _run("a", 4, float("inf")),
        ]
        self.assertEqual(sorted(_seed_means(runs)), [2.0, 2.0])  # broken/non-finite out

    def test_per_seed_values_mixed(self):
        runs = [_run("a", 1, 1.0), _run("a", 1, 3.0), _run("a", 2, 9.0, ok=False)]
        self.assertEqual(_per_seed_values(runs), {1: 2.0})

    def test_adaptive_stop(self):
        self.assertFalse(adaptive_stop([5.0]))  # r < 2 never stops
        self.assertTrue(adaptive_stop([5.0, 5.0]))  # tight CI stops at r=2
        self.assertFalse(adaptive_stop([1.0, 100.0]))  # loose CI continues
        self.assertFalse(adaptive_stop([0.0, 0.0]))  # zero mean never stops

    def test_is_flaky(self):
        two_seeds = [_run("a", 1, 1.0), _run("a", 2, 100.0)]
        self.assertFalse(is_flaky(two_seeds))  # < 3 seeds: False
        zero_mean = [_run("a", 1, -1.0), _run("a", 2, 0.0), _run("a", 3, 1.0)]
        self.assertFalse(is_flaky(zero_mean))
        flaky = [_run("a", 1, 10.0), _run("a", 2, 20.0), _run("a", 3, 30.0)]
        self.assertTrue(is_flaky(flaky))  # CV 0.5 > 0.15
        stable = [_run("a", 1, 10.0), _run("a", 2, 10.1), _run("a", 3, 9.9)]
        self.assertFalse(is_flaky(stable))

    def test_summarize_exact(self):
        runs = [
            _run("a", 1, 1.0),
            _run("a", 1, 3.0),
            _run("a", 2, 2.0),
            _run("a", 2, 4.0),
        ]
        summary = summarize_runs("a", runs)
        self.assertEqual(summary.candidate, "a")
        self.assertEqual(summary.mean, 2.5)
        self.assertAlmostEqual(summary.stddev, 1.2909944487358056)
        self.assertEqual(summary.median, 2.5)
        self.assertEqual(summary.minimum, 1.0)
        self.assertEqual(summary.maximum, 4.0)
        self.assertFalse(summary.flaky)  # 2 seeds

    def test_summarize_empty(self):
        summary = summarize_runs("a", [])
        self.assertEqual(summary.mean, float("inf"))
        self.assertEqual(summary.stddev, 0.0)
        self.assertEqual(summary.median, float("inf"))
        self.assertEqual(summary.minimum, float("inf"))
        self.assertEqual(summary.maximum, float("inf"))
        self.assertFalse(summary.flaky)

    def test_summarize_mixed_broken_poison(self):
        runs = [_run("a", 1, 1.0), _run("a", 2, 2.0, ok=False)]
        summary = summarize_runs("a", runs)
        self.assertEqual(summary.mean, float("inf"))
        self.assertEqual(summary.median, float("inf"))

    def test_parse_time(self):
        result = _result(1.25)
        self.assertEqual(parse_metrics(result, "time", "time"), {"time": 1.25})

    def test_parse_json_stdout_skips_garbage(self):
        out = '{"time": 2.5}\n{bad json\ntrailing garbage\n'
        result = _result(0.1, out=out)
        self.assertEqual(parse_metrics(result, "json_stdout", "time"), {"time": 2.5})

    def test_parse_regex_modes(self):
        named = _result(0.1, out="score time=3.5 ok")
        self.assertEqual(
            parse_metrics(named, r"regex:time=(?P<time>\S+)", "time"), {"time": 3.5}
        )
        fallback = _result(0.1, out="score 4.5 ok")
        self.assertEqual(
            parse_metrics(fallback, r"regex:score (?P<other>\S+)", "time"),
            {"time": 4.5},
        )
        positional = _result(0.1, out="score 5.5 ok")
        self.assertEqual(
            parse_metrics(positional, r"regex:score (\S+)", "time"), {"time": 5.5}
        )
        with self.assertRaises(RuntimeError):
            parse_metrics(_result(0.1, out="nothing"), r"regex:score (\S+)", "time")

    def test_parse_regex_spans_stdout_stderr_join(self):
        result = _result(0.1, out="score 7", err="more")
        self.assertEqual(
            parse_metrics(result, r"regex:score (\S+)\nmore", "time"), {"time": 7.0}
        )

    def test_stem_format(self):
        sweep = _sweep_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner([_result(1.0)]))
            stem = executor._stem(sweep)
        self.assertEqual(stem, f"sweep-100000000-{os.getpid()}")


class ExportTests(unittest.TestCase):
    def _export(self, sweep, method, *args):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner([_result(1.0)]))
            path = getattr(executor, method)(sweep, *args)
            return path.read_text(encoding="utf-8")

    def test_json_sorted_keys_and_indent(self):
        text = self._export(_sweep_fixture(), "export_json")
        self.assertLess(text.index('"comparisons"'), text.index('"target"'))
        lines = text.splitlines()
        self.assertTrue(lines[1].startswith('  "'))
        self.assertFalse(lines[1].startswith('   "'))
        self.assertEqual(json.loads(text)["metric"], "m")

    def test_csv_header_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner([_result(1.0)]))
            path = executor.export_csv(_sweep_fixture())
            raw = path.read_bytes()
        first, _, _ = raw.partition(b"\n")
        self.assertEqual(first, b"candidate,seed,metric,value,seconds,ok\r")
        self.assertIn(b"a,1,time,1.0,0.01,True\r\n", raw)

    def test_markdown_golden_lower(self):
        comparisons = [
            {
                "candidate": "b",
                "mean_delta": 0.5,
                "ci_low": 0.1,
                "ci_high": 0.9,
                "p_value": 0.03125,
                "p_value_corrected": 0.06,
                "effect_dz": 1.5,
            },
            {
                "candidate": "c",
                "mean_delta": -0.25,
                "ci_low": -0.5,
                "ci_high": 0.0,
                "p_value": 0.5,
                "p_value_corrected": None,
                "effect_dz": -0.2,
            },
        ]
        text = self._export(_sweep_fixture(comparisons=comparisons), "export_markdown")
        expected = """# Benchmark sweep — t

Metric: `m` (lower is better)

| candidate | mean | stddev | median | min | max | runs |
|---|---|---|---|---|---|---|
| a | 2 | 1.41 | 2 | 1 | 3 | 2 |
| b | 2 | 0 | 2 | 2 | 2 | 1 |

## Paired comparisons (per-seed deltas, BCa CI + sign-flip p)

| candidate | mean Δ | CI low | CI high | p | p (corr) | effect dz |
|---|---|---|---|---|---|---|
| b | 0.5 | 0.1 | 0.9 | 0.0312 | 0.0600 | 1.500 |
| c | -0.25 | -0.5 | 0 | 0.5000 | — | -0.200 |
"""
        self.assertEqual(text, expected)

    def test_markdown_golden_higher_no_comparisons(self):
        sweep = _sweep_fixture(lower_is_better=False)
        text = self._export(sweep, "export_markdown")
        self.assertIn("(higher is better)", text)
        self.assertNotIn("Paired comparisons", text)

    def test_html_verdict_default_and_threaded(self):
        sweep = _sweep_fixture()
        default = self._export(sweep, "export_html")
        self.assertNotIn("Verdict", default)
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner([_result(1.0)]))
            path = executor.export_html(sweep, verdict="go <b>now</b>")
            threaded = path.read_text(encoding="utf-8")
        self.assertIn("Verdict:", threaded)
        self.assertIn("go &lt;b&gt;now&lt;/b&gt;", threaded)


class RunOnceTests(unittest.TestCase):
    def _executor(self, tmp, script, **manifest_kwargs):
        return _make_executor(Path(tmp), _ScriptRunner(script), **manifest_kwargs)

    def test_ok_path_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = self._executor(tmp, [_result(1.5)])
            run = executor._run_once("a", 0, seed=7, warmup=False, variant=None)
        self.assertEqual(
            (run.candidate, run.seed, run.metric, run.value, run.seconds, run.ok),
            ("a", 7, "time", 1.5, 1.5, True),
        )
        call = target.runner.calls[0]
        self.assertEqual(call["command"], "bench --x")
        self.assertEqual(call["env"], {"BASE": "1", "MY_SEED": "7"})
        self.assertIsNone(call["seed"])

    def test_failed_result_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = self._executor(tmp, [_result(0.5, rc=1)])
            run = executor._run_once("a", 0, seed=7, warmup=False, variant=None)
        self.assertEqual((run.value, run.seconds, run.ok), (float("inf"), 0.5, False))

    def test_parse_failure_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = self._executor(
                tmp, [_result(0.5, out="garbage")], metrics_parser="json_stdout"
            )
            run = executor._run_once("a", 0, seed=7, warmup=False, variant=None)
        self.assertEqual((run.value, run.ok), (float("inf"), False))

    def test_nonfinite_value_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = self._executor(
                tmp,
                [_result(0.5, out="v=inf")],
                metrics_parser=r"regex:v=(\S+)",
            )
            run = executor._run_once("a", 0, seed=7, warmup=False, variant=None)
        self.assertEqual(run.value, float("inf"))
        self.assertFalse(run.ok)

    def test_warmup_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = self._executor(tmp, [_result(0.5, rc=1)])
            run = executor._run_once("a", 0, seed=7, warmup=True, variant=None)
        self.assertEqual((run.value, run.ok), (0.0, False))

    def test_variant_env_mode(self):
        variant = Variant(name="v", mode="env", args=["--a", "--b"])
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = self._executor(tmp, [_result(1.0)])
            executor._run_once("a", 0, seed=7, warmup=False, variant=variant)
        call = target.runner.calls[0]
        self.assertEqual(call["command"], "bench --x --a --b")
        self.assertEqual(call["env"], {"V_MODE": "env", "V_SEED": "7"})
        self.assertEqual(target.variant_env_calls, [(variant, 7)])
        self.assertEqual(target.apply_calls, [])

    def test_variant_branch_by_mode(self):
        for mode, expect_env_branch in (
            ("args", True),
            ("profile", True),
            ("patch", False),
        ):
            variant = Variant(name="v", mode=mode)
            with tempfile.TemporaryDirectory() as tmp:
                executor, target = self._executor(tmp, [_result(1.0)])
                executor._run_once("a", 0, seed=7, warmup=False, variant=variant)
            if expect_env_branch:
                self.assertEqual(len(target.variant_env_calls), 1, mode)
                self.assertEqual(target.apply_calls, [], mode)
            else:
                self.assertEqual(target.apply_calls, [variant], mode)
                self.assertEqual(target.revert_calls, [("SNAP", variant)], mode)
                call = target.runner.calls[0]
                self.assertEqual(call["env"], {"BASE": "1", "MY_SEED": "7"})


class CandidateTests(unittest.TestCase):
    def test_warmup_count_and_seed(self):
        script = [_result(1.0)] * 4
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = _make_executor(
                Path(tmp), _ScriptRunner(script), warmup=2
            )
            runs = executor.benchmark_candidate("a", [5, 6], variant=None)
        self.assertEqual(len(target.runner.calls), 4)  # 2 warmup + 2 measured
        self.assertEqual(len(runs), 2)
        self.assertEqual(target.runner.calls[0]["env"]["MY_SEED"], "5")
        self.assertEqual(target.runner.calls[1]["env"]["MY_SEED"], "5")
        self.assertEqual(target.runner.calls[2]["env"]["MY_SEED"], "5")
        self.assertEqual(target.runner.calls[3]["env"]["MY_SEED"], "6")

    def test_no_warmup_when_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)] * 2), warmup=0
            )
            executor.benchmark_candidate("a", [5, 6], variant=None)
        self.assertEqual(len(target.runner.calls), 2)

    def test_warmup_threads_variant_and_seed(self):
        variant = Variant(name="v", mode="env", args=["--fast"])
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)] * 2), warmup=1
            )
            executor.benchmark_candidate("a", [5], variant=variant)
        warmup_call = target.runner.calls[0]
        self.assertEqual(warmup_call["command"], "bench --x --fast")
        self.assertEqual(warmup_call["env"]["V_SEED"], "5")

    def test_warmup_empty_seeds_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)]), warmup=1
            )
            runs = executor.benchmark_candidate("a", [], variant=None)
        self.assertEqual(runs, [])
        self.assertEqual(target.runner.calls[0]["env"]["MY_SEED"], "101")

    def test_repeats_floor_and_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)] * 2), repeats=0
            )
            runs = executor.benchmark_candidate("a", [1, 2], variant=None)
        self.assertEqual(len(runs), 2)  # max(1, 0): one run per seed
        self.assertEqual([run.seed for run in runs], [1, 2])
        self.assertEqual(target.prepare_calls, [1, 2])

    def test_adaptive_default_off_explicit_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)] * 5), repeats=5
            )
            runs = executor.benchmark_candidate("a", [1], variant=None)
        self.assertEqual(len(runs), 5)  # default: full repeats
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)] * 5), repeats=5
            )
            runs = executor.benchmark_candidate(
                "a", [1], variant=None, adaptive_repeats=True
            )
        self.assertEqual(len(runs), 2)  # constant: stops at r=2

    def test_no_command_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(
                Path(tmp), _ScriptRunner([_result(1.0)]), benchmark_command=""
            )
            with self.assertRaises(RuntimeError):
                executor.benchmark_candidate("a", [1], variant=None)


class SweepTests(unittest.TestCase):
    def test_full_sweep_default_baseline(self):
        script = [_result(10.0)] * 3 + [_result(5.0)] * 3
        with tempfile.TemporaryDirectory() as tmp:
            executor, target = _make_executor(Path(tmp), _ScriptRunner(script))
            sweep = executor.sweep({"a": None, "b": None}, [1, 2, 3])
        self.assertEqual(len(sweep.comparisons), 1)
        payload = sweep.comparisons[0]
        self.assertEqual(payload["baseline"], "a")
        self.assertEqual(payload["candidate"], "b")
        self.assertEqual(payload["mean_delta"], 5.0)  # lower-better: b faster
        self.assertEqual(payload["confidence"], 0.95)
        self.assertEqual(sweep.target, str(target.root))
        self.assertIs(sweep.partial, False)

    def test_confidence_threaded(self):
        script = [_result(10.0)] * 3 + [_result(5.0)] * 3
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner(script))
            sweep = executor.sweep({"a": None, "b": None}, [1, 2, 3], confidence=0.99)
        self.assertEqual(sweep.comparisons[0]["confidence"], 0.99)

    def test_explicit_and_ghost_baseline(self):
        script = [_result(10.0)] * 3 + [_result(5.0)] * 3
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner(script))
            sweep = executor.sweep({"a": None, "b": None}, [1, 2, 3], baseline="b")
        payload = sweep.comparisons[0]
        self.assertEqual((payload["baseline"], payload["candidate"]), ("b", "a"))
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner(script))
            sweep = executor.sweep({"a": None, "b": None}, [1, 2, 3], baseline="ghost")
        self.assertEqual(sweep.comparisons, [])

    def test_two_shared_seeds_still_compares(self):
        script = [_result(10.0)] * 3 + [_result(5.0)] * 2 + [_result(0.5, rc=1)]
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner(script))
            sweep = executor.sweep({"a": None, "b": None}, [1, 2, 3])
        self.assertEqual(len(sweep.comparisons), 1)  # shared {1,2}: not skipped

    def test_direction_flips_for_higher_better(self):
        script = [_result(10.0)] * 3 + [_result(5.0)] * 3
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(
                Path(tmp), _ScriptRunner(script), lower_is_better=False
            )
            sweep = executor.sweep({"a": None, "b": None}, [1, 2, 3])
        self.assertEqual(sweep.comparisons[0]["mean_delta"], -5.0)

    def test_empty_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner([_result(1.0)]))
            sweep = executor.sweep({}, [1, 2])
        self.assertEqual((sweep.summaries, sweep.comparisons), ([], []))
        self.assertIs(sweep.partial, False)

    def test_interrupted_mid_sweep(self):
        script = [_result(10.0)] * 3 + [KeyboardInterrupt()]
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(Path(tmp), _ScriptRunner(script))
            with self.assertRaises(SweepInterrupted) as ctx:
                executor.sweep({"a": None, "b": None}, [1, 2, 3])
        partial = ctx.exception.sweep
        self.assertIsNotNone(partial)
        assert partial is not None
        self.assertIs(partial.partial, True)
        self.assertEqual([s.candidate for s in partial.summaries], ["a"])

    def test_interrupted_before_any_measurement_stays_plain(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = _make_executor(
                Path(tmp), _ScriptRunner([KeyboardInterrupt()])
            )
            with self.assertRaises(KeyboardInterrupt) as ctx:
                executor.sweep({"a": None, "b": None}, [1, 2, 3])
        self.assertNotIsInstance(ctx.exception, SweepInterrupted)


class InitTests(unittest.TestCase):
    def test_nested_export_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = _ScriptRunner([_result(1.0)])
            target = _make_target(Path(tmp), runner)
            nested = Path(tmp) / "a" / "b"
            BenchmarkExecutor(target, export_dir=nested)
            self.assertTrue(nested.is_dir())


if __name__ == "__main__":
    unittest.main()
