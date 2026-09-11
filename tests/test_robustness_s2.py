"""Sessão 2, Ciclo 4 — fault injection / robustness guards.

Locks down three classes of failure that previously surfaced as raw
tracebacks or incomplete cleanup:

* a benchmark that prints a non-numeric metric (or a bad/un-grouped regex)
  must fail the *run* (RuntimeError -> inf -> honest rejection), never crash
  the sweep;
* huge-but-finite measurements must degrade to non-accepting statistics, not
  raise OverflowError (M3 contract);
* a 'patch' variant whose source is missing must raise AND leave no temp
  snapshot dir and no partially injected file.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.bench import parse_metrics
from mycelium_accel.stats import bca_bootstrap_ci, effect_size
from mycelium_accel.targets.base import (
    ProjectTarget,
    TargetManifest,
    TargetRunResult,
    Variant,
)


def _run(stdout: str = "", returncode: int = 0, seconds: float = 0.1) -> TargetRunResult:
    return TargetRunResult(
        command=["x"], returncode=returncode, seconds=seconds,
        stdout_tail=stdout, stderr_tail="")


class MetricParsingRobustnessTests(unittest.TestCase):
    def test_valid_parsers_still_extract(self) -> None:
        good_json = 'noise\n{"other": 1, "seconds": 0.123}\n'
        self.assertEqual(parse_metrics(_run(good_json), "json_stdout", "seconds"),
                         {"seconds": 0.123})
        self.assertEqual(
            parse_metrics(_run("time=0.456\n"), r"regex:time=(?P<seconds>\S+)", "seconds"),
            {"seconds": 0.456})
        self.assertEqual(parse_metrics(_run(seconds=0.9), "time", "seconds"),
                         {"seconds": 0.9})

    def test_non_numeric_metric_fails_run_not_sweep(self) -> None:
        with self.assertRaises(RuntimeError):
            parse_metrics(_run('{"seconds": "fast"}\n'), "json_stdout", "seconds")
        with self.assertRaises(RuntimeError):
            parse_metrics(_run('{"seconds": null}\n'), "json_stdout", "seconds")
        with self.assertRaises(RuntimeError):
            parse_metrics(_run("time=abc\n"), r"regex:time=(?P<seconds>\S+)", "seconds")
        with self.assertRaises(RuntimeError):
            parse_metrics(_run('{"seconds": "x"}\n'), r"regex:(?P<seconds>.*)", "seconds")

    def test_invalid_regex_is_runtime_error(self) -> None:
        with self.assertRaises(RuntimeError):
            parse_metrics(_run("x"), "regex:(unclosed", "seconds")

    def test_regex_without_group_is_runtime_error_on_match(self) -> None:
        with self.assertRaises(RuntimeError):
            parse_metrics(_run("plainmatch\n"), "regex:plainmatch", "seconds")

    def test_unknown_parser_is_value_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_metrics(_run("x"), "binary_ast", "seconds")

    def test_broken_baseline_metric_is_honestly_rejected_end_to_end(self) -> None:
        from mycelium_accel.accelerate_generic import accelerate_target
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bench.py").write_text("print('{\"seconds\": \"oops\"}')")
            manifest = {"name": "x", "kind": "shell",
                        "benchmark_command": "python3 bench.py",
                        "metrics_parser": "json_stdout", "metric_name": "seconds",
                        "warmup": 0, "repeats": 1, "variants": []}
            (root / "mycelium.target.json").write_text(json.dumps(manifest))
            out = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            self.assertIsNone(out.best_candidate)
            self.assertIn("no successful runs", out.decision_reasons[0])


class HugeFiniteInputTests(unittest.TestCase):
    def test_huge_finite_values_degrade_without_overflow(self) -> None:
        for data in ([1e308] * 7, [-1e308] * 7,
                     [1e308, 1e308, 1e307, 1e308, 1e308, 1e307, 1e308]):
            lo, hi = bca_bootstrap_ci(data, n_bootstrap=200)
            # bounds must not be finite-positive -> such data never wins
            self.assertFalse(lo > 0.0 and math.isfinite(lo))
            dz, _median, _prob = effect_size(data)  # must not raise OverflowError
            self.assertTrue(math.isnan(dz) or math.isinf(dz) or math.isfinite(dz))


class MissingPatchSourceTests(unittest.TestCase):
    def test_missing_source_cleans_up_and_does_not_inject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["TMPDIR"] = tmp
            try:
                root = Path(tempfile.mkdtemp())
                manifest = TargetManifest.from_dict(
                    {"name": "r", "kind": "shell", "warmup": 0, "repeats": 1})
                target = ProjectTarget(root, manifest)
                variant = Variant(
                    name="miss", mode="patch",
                    files={"dest.py": str(root / "does_not_exist_src.py")})
                snapshots = list(Path(tmp).glob("mycelium-snapshot-*"))
                with self.assertRaises(FileNotFoundError):
                    target.apply_variant(variant)
                self.assertFalse((root / "dest.py").exists())
                # failed snapshot cleaned itself up (no leaked backup dir growth)
                self.assertEqual(list(Path(tmp).glob("mycelium-snapshot-*")), snapshots)
            finally:
                os.environ.pop("TMPDIR", None)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
