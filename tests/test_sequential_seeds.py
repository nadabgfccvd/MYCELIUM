"""S1: group-sequential seeds (OBF look at 6/7) — stop early, same verdicts.

Pre-registered (API §7): Type I sim 0.0335, 0 replay flips, 14.2% savings on
decisive effects. The replay test below is the permanent kill-gate.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest

from mycelium_accel.accelerate_generic import (
    decide_best_candidate,
    sequential_look,
)
from mycelium_accel.accelerate_generic import accelerate_target
from mycelium_accel.bench import BenchmarkSweep, summarize_runs
from mycelium_accel.stats import AcceptancePolicy
from test_verdict_equivalence import EXPECTED

REPLAY = Path(__file__).resolve().parent / "replay"
SEEDS7 = [101, 103, 107, 109, 113, 127, 131]

BENCH = (
    "import json, os\n"
    "fast = os.environ.get('MODE') == 'fast'\n"
    "print(json.dumps({'seconds': 0.01 if fast else 0.05}))\n"
)
BENCH_NOOP = "import json\nprint(json.dumps({'seconds': 0.042}))\n"


def make_target(root: Path, bench: str, variants: list[dict]) -> None:
    (root / "bench.py").write_text(bench, encoding="utf-8")
    (root / "mycelium.target.json").write_text(json.dumps({
        "benchmark_command": "python bench.py", "metrics_parser": "json_stdout",
        "manifest_version": "1.0", "repeats": 2, "warmup": 0,
        "variants": variants}), encoding="utf-8")


class SequentialReplayTests(unittest.TestCase):
    def test_sequential_verdicts_equal_recorded(self) -> None:
        for name, expected in EXPECTED.items():
            with self.subTest(sweep=name):
                sweep = BenchmarkSweep.from_dict(
                    json.loads((REPLAY / name).read_text(encoding="utf-8")))
                seeds6 = sorted({r.seed for s in sweep.summaries for r in s.runs})[:6]
                trunc = BenchmarkSweep(
                    sweep.target, sweep.metric, sweep.lower_is_better,
                    [summarize_runs(s.candidate, [r for r in s.runs if r.seed in seeds6])
                     for s in sweep.summaries], [], sweep.started_at)
                stopped = sequential_look(trunc)
                if stopped is not None:
                    self.assertEqual(stopped, expected)
                else:
                    best, _, _ = decide_best_candidate(
                        sweep, "baseline", policy=AcceptancePolicy())
                    self.assertEqual(best, expected)


class SequentialLiveTests(unittest.TestCase):
    @pytest.mark.slow
    def test_decisive_stops_at_six(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root, BENCH, [{"name": "fast", "mode": "env", "env": {"MODE": "fast"}}])
            seq = accelerate_target(root, seeds=SEEDS7, apply=False, sequential_seeds=True)
            full = accelerate_target(root, seeds=SEEDS7, apply=False)
            self.assertEqual(seq.best_candidate, "fast")
            self.assertEqual(seq.best_candidate, full.best_candidate)
            sweep = json.loads(Path(seq.sweep_path).read_text(encoding="utf-8"))
            seeds_seen = {r["seed"] for s in sweep["summaries"] for r in s["runs"]}
            self.assertEqual(len(seeds_seen), 6)
            self.assertTrue(any("stopped at 6/7" in r for r in seq.decision_reasons))

    @pytest.mark.slow
    def test_close_continues_to_seven(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root, BENCH_NOOP, [{"name": "noop", "mode": "env", "env": {"X": "1"}}])
            seq = accelerate_target(root, seeds=SEEDS7, apply=False, sequential_seeds=True)
            self.assertIsNone(seq.best_candidate)
            sweep = json.loads(Path(seq.sweep_path).read_text(encoding="utf-8"))
            seeds_seen = {r["seed"] for s in sweep["summaries"] for r in s["runs"]}
            self.assertEqual(len(seeds_seen), 7)
            self.assertTrue(any("continued to 7/7" in r for r in seq.decision_reasons))

    def test_requires_exactly_seven_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_target(root, BENCH_NOOP, [])
            with self.assertRaises(ValueError) as ctx:
                accelerate_target(root, seeds=[101, 103, 107], apply=False,
                                  sequential_seeds=True)
            self.assertIn("exactly 7 seeds", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
