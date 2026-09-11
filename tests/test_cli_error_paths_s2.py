"""S2 Ciclo 10 — fresh-eyes CLI bug hunt: no raw tracebacks on bad inputs.

Bug-hunt contract: every user-facing command must degrade to one actionable
stderr line plus a non-zero exit code (or to safe default output), never a raw
Python traceback. The issues below were found by fuzzing malformed/missing
inputs after the Ciclo-4 state-error work had shipped; they complement
``test_cli_state_errors`` (corrupt state/checkpoints) without replacing it.

Regression guards added here:

1. ``accelerate --target <missing dir/module>`` fell through to the legacy
   module loader and leaked ``RuntimeError: Could not load module from ...``.
2. A syntactically invalid target module leaked ``SyntaxError``; a valid
   module without ``BENCHMARK_SPEC`` leaked ``AttributeError``.
3. ``growth-regime`` with a corrupt/non-object derived sidecar
   (``.mycelium_qd/qd_experiment.json`` etc.) leaked ``JSONDecodeError``;
   sidecars are optional, so it now warns and degrades to zeros (rc 0).
4. ``rollback --round N`` to a round with no checkpoint is friendly.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_runner import cli  # type: ignore[import-not-found]


class _Chdir:
    def __init__(self, dest: Path) -> None:
        self.dest = dest
        self._prev = ""

    def __enter__(self) -> _Chdir:
        self._prev = os.getcwd()
        os.chdir(self.dest)
        return self

    def __exit__(self, *exc: object) -> None:
        os.chdir(self._prev)


class AccelerateBadTargetTests(unittest.TestCase):
    def test_missing_target_is_one_line_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-project"
            result = cli("accelerate", "--target", str(missing),
                         "--no-apply", "--seeds", "101")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("target not found", result.stderr)

    def test_syntax_error_target_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.py"
            bad.write_text("def not python @#$\n", encoding="utf-8")
            result = cli("accelerate", "--target", str(bad), "--seeds", "101")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("accelerate failed", result.stderr)

    def test_module_without_benchmark_spec_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain.py"
            plain.write_text("x = 1\n", encoding="utf-8")
            result = cli("accelerate", "--target", str(plain), "--seeds", "101")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("BENCHMARK_SPEC", result.stderr)


class GrowthRegimeSidecarTests(unittest.TestCase):
    def _init_state(self, state_dir: Path) -> None:
        result = cli("init", "--state-dir", str(state_dir), "--seed", "101")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = cli("run", "--state-dir", str(state_dir), "--seed", "101",
                  "--rounds", "2")
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_corrupt_sidecar_warns_not_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "st"
            self._init_state(state_dir)
            cwd = Path(tmp) / "cwd"
            (cwd / ".mycelium_qd").mkdir(parents=True)
            (cwd / ".mycelium_qd" / "qd_experiment.json").write_text(
                "{broken", encoding="utf-8")
            with _Chdir(cwd):
                result = cli("growth-regime", "--state-dir", str(state_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("unreadable", result.stderr)

    def test_non_object_sidecar_warns_not_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "st"
            self._init_state(state_dir)
            cwd = Path(tmp) / "cwd"
            (cwd / ".mycelium_transfer").mkdir(parents=True)
            (cwd / ".mycelium_transfer" / "transfer_graph.json").write_text(
                "[]", encoding="utf-8")
            with _Chdir(cwd):
                result = cli("growth-regime", "--state-dir", str(state_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("expected a JSON object", result.stderr)


class StateDirIsFileTests(unittest.TestCase):
    def test_engine_commands_reject_file_state_dir(self) -> None:
        # A file (not a directory) passed via --state-dir leaked a raw
        # NotADirectoryError from AuditLog's checkpoint mkdir.
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "f"
            bad.write_text("data", encoding="utf-8")
            for argv in (
                ("report",),
                ("run", "--rounds", "0"),
                ("rollback", "--round", "1"),
                ("growth-regime",),
                ("self-improve", "--cycles", "0"),
            ):
                with self.subTest(argv=argv):
                    result = cli(*argv, "--state-dir", str(bad))
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertIn("must be a directory", result.stderr)


class RollbackMissingRoundTests(unittest.TestCase):
    def test_rollback_beyond_available_rounds_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "st"
            init = cli("init", "--state-dir", str(state_dir), "--seed", "101",
                       "--persistence-backend", "json", "--checkpoint-every", "2")
            self.assertEqual(init.returncode, 0, init.stderr)
            run = cli("run", "--state-dir", str(state_dir), "--seed", "101",
                      "--rounds", "2", "--persistence-backend", "json",
                      "--checkpoint-every", "2")
            self.assertEqual(run.returncode, 0, run.stderr)
            result = cli("rollback", "--state-dir", str(state_dir),
                         "--round", "99", "--persistence-backend", "json")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("Nothing to roll back", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
