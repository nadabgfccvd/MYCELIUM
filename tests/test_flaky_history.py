"""H1.2: flakiness rule (API §5, advisory) + history command."""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import pytest
import unittest
from pathlib import Path

from mycelium_accel.bench import BenchmarkRun, is_flaky
from mycelium_accel.history import history_html, load_sweeps

ROOT = Path(__file__).resolve().parents[1]


def runs(seed_means: dict[int, float], per_seed: int = 2) -> list[BenchmarkRun]:
    out = []
    for seed, mean in seed_means.items():
        for _ in range(per_seed):
            out.append(BenchmarkRun("c", seed, "seconds", mean, 0.01, True))
    return out


class FlakyTests(unittest.TestCase):
    def test_stable_is_not_flaky(self) -> None:
        self.assertFalse(is_flaky(runs({101: 1.0, 103: 1.01, 107: 0.99, 109: 1.0})))

    def test_bimodal_is_flaky(self) -> None:
        self.assertTrue(is_flaky(runs({101: 0.01, 103: 0.05, 107: 0.01})))

    def test_fewer_than_3_seeds_is_not_flaky(self) -> None:
        self.assertFalse(is_flaky(runs({101: 0.01, 103: 0.50})))

    @pytest.mark.slow
    def test_flaky_end_to_end_warns_without_changing_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bench.py").write_text(
                "import json, os\nseed = int(os.environ.get('MYCELIUM_SEED', '101'))\n"
                "print(json.dumps({'seconds': 0.05 if seed % 2 else 0.01}))\n",
                encoding="utf-8")
            Path(tmp, "mycelium.target.json").write_text(json.dumps({
                "benchmark_command": "python bench.py", "metrics_parser": "json_stdout",
                "manifest_version": "1.0"}), encoding="utf-8")
            proc = cli("accelerate",
                 "--target", tmp, "--no-apply", "--seeds", "101,102,103")  # mixed parity -> bimodal
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outcome = json.loads(proc.stdout)
            self.assertTrue(any("flaky" in r for r in outcome["decision_reasons"]))
            sweep = json.loads(Path(outcome["sweep_path"]).read_text(encoding="utf-8"))
            self.assertTrue(sweep["summaries"][0]["flaky"])


def fake_sweep(ts: float, means: dict[str, float]) -> dict:
    return {"target": "t", "metric": "seconds", "lower_is_better": True,
            "started_at": ts,
            "summaries": [{"candidate": n, "mean": m, "stddev": m * 0.05, "runs": []}
                          for n, m in means.items()],
            "comparisons": []}


class HistoryTests(unittest.TestCase):
    def test_load_sweeps_sorted_skips_garbage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp)
            (bench / "sweep-2.json").write_text(json.dumps(fake_sweep(2.0, {"baseline": 1.0})), encoding="utf-8")
            (bench / "sweep-1.json").write_text(json.dumps(fake_sweep(1.0, {"baseline": 1.2})), encoding="utf-8")
            (bench / "sweep-bad.json").write_text("not json", encoding="utf-8")
            sweeps = load_sweeps(bench)
            self.assertEqual([s["started_at"] for s in sweeps], [1.0, 2.0])

    def test_history_html_offline_charts(self) -> None:
        out = history_html([fake_sweep(1.0, {"baseline": 1.2, "fast": 0.9}),
                            fake_sweep(2.0, {"baseline": 1.1, "fast": 0.8})])
        self.assertIn("<svg", out)
        self.assertIn("fast", out)
        self.assertNotIn("http", out)
        self.assertNotIn("<script", out)

    def test_history_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp) / ".mycelium_benchmarks"
            bench.mkdir()
            for i, means in enumerate(({"baseline": 1.2}, {"baseline": 1.1})):
                (bench / f"sweep-{i}.json").write_text(
                    json.dumps(fake_sweep(float(i), means)), encoding="utf-8")
            proc = cli("history", "--target", tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((bench / "history.html").exists())

    def test_history_needs_two_sweeps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp) / ".mycelium_benchmarks"
            bench.mkdir()
            (bench / "sweep-0.json").write_text(
                json.dumps(fake_sweep(0.0, {"baseline": 1.0})), encoding="utf-8")
            proc = cli("history", "--target", tmp)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("≥2 sweeps", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
