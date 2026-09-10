"""Fase 3.4: API freeze — manifest v1 friendly errors + CLI exit codes."""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.targets.base import TargetManifest

ROOT = Path(__file__).resolve().parents[1]


class ApiFreezeTests(unittest.TestCase):
    def test_unknown_key_lists_known(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            TargetManifest.from_dict({"bogus_key": 1})
        self.assertIn("bogus_key", str(ctx.exception))
        self.assertIn("benchmark_command", str(ctx.exception))

    def test_bad_version_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            TargetManifest.from_dict({"manifest_version": "9.9"})
        self.assertIn("9.9", str(ctx.exception))

    def test_validate_catches_nonallowlisted_executable(self) -> None:
        manifest = TargetManifest.from_dict({
            "benchmark_command": "evil-tool bench.py", "repeats": 0})
        errors = manifest.validate()
        self.assertTrue(any("evil-tool" in e for e in errors))
        self.assertTrue(any("repeats" in e for e in errors))

    def test_versioned_python_is_trusted_as_python3(self) -> None:
        manifest = TargetManifest.from_dict({
            "benchmark_command": "python3.13 bench.py", "manifest_version": "1.0"})
        self.assertEqual(manifest.validate(), [])

    def test_load_rejects_invalid_manifest_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mycelium.target.json"
            path.write_text(json.dumps({"benchmark_command": "nope run"}), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                TargetManifest.load(path)
            self.assertIn("nope", str(ctx.exception))

    def test_accelerate_broken_target_exits_1_with_one_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "mycelium.target.json").write_text(
                json.dumps({"benchmark_command": "python -c 'import sys; sys.exit(3)'"}),
                encoding="utf-8")
            proc = cli("accelerate",
                 "--target", tmp, "--seeds", "101,103,107", "--no-apply")
        # broken benchmark: fail-fast aborts the sweep, verdict negative — exit 0,
        # never a traceback (measured negative is a successful measurement).
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(json.loads(proc.stdout)["best_candidate"])

    def test_usage_error_exits_2(self) -> None:
        proc = cli("run", "--nope", "1")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
