"""H1.3: --reference/--fail-on-regression CI gate (API §5, dual criterion)."""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import pytest
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import check_regression

ROOT = Path(__file__).resolve().parents[1]

def bench_src(value: float) -> str:
    return f"import json\nprint(json.dumps({{'seconds': {value}}}))\n"
MANIFEST = {
    "benchmark_command": "python bench.py", "metrics_parser": "json_stdout",
    "manifest_version": "1.0", "repeats": 2, "warmup": 0,
}


def run_gate(tmp: str, *extra: str):
    return cli("accelerate",
               "--target", tmp, "--no-apply", "--seeds", "101,103,107", *extra)


class RegressionUnitTests(unittest.TestCase):
    def test_clear_regression_trips(self) -> None:
        bad, reason = check_regression(
            [0.05, 0.051, 0.049], [0.01, 0.0101, 0.0099], 5.0, lower_is_better=True)
        self.assertTrue(bad)
        self.assertIn("REGRESSION", reason)

    def test_same_speed_passes(self) -> None:
        bad, _ = check_regression(
            [0.01, 0.0101, 0.0099], [0.01, 0.01, 0.0102], 5.0, lower_is_better=True)
        self.assertFalse(bad)

    def test_small_effect_insignificant_passes(self) -> None:
        # 3% worse but noisy: effect under gate AND inside noise -> pass
        bad, _ = check_regression(
            [0.010, 0.011, 0.012], [0.010, 0.010, 0.011], 5.0, lower_is_better=True)
        self.assertFalse(bad)

    def test_higher_is_better_flips(self) -> None:
        bad, _ = check_regression(
            [10.0, 10.1, 9.9], [20.0, 20.1, 19.9], 5.0, lower_is_better=False)
        self.assertTrue(bad)

    def test_insufficient_data_skips(self) -> None:
        bad, reason = check_regression([0.5], [0.01], 5.0, lower_is_better=True)
        self.assertFalse(bad)
        self.assertIn("insufficient data", reason)


class RegressionGateTests(unittest.TestCase):
    @pytest.mark.slow
    def test_gate_fails_on_slow_and_passes_on_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fast, slow_dir = Path(tmp, "fast"), Path(tmp, "slow")
            fast.mkdir()
            slow_dir.mkdir()
            fast.joinpath("bench.py").write_text(bench_src(0.01), encoding="utf-8")
            slow_dir.joinpath("bench.py").write_text(bench_src(0.05), encoding="utf-8")
            for root in (fast, slow_dir):
                root.joinpath("mycelium.target.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
            ref = run_gate(str(fast))
            self.assertEqual(ref.returncode, 0, ref.stderr)
            ref_path = json.loads(ref.stdout)["sweep_path"]
            slow = run_gate(str(slow_dir), "--reference", ref_path, "--fail-on-regression", "5")
            self.assertEqual(slow.returncode, 1, slow.stdout)
            self.assertIn("regression", slow.stderr)
            self.assertNotIn("Traceback", slow.stderr)
            self.assertTrue(json.loads(slow.stdout)["regression"])
            fast = run_gate(str(fast), "--reference", ref_path, "--fail-on-regression", "5")
            self.assertEqual(fast.returncode, 0, fast.stderr)
            self.assertFalse(json.loads(fast.stdout)["regression"])

    @pytest.mark.slow
    def test_incompatible_reference_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bench.py").write_text(bench_src(0.01), encoding="utf-8")
            Path(tmp, "mycelium.target.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
            other = Path(tmp, "other.json")
            other.write_text(json.dumps({
                "metric": "rps", "lower_is_better": False, "summaries": [
                    {"candidate": "baseline", "runs": [
                        {"seed": 101, "value": 5.0, "ok": True}]}]}), encoding="utf-8")
            proc = run_gate(tmp, "--reference", str(other), "--fail-on-regression", "5")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("incompatible", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
