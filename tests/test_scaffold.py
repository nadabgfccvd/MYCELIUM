"""H1.1: init wizard/yes + doctor --target/--fix."""
from __future__ import annotations

import json
from cli_runner import cli
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.scaffold import run_wizard
from mycelium_accel.targets.base import TargetManifest

ROOT = Path(__file__).resolve().parents[1]


def scripted(answers: list[str]):
    it = iter(answers)
    return lambda prompt, default: next(it, default)


class ScaffoldTests(unittest.TestCase):
    def test_wizard_refines_detection(self) -> None:
        detected = TargetManifest(benchmark_command="python bench.py")
        out = run_wizard(detected, scripted([
            "python -O bench.py",  # benchmark
            "ms",                  # metric
            "y",                   # lower is better
            "3",                   # repeats
            "fast",                # variant name
            "MODE=fast",           # variant env
        ]))
        self.assertEqual(out.benchmark_command, "python -O bench.py")
        self.assertEqual(out.metric_name, "ms")
        self.assertTrue(out.lower_is_better)
        self.assertEqual(out.repeats, 3)
        self.assertEqual(out.variants[0].name, "fast")
        self.assertEqual(out.variants[0].env, {"MODE": "fast"})
        self.assertEqual(out.validate(), [])

    def test_wizard_bad_repeats_is_friendly(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            run_wizard(TargetManifest(), scripted(["", "", "", "abc"]))
        self.assertIn("repeats", str(ctx.exception))

    def test_init_yes_writes_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "benchmark.py").write_text("print(1)\n", encoding="utf-8")
            proc = cli("accelerate", "init", "--target", tmp, "--yes")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Next steps", proc.stdout)
            manifest = TargetManifest.load(Path(tmp) / "mycelium.target.json")
            self.assertEqual(manifest.validate(), [])

    def test_init_wizard_piped_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "benchmark.py").write_text("print(1)\n", encoding="utf-8")
            proc = cli("accelerate", "init", "--target", tmp, "--wizard",
                         input="\n\n\n2\n\n")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            raw = json.loads(Path(tmp, "mycelium.target.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["repeats"], 2)

    def test_doctor_target_and_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "mycelium.target.json").write_text(
                json.dumps({"benchmark_command": "python bench.py",
                            "executable_allowlist": ["python", "python", "cc"]}),
                encoding="utf-8")
            check = cli("doctor", "--target", tmp, "--json")
            self.assertEqual(check.returncode, 0)  # WARN (missing version), not FAIL
            self.assertIn("manifest_version", check.stdout)
            fix = cli("doctor", "--target", tmp, "--fix")
            self.assertEqual(fix.returncode, 0, fix.stderr)
            raw = json.loads(Path(tmp, "mycelium.target.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["manifest_version"], "1.0")
            self.assertEqual(raw["executable_allowlist"], ["cc", "python"])

    def test_doctor_target_missing_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = cli("doctor", "--target", tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("accelerate init", proc.stdout)


if __name__ == "__main__":
    unittest.main()
