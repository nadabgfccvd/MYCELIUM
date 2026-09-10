"""Q3.3 — rollback reverts the WINNER (binding tripwire).

Regression: a rename once left the ``except`` path reverting the loop variable
``variant`` (last in manifest order) instead of ``winner`` — type-correct,
behavior-wrong, invisible to mypy. This test pins the binding directly: the
winner is FIRST in the manifest, so any loop-variable leak reverts the loser.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
from unittest import mock

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402

from mycelium_accel.accelerate_generic import accelerate_target  # noqa: E402
from mycelium_accel.targets.base import ProjectTarget, TargetRunResult  # noqa: E402

_ORIG_REVERT = ProjectTarget.revert_variant  # unbound; keeps sweep isolation under mock


def _ok() -> TargetRunResult:
    return TargetRunResult(command=["t"], returncode=0, seconds=0.01,
                           stdout_tail="", stderr_tail="")


def _fail() -> TargetRunResult:
    return TargetRunResult(command=["t"], returncode=1, seconds=0.01,
                           stdout_tail="", stderr_tail="boom")


def _project_with_patch_winner(root: Path) -> None:
    _make_python_project(root)
    (root / "bench_fast.py").write_text(
        # constant 1us: always beats the ~ms demo baseline (unanimous win)
        "import json\nprint(json.dumps({'seconds': 0.000001, 'total': 1}))\n",
        encoding="utf-8",
    )
    manifest = json.loads((root / "mycelium.target.json").read_text())
    manifest["variants"] = [
        {"name": "fast-patch", "mode": "patch",  # WINNER, deliberately FIRST
         "files": {"bench.py": "bench_fast.py"}},
        {"name": "slow-mode", "mode": "env", "env": {"BENCH_MODE": "slow"}},
    ]
    (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.slow  # Q3 re-tier: real 7-seed sweeps under mock
class RollbackBindingTests(unittest.TestCase):
    def test_retest_failure_reverts_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _project_with_patch_winner(root)
            with mock.patch.object(ProjectTarget, "test", side_effect=[_ok(), _fail()]), \
                 mock.patch.object(ProjectTarget, "revert_variant", autospec=True) as reverted:
                reverted.side_effect = _ORIG_REVERT  # record AND restore
                out = accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131],
                                        apply=True)
            self.assertEqual(out.best_candidate, "fast-patch")
            self.assertFalse(out.applied)
            self.assertTrue(any("rolled back" in r for r in out.decision_reasons))
            # last call is the rollback (earlier calls are per-run sweep isolation)
            self.assertEqual(reverted.call_args[0][2].name, "fast-patch")

    def test_retest_exception_reverts_winner_and_reraises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _project_with_patch_winner(root)
            with mock.patch.object(ProjectTarget, "test", side_effect=[_ok(), RuntimeError("x")]), \
                 mock.patch.object(ProjectTarget, "revert_variant", autospec=True) as reverted:
                reverted.side_effect = _ORIG_REVERT  # record AND restore
                with self.assertRaises(RuntimeError):
                    accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131], apply=True)
            # last call is the rollback (earlier calls are per-run sweep isolation)
            self.assertEqual(reverted.call_args[0][2].name, "fast-patch")


if __name__ == "__main__":
    unittest.main()
