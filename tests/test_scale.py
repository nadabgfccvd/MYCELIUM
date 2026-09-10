"""Q2.3 — scale smoke: 50 variants x 10 seeds stay CORRECT (not fast).

The subprocess fan-out is linear by construction; what could hide O(n^2) is
decide + Holm + the four exporters. So this test synthesizes the sweep in
memory (no subprocesses) and pins: right winner, all artifacts written, HTML
mentions the winner, and a generous wall-clock bound against blowups.
"""
from __future__ import annotations

import random
import tempfile
import time
import unittest
from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402

from mycelium_accel.accelerate_generic import decide_best_candidate  # noqa: E402
from mycelium_accel.bench import BenchmarkExecutor, BenchmarkSweep  # noqa: E402
from mycelium_accel.targets import load_target  # noqa: E402

SEEDS = [101, 103, 107, 109, 113, 127, 131, 137, 139, 149]


def _big_sweep(n_variants: int = 50) -> BenchmarkSweep:
    rng = random.Random(20260910)

    def runs(values: list[float], name: str) -> list[dict]:
        return [
            {"candidate": name, "seed": s, "metric": "seconds",
             "value": v, "seconds": 0.01, "ok": True}
            for s, v in zip(SEEDS, values)
        ]

    summaries = [{
        "candidate": "baseline",
        "runs": runs([1.0 + rng.gauss(0, 0.01) for _ in SEEDS], "baseline"),
        "mean": 1.0, "stddev": 0.01, "median": 1.0, "minimum": 0.9, "maximum": 1.1,
    }]
    for i in range(n_variants):
        if i == 7:  # planted winner, ~15% better, tight
            values = [0.85 + rng.gauss(0, 0.005) for _ in SEEDS]
        else:  # noise around baseline (half slightly better, never significant)
            shift = rng.uniform(-0.02, 0.02)
            values = [1.0 + shift + rng.gauss(0, 0.03) for _ in SEEDS]
        summaries.append({
            "candidate": f"v{i:02d}",
            "runs": runs(values, f"v{i:02d}"),
            "mean": 0.0, "stddev": 0.0, "median": 0.0, "minimum": 0.0, "maximum": 0.0,
        })
    return BenchmarkSweep.from_dict({
        "target": "scale", "metric": "seconds", "lower_is_better": True,
        "summaries": summaries,
    })


class ScaleTests(unittest.TestCase):
    def test_50x10_decide_and_export(self) -> None:
        sweep = _big_sweep()
        started = time.perf_counter()
        best, _reasons, comparisons = decide_best_candidate(sweep, "baseline")
        decide_seconds = time.perf_counter() - started
        self.assertEqual(best, "v07")
        self.assertEqual(len(comparisons), 50)
        self.assertLess(decide_seconds, 30.0)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            executor = BenchmarkExecutor(load_target(root, None))
            sweep.comparisons = comparisons
            started = time.perf_counter()
            json_path = executor.export_json(sweep)
            csv_path = executor.export_csv(sweep)
            md_path = executor.export_markdown(sweep)
            html_path = executor.export_html(sweep, verdict="v07 accepted")
            export_seconds = time.perf_counter() - started
            for path in (json_path, csv_path, md_path, html_path):
                self.assertTrue(path.is_file(), path)
            self.assertIn("v07", html_path.read_text(encoding="utf-8"))
            self.assertLess(export_seconds, 30.0)


if __name__ == "__main__":
    unittest.main()
