"""Fase 3.1: racing screen — drops futile candidates, keeps winner, saves time."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow
import json
import tempfile
import time
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import accelerate_target

BENCH = """import json, os, time
n = {"fast": 25000, "slow": 1000000}.get(os.environ.get("RACE_MODE", ""), 250000)
t0 = time.perf_counter()
s = sum(i * i for i in range(n))
print(json.dumps({"seconds": time.perf_counter() - t0, "s": s}))
"""

MANIFEST = {
    "name": "race-test",
    "kind": "python",
    "benchmark_command": "python benchmark.py",
    "metrics_parser": "json_stdout",
    "metric_name": "seconds",
    "lower_is_better": True,
    "warmup": 0,
    "repeats": 2,
    "variants": [
        {"name": "fast", "mode": "env", "env": {"RACE_MODE": "fast"}},
        {"name": "slow", "mode": "env", "env": {"RACE_MODE": "slow"}},
    ],
}


def _make_target(tmp: str) -> Path:
    root = Path(tmp) / "tgt"
    root.mkdir()
    (root / "benchmark.py").write_text(BENCH, encoding="utf-8")
    (root / "mycelium.target.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    return root


class RacingTests(unittest.TestCase):
    def test_race_drops_slow_keeps_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_target(tmp)
            t0 = time.perf_counter()
            full = accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131], apply=False)
            full_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            raced = accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131], apply=False,
                                      race=True, race_seeds=2)
            race_s = time.perf_counter() - t0
        self.assertEqual(full.best_candidate, "fast")
        self.assertEqual(raced.best_candidate, "fast")
        self.assertIn("slow", raced.raced_candidates)
        self.assertNotIn("fast", raced.raced_candidates)
        self.assertLess(race_s, full_s)

    def test_race_skipped_with_single_challenger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tgt"
            root.mkdir()
            (root / "benchmark.py").write_text(BENCH, encoding="utf-8")
            single = dict(MANIFEST)
            single["variants"] = [MANIFEST["variants"][0]]
            (root / "mycelium.target.json").write_text(json.dumps(single), encoding="utf-8")
            outcome = accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131], apply=False, race=True)
        self.assertEqual(outcome.raced_candidates, [])
        self.assertTrue(any("pure overhead" in r for r in outcome.decision_reasons))


if __name__ == "__main__":
    unittest.main()
