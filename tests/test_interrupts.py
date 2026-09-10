"""Q2.1 — Ctrl-C degrades gracefully: no tracebacks, orphans die, honest partials.

* CLI exits 130 with a friendly message (all commands, via ``main`` wrapper).
* A sweep cut short exports its honestly-measured prefix (``partial: true``)
  and REFUSES to decide on it (deciding on a lucky subset is survivor bias).
* The runner kills the whole process group on Ctrl-C/timeout (no orphans).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import pytest

from mycelium_accel.accelerate_generic import accelerate_target
from mycelium_accel.bench import (
    BenchmarkExecutor,
    BenchmarkSweep,
    SweepInterrupted,
)
from mycelium_accel.targets import load_target

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402


def _fast_project(root: Path, *, variants: int = 2, sleep: float = 0.05) -> None:
    _make_python_project(root)
    (root / "bench.py").write_text(
        f'import time; time.sleep({sleep}); print(\'{{"seconds": {sleep}, "total": 1}}\')',
        encoding="utf-8",
    )
    if variants != 2:
        manifest = json.loads((root / "mycelium.target.json").read_text())
        base = manifest["variants"]
        manifest["variants"] = [
            {"name": f"{v['name']}-{i}", "mode": "env", "env": dict(v["env"], I=str(i))}
            for i in range(variants)
            for v in base
        ][:variants]
        (root / "mycelium.target.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )


class SweepInterruptTests(unittest.TestCase):
    def test_sweep_carries_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            target = load_target(root, None)
            executor = BenchmarkExecutor(target)
            real = executor.benchmark_candidate
            calls = 0

            def fake(name: str, seeds: list[int], **kwargs):  # noqa: ANN001, ANN202
                nonlocal calls
                calls += 1
                if calls > 1:
                    raise KeyboardInterrupt
                return real(name, seeds, **kwargs)

            executor.benchmark_candidate = fake  # type: ignore[method-assign]
            with self.assertRaises(SweepInterrupted) as ctx:
                executor.sweep({"baseline": None, "fast-mode": None}, [101, 103, 107])
            sweep = ctx.exception.sweep
            self.assertTrue(sweep.partial)
            self.assertEqual([s.candidate for s in sweep.summaries], ["baseline"])
            self.assertTrue(all(s.runs for s in sweep.summaries))

    def test_empty_prefix_stays_plain_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            target = load_target(root, None)
            executor = BenchmarkExecutor(target)

            def boom(name: str, seeds: list[int], **kwargs):  # noqa: ANN001, ANN202
                raise KeyboardInterrupt

            executor.benchmark_candidate = boom  # type: ignore[method-assign]
            with self.assertRaises(KeyboardInterrupt) as ctx:
                executor.sweep({"baseline": None}, [101, 103, 107])
            self.assertNotIsInstance(ctx.exception, SweepInterrupted)

    def test_partial_flag_roundtrip(self) -> None:
        sweep = BenchmarkSweep(
            target="t",
            metric="m",
            lower_is_better=True,
            summaries=[],
            comparisons=[],
            partial=True,
        )
        self.assertTrue(BenchmarkSweep.from_dict(sweep.to_dict()).partial)
        full = BenchmarkSweep(
            target="t", metric="m", lower_is_better=True, summaries=[], comparisons=[]
        )
        self.assertNotIn("partial", full.to_dict())  # old files stay clean


class AccelerateInterruptTests(unittest.TestCase):
    def test_interrupted_outcome_exports_partial_decides_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            carried = BenchmarkSweep(
                target=str(root),
                metric="seconds",
                lower_is_better=True,
                summaries=[],
                comparisons=[],
                partial=True,
            )

            def boom(self, *args, **kwargs):  # noqa: ANN001, ANN202
                raise SweepInterrupted(carried)

            orig = BenchmarkExecutor.sweep
            BenchmarkExecutor.sweep = boom  # type: ignore[method-assign]
            try:
                out = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            finally:
                BenchmarkExecutor.sweep = orig
            self.assertTrue(out.interrupted)
            self.assertIsNone(out.best_candidate)
            self.assertFalse(out.applied)
            self.assertIsNotNone(out.sweep_path)
            payload = json.loads(Path(str(out.sweep_path)).read_text())
            self.assertTrue(payload["partial"])
            self.assertTrue(
                any("no decision on partial data" in r for r in out.decision_reasons)
            )

    def test_plain_interrupt_has_no_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)

            def boom(self, *args, **kwargs):  # noqa: ANN001, ANN202
                raise KeyboardInterrupt

            orig = BenchmarkExecutor.sweep
            BenchmarkExecutor.sweep = boom  # type: ignore[method-assign]
            try:
                out = accelerate_target(root, seeds=[101, 103, 107], apply=False)
            finally:
                BenchmarkExecutor.sweep = orig
            self.assertTrue(out.interrupted)
            self.assertIsNone(out.sweep_path)


@pytest.mark.slow
@pytest.mark.skipif(
    os.name != "posix",
    reason="SIGINT-to-child is posix-only (Windows force-kills: no graceful 130)",
)
class CLIInterruptTests(unittest.TestCase):
    def test_cli_ctrl_c_is_130_with_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fast_project(root, variants=4, sleep=0.05)
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "mycelium_accel",
                    "accelerate",
                    "--target",
                    str(root),
                    "--no-apply",
                    "--seeds",
                    "101,103,107,109,113",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=Path(__file__).resolve().parent.parent,
            )
            # C2: 5 seeds + SIGINT aos 2.0 s (era 7 seeds + 3.0 s), mesmas
            # asserções. Piso de sleep do sweep = 5 cand × 5 seeds × 2 reps ×
            # 0.05 s = 2.5 s > 2.0 s: o SIGINT cai no meio do sweep em
            # qualquer máquina (spawn rápido não encurta sleep); baseline
            # (~0.5 s + spawn) já terminou mesmo a 2× slowdown. ~1 s mais
            # rápido, robustez igual ou melhor nas duas direções.
            time.sleep(2.0)
            proc.send_signal(signal.SIGINT)
            out, _ = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 130, out[-2000:])
            self.assertIn("interrupted", out)
            self.assertNotIn("Traceback", out)
            payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
            self.assertTrue(payload["interrupted"])
            self.assertIsNone(payload["best_candidate"])
            sweep = json.loads(Path(payload["sweep_path"]).read_text())
            self.assertTrue(sweep["partial"])
            self.assertGreaterEqual(len(sweep["summaries"]), 1)


@pytest.mark.slow
@pytest.mark.skipif(
    os.name != "posix",
    reason="SIGINT-to-child is posix-only (Windows force-kills: no graceful 130)",
)
class RunnerTimeoutPortableTests(unittest.TestCase):
    """Timeout kill without pgrep/signals: runs everywhere incl. Windows/macOS."""

    def test_timeout_returns_promptly_failed(self) -> None:
        python = "python3" if shutil.which("python3") else "python"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            runner = load_target(root, None).runner
            started = time.perf_counter()
            # C2: timeout 1.0 (era 2.0) — mesma propriedade (kill no timeout,
            # não na conclusão), ~1 s mais rápido; bound elapsed<25 intacto.
            result = runner.run(
                f'{python} -c "import time; time.sleep(30)"',
                timeout=1.0,
            )
            elapsed = time.perf_counter() - started
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, -signal.SIGKILL)
        self.assertLess(elapsed, 25.0)


@pytest.mark.slow  # Q2 re-tier: timing-based process tests live in slow
@pytest.mark.skipif(os.name != "posix", reason="process groups are posix-only")
@pytest.mark.skipif(
    shutil.which("pgrep") is None, reason="pgrep missing (no procps on macOS runners)"
)
class OrphanKillTests(unittest.TestCase):
    def _runner(self, root: Path):  # noqa: ANN202
        _make_python_project(root)
        return load_target(root, None).runner

    def _pgrep(self, marker: str) -> bool:
        proc = subprocess.run(["pgrep", "-f", marker], capture_output=True, timeout=10)
        return proc.returncode == 0

    def test_timeout_kills_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = self._runner(Path(temp))
            result = runner.run("sh -c 'sleep 61'", timeout=1.0)
            self.assertEqual(result.returncode, -signal.SIGKILL)
            time.sleep(0.5)
            self.assertFalse(self._pgrep("sleep 61"), "orphan sleep survived timeout")

    def test_ctrl_c_kills_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = self._runner(Path(temp))
            timer = threading.Timer(1.0, lambda: os.kill(os.getpid(), signal.SIGINT))
            timer.start()
            try:
                with self.assertRaises(KeyboardInterrupt):
                    runner.run("sh -c 'sleep 62'", timeout=60.0)
            finally:
                timer.cancel()
            time.sleep(0.5)
            self.assertFalse(self._pgrep("sleep 62"), "orphan sleep survived Ctrl-C")


if __name__ == "__main__":
    unittest.main()
