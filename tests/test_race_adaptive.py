"""S3: adaptive racing screen — same eliminations, fewer screen runs.

Kill gate (permanent): the 2-seed+borderline rule simulated on the replay
corpus must match the 3-seed rule on every challenger AND save >=10% of
screen runs. Live test: same verdict as plain racing with fewer measured runs.
"""
from __future__ import annotations

import json
import tempfile
import pytest
import unittest
from pathlib import Path
from unittest.mock import patch

from mycelium_accel.accelerate_generic import accelerate_target
from mycelium_accel.bench import BenchmarkExecutor, BenchmarkSweep
from mycelium_accel.stats import compare_paired_metric
from test_racing import _make_target
from test_racing_recall import screen_eliminated

REPLAY = Path(__file__).resolve().parent / "replay"


def adaptive_eliminated(sweep: BenchmarkSweep, candidate: str) -> tuple[bool, bool]:
    """Mirror of the S3 rule. Returns (eliminated, extended_to_3rd_seed)."""
    base = next(s for s in sweep.summaries if s.candidate == "baseline")
    cand = next(s for s in sweep.summaries if s.candidate == candidate)

    def first_runs(summary, n):
        seen: dict[int, float] = {}
        for run in summary.runs:
            if run.ok and run.seed not in seen:
                seen[run.seed] = run.value
        return {s: seen[s] for s in sorted(seen)[:n]}

    def comp(n):
        bm, cm = first_runs(base, n), first_runs(cand, n)
        shared = sorted(set(bm) & set(cm))
        if len(shared) < 2:
            return None
        direction = -1 if sweep.lower_is_better else 1
        return compare_paired_metric(
            sweep.metric, [bm[s] for s in shared], [cm[s] for s in shared],
            direction=direction, confidence=0.95)

    c2 = comp(2)
    if c2 is None:
        return screen_eliminated(sweep, candidate), True
    width = max(c2.ci_high - c2.ci_low, 1e-12)
    if abs(c2.ci_high - 0.0) < 0.25 * width:
        c3 = comp(3)
        return (c3.ci_high < 0.0) if c3 is not None else False, True
    return c2.ci_high < 0.0, False


class AdaptiveRacingTests(unittest.TestCase):
    def test_replay_simulation_matches_and_saves(self) -> None:
        screen_runs, saved = 0, 0
        for name in ("replay_win.json", "replay_loss.json", "replay_raced.json"):
            sweep = BenchmarkSweep.from_dict(
                json.loads((REPLAY / name).read_text(encoding="utf-8")))
            cands = [s.candidate for s in sweep.summaries if s.candidate != "baseline"]
            screen_runs += (1 + len(cands)) * 3
            extended_any = False
            for cand in cands:
                with self.subTest(sweep=name, candidate=cand):
                    elim_adapt, extended = adaptive_eliminated(sweep, cand)
                    self.assertEqual(elim_adapt, screen_eliminated(sweep, cand))
                    if extended:
                        extended_any = True
                    else:
                        saved += 1
            if not extended_any:
                saved += 1  # baseline 3rd seed also skipped
        self.assertGreaterEqual(saved / screen_runs, 0.10)

    @pytest.mark.slow
    def test_live_same_verdict_fewer_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_target(tmp)
            seeds = [101, 103, 107, 109, 113, 127, 131]
            real = BenchmarkExecutor._run_once
            calls: list[int] = []

            def counting(self, *a, **k):
                calls.append(1)
                return real(self, *a, **k)

            with patch.object(BenchmarkExecutor, "_run_once", counting):
                plain = accelerate_target(root, seeds=seeds, apply=False,
                                          race=True, race_seeds=3)
                n_plain = len(calls)
                adapt = accelerate_target(root, seeds=seeds, apply=False,
                                          race=True, race_seeds=3, race_adaptive=True)
                n_adapt = len(calls) - n_plain
            self.assertEqual(adapt.best_candidate, plain.best_candidate)
            self.assertEqual(sorted(adapt.raced_candidates), sorted(plain.raced_candidates))
            self.assertLess(n_adapt, n_plain)


if __name__ == "__main__":
    unittest.main()
