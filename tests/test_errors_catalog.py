"""C5 — docs/ERRORS.md is executable: every catalogued error, pinned.

One stderr line + contract exit code, never a traceback, for each row the
catalog promises. If a message changes, the catalog changes in the same diff.
"""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import unittest
from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent))
from test_targets import _make_python_project  # noqa: E402


def _single_line(stderr: str) -> str:
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    assert len(lines) == 1, f"expected 1 stderr line, got {lines!r}"
    return lines[0]


class AccelerateErrorsTests(unittest.TestCase):
    def test_missing_legacy_target_is_one_line(self) -> None:
        proc = cli("accelerate", "--target", "/tmp/mycelium-no-such-target-xyz")
        self.assertEqual(proc.returncode, 1)
        line = _single_line(proc.stderr)
        self.assertTrue(line.startswith("mycelium-accel: accelerate failed: "),
                        line)
        self.assertNotIn("Traceback", proc.stderr)

    def test_invalid_manifest_is_one_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            manifest = json.loads((root / "mycelium.target.json").read_text())
            manifest["bogus_key"] = True
            (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")
            proc = cli("accelerate", "--target", temp)
            self.assertEqual(proc.returncode, 1)
            line = _single_line(proc.stderr)
            self.assertTrue(line.startswith("mycelium-accel: accelerate failed: "),
                            line)
            self.assertNotIn("Traceback", proc.stderr)


class DoctorHistoryInitErrorsTests(unittest.TestCase):
    def test_fix_without_target(self) -> None:
        proc = cli("doctor", "--fix")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stderr.strip(),
                         "mycelium-accel: --fix needs --target DIR")

    def test_history_without_benchmarks_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            proc = cli("history", "--target", temp)
            self.assertEqual(proc.returncode, 1)
            line = _single_line(proc.stderr)
            self.assertTrue(line.startswith("mycelium-accel: no benchmarks dir: "),
                            line)

    def test_accelerate_init_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = str(Path(temp) / "nope")
            proc = cli("accelerate", "init", "--target", missing)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("Target directory not found", _single_line(proc.stderr))

    def test_accelerate_init_existing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _make_python_project(Path(temp))
            proc = cli("accelerate", "init", "--target", temp)
            self.assertEqual(proc.returncode, 1)
            line = _single_line(proc.stderr)
            self.assertIn("exists (use --force to overwrite)", line)

    def test_no_subcommand_is_usage_exit_2(self) -> None:
        proc = cli()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
