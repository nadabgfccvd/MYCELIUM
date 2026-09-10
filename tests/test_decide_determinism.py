"""Q1.4 — determinism audit of the analysis pipeline.

Scope (honest): MEASUREMENTS inherently vary run to run; what must be
bit-identical is the ANALYSIS (sweep in -> verdict + comparisons out).
Verified across processes with different hash seeds (catches set/dict-order
dependence, the Q0 lesson). Plus decision monotonicity: doubling an established
improvement never un-accepts it.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import decide_best_candidate
from mycelium_accel.bench import BenchmarkSweep

REPLAY = Path(__file__).resolve().parent / "replay"
NAMES = [
    "replay_win.json",
    "replay_loss.json",
    "replay_baseline_only.json",
    "replay_flaky.json",
    "replay_raced.json",
]

_PROBE = "\n".join([
    "import json",
    "from pathlib import Path",
    "from mycelium_accel.accelerate_generic import decide_best_candidate",
    "from mycelium_accel.bench import BenchmarkSweep",
    f"names = {NAMES!r}",
    "d = Path('tests/replay')",
    "out = {}",
    "for n in names:",
    "    sweep = BenchmarkSweep.from_dict(json.loads((d / n).read_text()))",
    "    out[n] = decide_best_candidate(sweep, 'baseline')[2]",
    "print(json.dumps(out, sort_keys=True))",
])


def _make_sweep(base: list[float], cand: list[float]) -> BenchmarkSweep:
    seeds = [101, 103, 107, 109, 113, 127, 131]

    def runs(values: list[float], name: str) -> list[dict]:
        return [
            {"candidate": name, "seed": s, "metric": "seconds",
             "value": v, "seconds": 0.01, "ok": True}
            for s, v in zip(seeds, values)
        ]

    return BenchmarkSweep.from_dict({
        "target": "t", "metric": "seconds", "lower_is_better": True,
        "summaries": [
            {"candidate": "baseline", "runs": runs(base, "baseline"),
             "mean": 0.0, "stddev": 0.0, "median": 0.0, "minimum": 0.0, "maximum": 0.0},
            {"candidate": "cand", "runs": runs(cand, "cand"),
             "mean": 0.0, "stddev": 0.0, "median": 0.0, "minimum": 0.0, "maximum": 0.0},
        ],
    })


class DecideDeterminismTests(unittest.TestCase):
    def test_bit_identical_across_hash_seeds(self) -> None:
        root = Path(__file__).resolve().parent.parent
        outputs = []
        for hash_seed in ("0", "1", "42"):
            proc = subprocess.run(
                [sys.executable, "-c", _PROBE],
                capture_output=True, text=True, cwd=root,
                env={"PYTHONHASHSEED": hash_seed, "PATH": "/usr/bin:/bin:/usr/local/bin"},
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            outputs.append(proc.stdout)
        self.assertEqual(outputs[1], outputs[0])
        self.assertEqual(outputs[2], outputs[0])

    def test_doubling_effect_never_unaccepts(self) -> None:
        base = [1.00, 1.02, 0.98, 1.01, 0.99, 1.03, 0.97]
        cand = [0.80, 0.82, 0.78, 0.81, 0.79, 0.83, 0.77]  # ~20% better
        best, _r, comp = decide_best_candidate(_make_sweep(base, cand), "baseline")
        self.assertEqual(best, "cand")
        ci_low_before = comp[0]["ci_low"]
        doubled = [b + 2.0 * (c - b) for b, c in zip(base, cand)]
        best2, _r2, comp2 = decide_best_candidate(_make_sweep(base, doubled), "baseline")
        self.assertEqual(best2, "cand")
        self.assertGreaterEqual(comp2[0]["ci_low"], ci_low_before)


if __name__ == "__main__":
    unittest.main()
