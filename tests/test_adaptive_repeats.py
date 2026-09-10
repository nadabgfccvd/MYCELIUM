"""V4.2: adaptive repeats — fewer runs, identical verdicts (kill-gated).

Kill gate (permanent): the online rule simulated on the replay corpus must
produce ZERO verdict flips. Live test: deterministic bench stops at 2/seed.
"""
from __future__ import annotations

import json
import tempfile
import pytest
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import decide_best_candidate
from mycelium_accel.bench import BenchmarkSweep, adaptive_stop, summarize_runs
from test_verdict_equivalence import EXPECTED

REPLAY = Path(__file__).resolve().parent / "replay"


def online_truncate(runs):
    by_seed: dict[int, list] = {}
    for run in runs:
        by_seed.setdefault(run.seed, []).append(run)
    out = []
    for seed in sorted(by_seed):
        seen: list[float] = []
        for run in by_seed[seed]:
            out.append(run)
            if not run.ok:
                break
            seen.append(run.value)
            if adaptive_stop(seen):
                break
    return out


class AdaptiveRuleTests(unittest.TestCase):
    def test_tight_stops(self) -> None:
        self.assertTrue(adaptive_stop([1.0, 1.001, 0.999]))

    def test_noisy_runs_on(self) -> None:
        self.assertFalse(adaptive_stop([1.0, 1.5, 0.7]))

    def test_min_two_repeats(self) -> None:
        self.assertFalse(adaptive_stop([1.0]))

    def test_zero_mean_never_stops(self) -> None:
        self.assertFalse(adaptive_stop([0.0, 0.0, 0.0]))

    def test_replay_simulation_zero_flips(self) -> None:
        # THE kill gate: any future rule change must keep this green.
        for name, expected in EXPECTED.items():
            with self.subTest(sweep=name):
                raw = json.loads((REPLAY / name).read_text(encoding="utf-8"))
                sweep = BenchmarkSweep.from_dict(raw)
                sim = BenchmarkSweep(
                    target=sweep.target, metric=sweep.metric,
                    lower_is_better=sweep.lower_is_better,
                    summaries=[summarize_runs(s.candidate, online_truncate(s.runs))
                               for s in sweep.summaries],
                    comparisons=[], started_at=sweep.started_at)
                best, _r, _c = decide_best_candidate(sim, "baseline")
                self.assertEqual(best, expected)

    @pytest.mark.slow
    def test_live_deterministic_stops_at_two(self) -> None:
        from mycelium_accel.accelerate_generic import accelerate_target

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bench.py").write_text(
                "import json\nprint(json.dumps({'seconds': 0.042}))\n", encoding="utf-8")
            (root / "mycelium.target.json").write_text(json.dumps({
                "benchmark_command": "python bench.py", "metrics_parser": "json_stdout",
                "manifest_version": "1.0", "repeats": 5}), encoding="utf-8")
            full = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            adapt = accelerate_target(root, seeds=[101, 103, 107], apply=False,
                                      adaptive_repeats=True)
            full_runs = sum(len(s["runs"]) for s in
                            json.loads(Path(full.sweep_path).read_text(encoding="utf-8"))["summaries"])
            adapt_runs = sum(len(s["runs"]) for s in
                             json.loads(Path(adapt.sweep_path).read_text(encoding="utf-8"))["summaries"])
            self.assertEqual(full_runs, 15)   # 3 seeds x 5
            self.assertEqual(adapt_runs, 6)   # 3 seeds x 2 (stopped early)
            self.assertEqual(adapt.best_candidate, full.best_candidate)


if __name__ == "__main__":
    unittest.main()
