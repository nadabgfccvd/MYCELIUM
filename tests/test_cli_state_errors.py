"""Ciclo 4 (R) — corrupt state/checkpoint files degrade to friendly errors.

Before: a truncated state.json surfaced as a raw json.JSONDecodeError
traceback from `report`/`run`/`rollback`. Contract now: StateCorruptError
carrying the file path, and the CLI printing one actionable line (exit 1,
no traceback) with the rollback/re-init remedies. Library users get a typed
exception to catch.
"""
from __future__ import annotations

import json
import pickle
import sys
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.state import StateCorruptError, load_state

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_runner import cli  # type: ignore[import-not-found]


def _write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


class CorruptStateLoadTests(unittest.TestCase):
    def test_truncated_json_raises_friendly_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp) / "state.json", '{"round_index": 3, "trunc')
            with self.assertRaises(StateCorruptError) as ctx:
                load_state(Path(tmp))
            self.assertIn("state.json", str(ctx.exception))
            self.assertIn("corrupt or truncated", str(ctx.exception))

    def test_empty_json_file_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp) / "state.json", "")
            with self.assertRaises(StateCorruptError):
                load_state(Path(tmp))

    def test_valid_json_wrong_shape_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp) / "state.json", json.dumps({"nonsense": True}))
            with self.assertRaises(StateCorruptError) as ctx:
                load_state(Path(tmp))
            self.assertIn("invalid content", str(ctx.exception))

    def test_truncated_pickle_raises_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.pkl"
            path.write_bytes(pickle.dumps({"round_index": 1})[:5])
            with self.assertRaises(StateCorruptError) as ctx:
                load_state(Path(tmp), backend="pickle")
            self.assertIn("state.pkl", str(ctx.exception))

    def test_missing_dir_still_raises_filenotfound_not_corrupt(self) -> None:
        # Absent state is NOT corruption — the engine inits fresh; keep that path.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "does-not-exist"
            with self.assertRaises(FileNotFoundError):
                load_state(target)


class CliFriendlyErrorsTests(unittest.TestCase):
    def _cli(self, *args: str):
        return cli(*args)

    def test_report_on_corrupt_state_is_one_line_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp) / "state.json", '{"round_index": 3, "trunc')
            result = self._cli("report", "--state-dir", tmp)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("corrupt or truncated", result.stderr)
        self.assertIn("rollback", result.stderr)  # remedy suggested
        self.assertIn("init", result.stderr)

    def test_run_on_corrupt_state_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp) / "state.json", "")
            result = self._cli("run", "--state-dir", tmp, "--seed", "101", "--rounds", "1")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("mycelium-accel:", result.stderr)

    def test_rollback_on_corrupt_checkpoint_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # init a valid state so engine setup succeeds, then poison the checkpoint
            result = self._cli(
                "init", "--state-dir", tmp, "--seed", "101",
                "--persistence-backend", "json", "--checkpoint-every", "2",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self._cli(
                "run", "--state-dir", tmp, "--seed", "101", "--rounds", "3",
                "--persistence-backend", "json", "--checkpoint-every", "2",
            )
            checkpoints = sorted((Path(tmp) / "checkpoints").glob("round-*.json"))
            self.assertTrue(checkpoints, "expected at least one checkpoint")
            _write(checkpoints[-1], "{corrupt")
            result = self._cli(
                "rollback", "--state-dir", tmp, "--round", "2",
                "--persistence-backend", "json",
            )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("corrupt or truncated", result.stderr)

    def test_report_on_uninitialized_dir_is_friendly(self) -> None:
        # S2 Ciclo 10: report on a dir with no state.json was a raw
        # FileNotFoundError traceback; expect one actionable line, exit 1.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "never-initialized"
            result = self._cli("report", "--state-dir", str(target))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("no state found", result.stderr)
        self.assertIn("init", result.stderr)

    def test_growth_regime_on_uninitialized_dir_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nope"
            result = self._cli("growth-regime", "--state-dir", str(target))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("no state found", result.stderr)

    def test_rollback_round_on_uninitialized_dir_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nope"
            result = self._cli(
                "rollback", "--state-dir", str(target), "--round", "1")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("Nothing to roll back", result.stderr)

    def test_corrupt_manifest_is_not_misreported_as_state(self) -> None:
        # Regression guard: manifest errors keep their own message; the new
        # StateCorruptError handler must not swallow unrelated JSON failures.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "proj"
            target.mkdir()
            (target / "mycelium.target.json").write_text("{not json", encoding="utf-8")
            (target / "bench.py").write_text("print(1)\n", encoding="utf-8")
            result = self._cli("accelerate", "--target", str(target), "--no-apply", "--seeds", "101")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("state file", result.stderr.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
