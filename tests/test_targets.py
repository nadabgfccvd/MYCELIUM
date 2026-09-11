from __future__ import annotations

import json
import tempfile
import unittest.mock
import pytest
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import accelerate_target
from mycelium_accel.bench import parse_metrics
from mycelium_accel.targets import TargetSafetyError, Variant, detect_kind, load_target
from mycelium_accel.targets.base import TargetManifest


def _make_python_project(root: Path) -> None:
    benchmark = root / "bench.py"
    benchmark.write_text(
        "import os, json, time\n"
        "mode = os.environ.get('BENCH_MODE', 'baseline')\n"
        "work = 30000 if mode == 'slow' else (1200 if mode == 'fast' else 6000)\n"
        "total = 0\n"
        "started = time.perf_counter()\n"
        "for i in range(work):\n"
        "    total += (i * i) % 7\n"
        "elapsed = time.perf_counter() - started\n"
        "print(json.dumps({'seconds': elapsed, 'total': total}))\n",
        encoding="utf-8",
    )
    manifest = {
        "name": "demo-python",
        "kind": "python",
        "benchmark_command": "python3 bench.py",
        "metrics_parser": "json_stdout",
        "metric_name": "seconds",
        "lower_is_better": True,
        "warmup": 0,  # W1.2: mechanics fixture, 5x gap needs no warmup
        "repeats": 2,
        "timeout_seconds": 30,
        "variants": [
            {"name": "fast-mode", "mode": "env", "env": {"BENCH_MODE": "fast"}},
            {"name": "slow-mode", "mode": "env", "env": {"BENCH_MODE": "slow"}},
        ],
    }
    (root / "mycelium.target.json").write_text(json.dumps(manifest), encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def test_manifest_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            manifest = TargetManifest.load(root)
            self.assertEqual(manifest.kind, "python")
            self.assertEqual(len(manifest.variants), 2)
            payload = manifest.to_dict()
            reloaded = TargetManifest.from_dict(payload)
            self.assertEqual(reloaded.metric_name, "seconds")

    def test_manifest_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            TargetManifest.from_dict({"kind": "python", "bogus": True})

    def test_detect_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(detect_kind(root), "shell")
            (root / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
            self.assertEqual(detect_kind(root), "cargo")


class RunnerSafetyTests(unittest.TestCase):
    def test_allowlist_blocks_unknown_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            from mycelium_accel.targets.base import CommandRunner

            runner = CommandRunner(root, allowlist=["python3"])
            with self.assertRaises(TargetSafetyError):
                runner.run("rm -rf /")


class ExecutorTests(unittest.TestCase):
    def test_json_stdout_parser(self) -> None:
        from mycelium_accel.targets.base import TargetRunResult

        result = TargetRunResult(command=["x"], returncode=0, seconds=1.0, stdout_tail='{"seconds": 0.42}\n', stderr_tail="")
        metrics = parse_metrics(result, "json_stdout", "seconds")
        self.assertAlmostEqual(metrics["seconds"], 0.42)

    def test_regex_parser(self) -> None:
        from mycelium_accel.targets.base import TargetRunResult

        result = TargetRunResult(command=["x"], returncode=0, seconds=1.0, stdout_tail='time: 3.14s\n', stderr_tail="")
        metrics = parse_metrics(result, r"regex:time:\s+([0-9.]+)s", "seconds")
        self.assertAlmostEqual(metrics["seconds"], 3.14)

    def test_file_variant_patch_snapshot_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            target = load_target(root)
            replacement = root / "bench_fast.py"
            replacement.write_text("import json\nprint(json.dumps({'seconds': 0.001}))\n", encoding="utf-8")
            variant = Variant.from_dict({
                "name": "patch-bench",
                "mode": "patch",
                "files": {"bench.py": "bench_fast.py"},
            })
            original = (root / "bench.py").read_text(encoding="utf-8")
            snapshot = target.apply_variant(variant)
            try:
                self.assertIn("0.001", (root / "bench.py").read_text(encoding="utf-8"))
            finally:
                target.revert_variant(snapshot, variant)
            self.assertEqual((root / "bench.py").read_text(encoding="utf-8"), original)


class EndToEndTests(unittest.TestCase):
    @pytest.mark.slow
    def test_accelerate_target_applies_record(self) -> None:
        # W1.2 fusion: also absorbs test_sweep_and_decision's assertions
        # (3 summaries, best fast-mode, accepted reason) via the sweep artifact.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            outcome = accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131], apply=True)
            self.assertEqual(outcome.best_candidate, "fast-mode")
            self.assertTrue(any("accepted" in r for r in outcome.decision_reasons))
            sweep = json.loads(Path(outcome.sweep_path).read_text(encoding="utf-8"))
            self.assertEqual(len(sweep["summaries"]), 3)
            self.assertTrue(outcome.applied)
            record = root / ".mycelium_targets" / "active_variant.json"
            self.assertTrue(record.exists())
            payload = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(payload["variant"]["name"], "fast-mode")
            self.assertTrue((root / ".mycelium_benchmarks").exists())

    @pytest.mark.slow
    def test_no_apply_means_measure_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_python_project(root)
            outcome = accelerate_target(root, seeds=[101, 103, 107, 109, 113, 127, 131], apply=False)
            self.assertFalse(outcome.applied)


if __name__ == "__main__":
    unittest.main()


class DefaultManifestTests(unittest.TestCase):
    """Ciclo 2 (Q): node/cargo/cmake default_manifest — 31-47% covered before.

    Each branch is pinned: missing toolchain, missing markers, malformed
    manifests, command priority. A regression in auto-detection now fails
    here instead of surprising a fresh `accelerate init` user.
    """

    def _root(self, tmp: str, name: str = "proj") -> Path:
        root = Path(tmp) / name
        root.mkdir(parents=True)
        return root

    # -- Node ------------------------------------------------------------

    def test_node_bare_manifest_without_package_json(self) -> None:
        from mycelium_accel.targets.node_target import NodeTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value="/fake/npm"
        ):
            manifest = NodeTarget.default_manifest(self._root(tmp))
        self.assertEqual(manifest.kind, "node")
        self.assertEqual(manifest.name, "proj")
        self.assertIsNone(manifest.build_command)
        self.assertIsNone(manifest.test_command)
        self.assertIsNone(manifest.benchmark_command)

    def test_node_manifest_reads_scripts(self) -> None:
        from mycelium_accel.targets.node_target import NodeTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value="/fake/npm"
        ):
            root = self._root(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "tsc", "test": "jest", "bench": "node bench.js"}}),
                encoding="utf-8",
            )
            manifest = NodeTarget.default_manifest(root)
        self.assertEqual(manifest.build_command, "npm run build")
        self.assertEqual(manifest.test_command, "npm test --silent")
        self.assertEqual(manifest.benchmark_command, "npm run bench")

    def test_node_bench_alias_and_missing_npm(self) -> None:
        from mycelium_accel.targets.node_target import NodeTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value="/fake/npm"
        ):
            root = self._root(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"benchmark": "node bench.js"}}), encoding="utf-8"
            )
            manifest = NodeTarget.default_manifest(root)
        self.assertEqual(manifest.benchmark_command, "npm run benchmark")

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value=None
        ):
            root = self._root(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "tsc"}}), encoding="utf-8"
            )
            manifest = NodeTarget.default_manifest(root)
        self.assertIsNone(manifest.build_command)

    def test_node_malformed_package_json_is_bare(self) -> None:
        from mycelium_accel.targets.node_target import NodeTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value="/fake/npm"
        ):
            root = self._root(tmp)
            (root / "package.json").write_text("{not json", encoding="utf-8")
            manifest = NodeTarget.default_manifest(root)
        self.assertIsNone(manifest.build_command)
        self.assertIsNone(manifest.test_command)

    # -- Cargo -----------------------------------------------------------

    def test_cargo_bare_manifest_without_cargo(self) -> None:
        from mycelium_accel.targets.cargo_target import CargoTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value=None
        ):
            manifest = CargoTarget.default_manifest(self._root(tmp))
        self.assertEqual(manifest.kind, "cargo")
        self.assertIsNone(manifest.build_command)
        self.assertIsNone(manifest.test_command)
        self.assertIsNone(manifest.benchmark_command)

    def test_cargo_manifest_with_and_without_benches(self) -> None:
        from mycelium_accel.targets.cargo_target import CargoTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value="/fake/cargo"
        ):
            root = self._root(tmp)
            manifest = CargoTarget.default_manifest(root)
            self.assertEqual(manifest.build_command, "cargo build --release")
            self.assertEqual(manifest.test_command, "cargo test --release")
            self.assertIsNone(manifest.benchmark_command)
            self.assertIsNone(manifest.clean_command)
            self.assertEqual(manifest.timeout_seconds, 600.0)

            (root / "benches").mkdir()
            manifest = CargoTarget.default_manifest(root)
            self.assertEqual(manifest.benchmark_command, "cargo bench")

    # -- CMake -----------------------------------------------------------

    def test_cmake_bare_manifest_without_cmake(self) -> None:
        from mycelium_accel.targets.cmake_target import CmakeTarget

        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
            "shutil.which", return_value=None
        ):
            manifest = CmakeTarget.default_manifest(self._root(tmp))
        self.assertEqual(manifest.kind, "cmake")
        self.assertIsNone(manifest.build_command)

    def test_cmake_manifest_commands(self) -> None:
        from mycelium_accel.targets.cmake_target import CmakeTarget

        def which_cmake_only(name: str) -> str | None:
            return "/fake/cmake" if name == "cmake" else None

        def which_both(name: str) -> str | None:
            return f"/fake/{name}" if name in ("cmake", "ctest") else None

        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            with unittest.mock.patch("shutil.which", side_effect=which_cmake_only):
                manifest = CmakeTarget.default_manifest(root)
            self.assertEqual(
                manifest.build_command,
                "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release",
            )
            self.assertIsNone(manifest.test_command)  # ctest absent
            self.assertEqual(manifest.timeout_seconds, 600.0)

            with unittest.mock.patch("shutil.which", side_effect=which_both):
                manifest = CmakeTarget.default_manifest(root)
            self.assertEqual(manifest.test_command, "ctest --test-dir build --output-on-failure")
