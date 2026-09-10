"""C6 — Go target kind + wider detection + friendlier validate() errors."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest
from cli_runner import cli

from mycelium_accel.targets import (
    GoTarget,
    detect_kind,
    load_target,
)
from mycelium_accel.targets.base import (
    CommandRunner,
    DEFAULT_EXECUTABLE_ALLOWLIST,
    TargetManifest,
)

ROOT = Path(__file__).resolve().parent.parent


class DetectKindMatrixTests(unittest.TestCase):
    def _dir_with(self, *files: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for name in files:
            (tmp / name).write_text("x\n", encoding="utf-8")
        return tmp

    def test_empty_is_shell(self) -> None:
        self.assertEqual(detect_kind(self._dir_with()), "shell")

    def test_go_mod_is_go(self) -> None:
        self.assertEqual(detect_kind(self._dir_with("go.mod")), "go")

    def test_python_signals(self) -> None:
        for name in ("pyproject.toml", "setup.py", "benchmark.py",
                     "requirements.txt", "uv.lock"):
            with self.subTest(file=name):
                self.assertEqual(detect_kind(self._dir_with(name)), "python")

    def test_node_signals(self) -> None:
        for name in ("package.json", "deno.json", "deno.jsonc"):
            with self.subTest(file=name):
                self.assertEqual(detect_kind(self._dir_with(name)), "node")

    def test_existing_precedence_preserved(self) -> None:
        # Polyglot dirs keep the old winners (python first, then cargo…).
        self.assertEqual(
            detect_kind(self._dir_with("pyproject.toml", "go.mod")), "python")
        self.assertEqual(
            detect_kind(self._dir_with("Cargo.toml", "go.mod")), "cargo")
        self.assertEqual(
            detect_kind(self._dir_with("package.json", "go.mod")), "node")
        self.assertEqual(
            detect_kind(self._dir_with("go.mod", "Makefile")), "go")


class GoManifestTests(unittest.TestCase):
    def test_default_manifest_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "go.mod").write_text("module x\n", encoding="utf-8")
            manifest = GoTarget.default_manifest(root)
            self.assertEqual(manifest.kind, "go")
            self.assertEqual(manifest.metric_name, "ns_per_op")
            self.assertTrue(manifest.metrics_parser.startswith("regex:"))
            self.assertIn("ns_per_op", manifest.metrics_parser)
            self.assertTrue(manifest.lower_is_better)
            if shutil.which("go") is None:
                self.assertIsNone(manifest.build_command)
                self.assertIsNone(manifest.benchmark_command)
            else:
                self.assertIn("go build", manifest.build_command or "")

    def test_bench_test_enables_benchmark_command(self) -> None:
        if shutil.which("go") is None:
            self.skipTest("needs go toolchain")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "go.mod").write_text("module x\n", encoding="utf-8")
            (root / "x_test.go").write_text("package x\n", encoding="utf-8")
            manifest = GoTarget.default_manifest(root)
            assert manifest.benchmark_command is not None
            self.assertIn("go test", manifest.benchmark_command)
            self.assertIn("-bench", manifest.benchmark_command)

    def test_go_in_allowlist(self) -> None:
        self.assertIn("go", DEFAULT_EXECUTABLE_ALLOWLIST)

    def test_go_cache_envs_pass_through_build_env(self) -> None:
        # Regression (windows-latest CI, PR #3): GOCACHE was missing from the
        # harness whitelist, so `go build` failed on runners where Go's
        # default cache location is undefined (%LocalAppData% not set).
        with tempfile.TemporaryDirectory() as temp:
            saved = {k: os.environ.get(k) for k in ("GOCACHE", "GOMODCACHE")}
            os.environ["GOCACHE"] = temp
            os.environ["GOMODCACHE"] = temp
            try:
                env = CommandRunner(Path(temp)).build_env()
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            self.assertEqual(env.get("GOCACHE"), temp)
            self.assertEqual(env.get("GOMODCACHE"), temp)

    def test_load_target_maps_go_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "go.mod").write_text("module x\n", encoding="utf-8")
            target = load_target(root, None)
            self.assertIsInstance(target, GoTarget)

    def test_init_scaffolds_go(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "go.mod").write_text("module x\n", encoding="utf-8")
            proc = cli("accelerate", "init", "--target", temp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads(
                Path(temp, "mycelium.target.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "go")

    def test_example_manifest_validates(self) -> None:
        manifest = TargetManifest.load(ROOT / "examples" / "go-bench")
        self.assertEqual(manifest.validate(), [])
        self.assertEqual(manifest.kind, "go")
        self.assertEqual(len(manifest.variants), 2)


class ValidateHintsTests(unittest.TestCase):
    def test_allowlist_hint_names_the_fix(self) -> None:
        manifest = TargetManifest(name="x", kind="shell",
                                  benchmark_command="rm -rf /tmp/x")
        errors = manifest.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("executable_allowlist", errors[0])
        self.assertIn("mycelium.target.json", errors[0])

    def test_repeats_warmup_echo_values(self) -> None:
        manifest = TargetManifest(name="x", kind="shell", repeats=0, warmup=-2)
        errors = manifest.validate()
        self.assertIn("repeats must be >= 1 (got 0)", errors)
        self.assertIn("warmup must be >= 0 (got -2)", errors)


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("go") is None, reason="needs go toolchain")
class GoLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        # Pin an explicit GOCACHE: runners like windows-latest may lack Go's
        # default cache location (%LocalAppData% undefined), which made
        # `go build` fail with "build cache is required". Deterministic fix.
        self._gocache = tempfile.mkdtemp(prefix="mycelium-gocache-")
        self._saved = os.environ.get("GOCACHE")
        os.environ["GOCACHE"] = self._gocache

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("GOCACHE", None)
        else:
            os.environ["GOCACHE"] = self._saved
        shutil.rmtree(self._gocache, True)

    def test_example_accelerates(self) -> None:
        from mycelium_accel.accelerate_generic import accelerate_target

        out = accelerate_target(ROOT / "examples" / "go-bench",
                                seeds=[101, 103, 107], apply=False)
        self.assertIsNotNone(out.sweep_path)
        sweep = json.loads(Path(str(out.sweep_path)).read_text(encoding="utf-8"))
        self.assertEqual(sweep["metric"], "ns_per_op")
        self.assertEqual(len(sweep["summaries"]), 3)  # baseline + 2 variants


if __name__ == "__main__":
    unittest.main()
