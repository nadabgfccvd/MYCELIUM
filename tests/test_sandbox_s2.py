"""Sessão 2, Ciclo 2 — sandbox, snapshot/rollback and manifest validation.

Targets the previously untested safety branches in ``targets/base.py`` and
``targets/__init__.py``: interpreter-name trust mapping, absolute-path policy,
environment scrubbing, the timeout kill path, the full target lifecycle
(prepare/build/test/clean), variant apply failure rollback, and FileSnapshot
restoration of modified/deleted files and directories.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.targets.base import (
    CommandRunner,
    FileSnapshot,
    ProjectTarget,
    TargetManifest,
    TargetSafetyError,
    Variant,
    canonical_executable,
)
from mycelium_accel.targets import detect_kind


def _manifest(**overrides) -> TargetManifest:
    base = {
        "name": "sandbox-test",
        "kind": "shell",
        "warmup": 0,
        "repeats": 1,
        "timeout_seconds": 20,
        "variants": [],
    }
    base.update(overrides)
    return TargetManifest.from_dict(base)


class CanonicalExecutableTests(unittest.TestCase):
    def test_versioned_and_freethreaded_python_maps_to_python3(self) -> None:
        for name in ("python3.9", "python3.13", "python3.14t", "python3.13t"):
            self.assertEqual(canonical_executable(name), "python3", name)

    def test_windows_suffix_and_plain_names(self) -> None:
        self.assertEqual(canonical_executable("python.exe"), "python")
        self.assertEqual(canonical_executable("python3.exe"), "python3")
        self.assertEqual(canonical_executable("gcc"), "gcc")
        self.assertEqual(canonical_executable("cmake"), "cmake")


class ManifestValidationTests(unittest.TestCase):
    def _errors(self, overrides) -> list[str]:
        return _manifest(**overrides).validate()

    def test_whitespace_only_command_is_empty_error(self) -> None:
        errors = self._errors({"benchmark_command": "   "})
        self.assertTrue(any("empty command" in e for e in errors), errors)

    def test_unbalanced_quote_is_parse_error(self) -> None:
        errors = self._errors({"benchmark_command": 'echo "unterminated'})
        self.assertTrue(any("cannot parse" in e for e in errors), errors)

    def test_non_allowlisted_variant_command_reported(self) -> None:
        variant = {"name": "x", "mode": "script", "apply_command": "rm -rf /"}
        errors = self._errors({"variants": [variant]})
        self.assertTrue(any("not allowlisted" in e for e in errors), errors)

    def test_repeats_and_warmup_bounds(self) -> None:
        self.assertTrue(any("repeats" in e for e in self._errors({"repeats": 0})))
        self.assertTrue(any("warmup" in e for e in self._errors({"warmup": -1})))

    def test_variant_construction_rejects_bad_shapes(self) -> None:
        with self.assertRaises(ValueError):
            Variant.from_dict("not-a-dict")
        with self.assertRaises(ValueError):
            Variant.from_dict({"name": "x", "mode": "bogus"})
        with self.assertRaises(ValueError):
            Variant.from_dict({"name": "x", "env": ["not", "a", "dict"]})
        with self.assertRaises(ValueError):
            Variant.from_dict({"name": "x", "files": [1, 2]})


class CommandRunnerPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.runner = CommandRunner(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_empty_argv_rejected(self) -> None:
        with self.assertRaises(TargetSafetyError):
            self.runner._check_command([])

    def test_unknown_executable_rejected(self) -> None:
        with self.assertRaises(TargetSafetyError):
            self.runner._check_command(["rm", "-rf", "/"])

    def test_absolute_path_policy(self) -> None:
        # outside root and outside the trusted toolchain prefixes -> rejected
        with self.assertRaises(TargetSafetyError):
            self.runner._check_command(["python3", "/etc/passwd_leak"])
        # under the sandbox root -> allowed
        self.runner._check_command(["python3", str(self.root / "bench.py")])
        # under a trusted toolchain prefix -> allowed
        self.runner._check_command(["python3", "/usr/lib/python3/something.py"])

    def test_environment_is_scrubbed(self) -> None:
        os.environ["MYCELIUM_TEST_SECRET_XYZ"] = "leak"
        try:
            env = self.runner.build_env()
            self.assertNotIn("MYCELIUM_TEST_SECRET_XYZ", env)
            self.assertIn("PATH", env)  # passthrough allowlist works
            overridden = self.runner.build_env({"MYCELIUM_SEED": "101"})
            self.assertEqual(overridden["MYCELIUM_SEED"], "101")
        finally:
            os.environ.pop("MYCELIUM_TEST_SECRET_XYZ", None)

    def test_seed_env_var_passed_to_process(self) -> None:
        result = self.runner.run(
            'python3 -c "import os;print(os.environ.get(\'MYCELIUM_SEED\'))"',
            seed=101)
        self.assertTrue(result.ok, result.stderr_tail)
        self.assertEqual(result.stdout_tail.strip(), "101")

    def test_timeout_kills_process_group(self) -> None:
        runner = CommandRunner(self.root, timeout_seconds=0.3)
        result = runner.run('python3 -c "import time; time.sleep(5)"')
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, -9)  # SIGKILL from _kill_tree
        self.assertIn("TIMEOUT", result.stderr_tail)


class FileSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_modified_file_and_dir_restored(self) -> None:
        (self.root / "f.txt").write_text("orig")
        d = self.root / "d"
        d.mkdir()
        (d / "a.txt").write_text("a0")
        snap = FileSnapshot(self.root, ["f.txt", "d"])
        snap.__enter__()
        (self.root / "f.txt").write_text("HACKED")
        (d / "a.txt").write_text("aHACK")
        (d / "new.txt").write_text("new")
        snap.__exit__(None, None, None)
        self.assertEqual((self.root / "f.txt").read_text(), "orig")
        self.assertEqual((d / "a.txt").read_text(), "a0")
        self.assertFalse((d / "new.txt").exists())  # whole dir restored

    def test_deleted_file_is_brought_back(self) -> None:
        (self.root / "gone.txt").write_text("keepme")
        snap = FileSnapshot(self.root, ["gone.txt"])
        with snap:
            (self.root / "gone.txt").unlink()
        self.assertEqual((self.root / "gone.txt").read_text(), "keepme")

    def test_restore_without_enter_is_noop(self) -> None:
        snap = FileSnapshot(self.root, ["anything"])
        snap.restore()  # no backup dir -> must not raise

    def test_newly_created_files_and_dirs_are_removed_on_restore(self) -> None:
        # Ciclo 4/S2 regression: paths absent pre-snapshot but created during
        # apply (e.g. a 'patch' variant adding a file) must NOT survive revert.
        (self.root / "present.txt").write_text("keep")
        snap = FileSnapshot(self.root, ["present.txt", "added.txt", "added_dir"])
        snap.__enter__()
        (self.root / "present.txt").write_text("changed")
        (self.root / "added.txt").write_text("born")
        (self.root / "added_dir").mkdir()
        (self.root / "added_dir" / "x").write_text("x")
        snap.__exit__(None, None, None)
        self.assertEqual((self.root / "present.txt").read_text(), "keep")
        self.assertFalse((self.root / "added.txt").exists())
        self.assertFalse((self.root / "added_dir").exists())

    def test_newly_created_symlink_is_removed_on_restore(self) -> None:
        target = self.root / "target.txt"
        target.write_text("t")
        snap = FileSnapshot(self.root, ["link"])
        snap.__enter__()
        try:
            (self.root / "link").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported here")
        snap.__exit__(None, None, None)
        self.assertFalse((self.root / "link").is_symlink())


class ProjectTargetLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _target(self, manifest: TargetManifest) -> ProjectTarget:
        return ProjectTarget(self.root, manifest)

    def test_prepare_build_test_clean_run_and_build_failure_raises(self) -> None:
        m = _manifest(
            prepare_command='python3 -c "from pathlib import Path;Path(\'p\').write_text(\'1\')"',
            build_command='python3 -c "from pathlib import Path;Path(\'b\').write_text(\'1\')"',
            test_command='python3 -c "from pathlib import Path;Path(\'t\').write_text(\'1\')"',
            clean_command='python3 -c "from pathlib import Path;Path(\'b\').unlink()"',
        )
        target = self._target(m)
        self.assertIsNotNone(target.prepare(101))
        self.assertTrue((self.root / "p").exists())
        self.assertIsNotNone(target.build())
        self.assertTrue((self.root / "b").exists())
        self.assertTrue(target.test().ok)
        target.clean()
        self.assertFalse((self.root / "b").exists())

        bad = _manifest(build_command='python3 -c "import sys;sys.exit(3)"')
        with self.assertRaises(RuntimeError):
            self._target(bad).build()

    def _existing(self, name: str, text: str = "orig") -> Path:
        path = self.root / name
        path.write_text(text)
        return path

    def test_patch_variant_overwrite_is_reverted(self) -> None:
        dest = self._existing("code.py", "ORIGINAL")
        src = self.root / "patch_source.py"
        src.write_text("PATCHED")
        variant = Variant(name="p", mode="patch", files={"code.py": str(src)})
        target = self._target(_manifest(artifact_paths=["code.py"]))
        snapshot = target.apply_variant(variant)
        self.assertEqual(dest.read_text(), "PATCHED")
        target.revert_variant(snapshot, variant)
        self.assertEqual(dest.read_text(), "ORIGINAL")

    def test_failed_apply_command_rolls_back(self) -> None:
        self._existing("code.py", "ORIGINAL")
        variant = Variant(
            name="boom", mode="script", files={"code.py": str(self.root / "unused.py")},
            apply_command='python3 -c "from pathlib import Path;Path(\'code.py\').write_text(\'X\');import sys;sys.exit(1)"',
        )
        target = self._target(_manifest())
        with self.assertRaises(RuntimeError):
            target.apply_variant(variant)
        self.assertEqual((self.root / "code.py").read_text(), "ORIGINAL")  # rolled back

    def test_patch_variant_adding_new_file_is_fully_reverted(self) -> None:
        src = self.root / "new_module.py"
        src.write_text("NEW = 1")  # variant copies a brand-new file in
        self.assertFalse((self.root / "injected.py").exists())
        variant = Variant(name="add", mode="patch", files={"injected.py": str(src)})
        target = self._target(_manifest())
        snapshot = target.apply_variant(variant)
        self.assertEqual((self.root / "injected.py").read_text(), "NEW = 1")
        target.revert_variant(snapshot, variant)
        self.assertFalse(
            (self.root / "injected.py").exists(),
            "a file created by a variant must not survive rollback")

    def test_failed_apply_that_created_a_file_rolls_new_file_back(self) -> None:
        variant = Variant(
            name="boom-add", mode="script", files={"created.txt": str(self.root / "u.py")},
            apply_command=(
                'python3 -c "from pathlib import Path;'
                "Path('created.txt').write_text('x');import sys;sys.exit(1)\""),
        )
        target = self._target(_manifest())
        with self.assertRaises(RuntimeError):
            target.apply_variant(variant)
        self.assertFalse((self.root / "created.txt").exists())

    def test_revert_command_runs_and_restores(self) -> None:
        self._existing("code.py", "ORIGINAL")
        src = self.root / "s.py"
        src.write_text("NEW")
        variant = Variant(
            name="scripted", mode="patch", files={"code.py": str(src)},
            revert_command='python3 -c "from pathlib import Path;Path(\'reverted\').write_text(\'1\')"',
        )
        target = self._target(_manifest())
        snapshot = target.apply_variant(variant)
        self.assertEqual((self.root / "code.py").read_text(), "NEW")
        target.revert_variant(snapshot, variant)
        self.assertEqual((self.root / "code.py").read_text(), "ORIGINAL")
        self.assertTrue((self.root / "reverted").exists())


class DetectKindTests(unittest.TestCase):
    def test_detect_prefers_python_then_ecosystems(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(detect_kind(root), "shell")
            (root / "package.json").write_text("{}")
            self.assertEqual(detect_kind(root), "node")
            with tempfile.TemporaryDirectory() as temp2:
                r2 = Path(temp2)
                (r2 / "Cargo.toml").write_text("[package]\nname='x'")
                self.assertEqual(detect_kind(r2), "cargo")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
