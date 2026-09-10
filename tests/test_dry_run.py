"""C5 — accelerate --dry-run validates manifest+build+tests, measures nothing."""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import unittest
from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402

from mycelium_accel.accelerate_generic import accelerate_target  # noqa: E402

SEEDS = [101, 103, 107]
EXIT1 = "python3 -c \"import sys; sys.exit(1)\""


def _with_commands(root: Path, **commands: str) -> None:
    manifest = json.loads((root / "mycelium.target.json").read_text())
    manifest.update(commands)
    (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")


class DryRunTests(unittest.TestCase):
    def test_healthy_project_validates_without_measuring(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            out = accelerate_target(root, seeds=SEEDS, dry_run=True)
            self.assertIsNone(out.best_candidate)
            self.assertFalse(out.applied)
            self.assertIsNone(out.sweep_path)
            self.assertEqual(out.comparisons, [])
            self.assertEqual(len(out.decision_reasons), 1)
            reason = out.decision_reasons[0]
            self.assertIn("dry run", reason)
            self.assertIn("manifest valid", reason)
            self.assertIn("metric 'seconds'", reason)
            self.assertIn("no measurements taken", reason)
            self.assertFalse((root / ".mycelium_benchmarks").exists())

    def test_failing_tests_are_reported_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            _with_commands(root, test_command=EXIT1)
            out = accelerate_target(root, seeds=SEEDS, dry_run=True)
            self.assertIn("FAIL", out.decision_reasons[0])
            self.assertFalse(out.applied)

    def test_failing_build_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            _with_commands(root, build_command=EXIT1)
            with self.assertRaises(RuntimeError):
                accelerate_target(root, seeds=SEEDS, dry_run=True)

    def test_invalid_manifest_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            manifest = json.loads((root / "mycelium.target.json").read_text())
            manifest["bogus_key"] = True
            (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                accelerate_target(root, seeds=SEEDS, dry_run=True)

    def test_missing_target_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                accelerate_target(Path(temp) / "nope", seeds=SEEDS, dry_run=True)

    def test_cli_dry_run_is_json_and_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _make_python_project(Path(temp))
            proc = cli("accelerate", "--target", temp, "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIsNone(payload["best_candidate"])
            self.assertIsNone(payload["sweep_path"])
            self.assertFalse(payload["applied"])


if __name__ == "__main__":
    unittest.main()
