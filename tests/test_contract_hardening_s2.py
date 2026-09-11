"""S2 Ciclo 8 — contract consolidation & defense-in-depth.

Locks down three things that should never regress:

* per-mode Variant contracts (a ``patch``/``args``/``script`` variant that
  changes nothing is a misconfiguration that would benchmark baseline against
  itself, so it is rejected at parse time with a clear ValueError);
* patch *destination* confinement: destinations are always relative and can
  never write outside the resolved target root (absolute, ``..`` and symlink
  escapes are refused, both at parse and at apply time);
* PEP 561 ``py.typed`` ships (marker file + explicit setuptools package-data).
"""
from __future__ import annotations

import os
import tempfile
import tomllib
import unittest
from pathlib import Path

from mycelium_accel.targets.base import (
    ProjectTarget,
    TargetManifest,
    TargetSafetyError,
    Variant,
)

ROOT = Path(__file__).resolve().parents[1]


def _variant(payload: dict) -> Variant:
    return Variant.from_dict(payload)


class VariantContractTests(unittest.TestCase):
    def test_name_required_and_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            _variant({"mode": "env"})
        with self.assertRaises(ValueError):
            _variant({"name": "   ", "mode": "env"})

    def test_patch_requires_files(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _variant({"name": "empty", "mode": "patch"})
        self.assertIn("files", str(ctx.exception))

    def test_patch_rejects_empty_destination(self) -> None:
        with self.assertRaises(ValueError):
            _variant({"name": "p", "mode": "patch",
                      "files": {"": "variant.py"}})

    def test_args_requires_args(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _variant({"name": "a", "mode": "args"})
        self.assertIn("args", str(ctx.exception))

    def test_script_requires_apply_command(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _variant({"name": "s", "mode": "script"})
        self.assertIn("apply_command", str(ctx.exception))
        # ... but a well-formed script variant parses
        v = _variant({"name": "s", "mode": "script",
                      "apply_command": "python apply.py"})
        self.assertEqual(v.apply_command, "python apply.py")

    def test_well_formed_variants_parse(self) -> None:
        self.assertEqual(_variant({"name": "e", "mode": "env",
                                   "env": {"PYTHONOPTIMIZE": "1"}}).mode, "env")
        self.assertEqual(_variant({"name": "a", "mode": "args",
                                   "args": ["-O3"]}).args, ["-O3"])
        p = _variant({"name": "p", "mode": "patch",
                      "files": {"pkg/mod.py": "variant_mod.py"}})
        self.assertEqual(p.files, {"pkg/mod.py": "variant_mod.py"})

    def test_patch_destination_must_be_relative_at_parse(self) -> None:
        for bad in ("/etc/evil.py", "/tmp/x.py"):
            with self.subTest(dest=bad):
                with self.assertRaises(ValueError):
                    _variant({"name": "p", "mode": "patch",
                              "files": {bad: "v.py"}})
        with self.assertRaises(ValueError):
            _variant({"name": "p", "mode": "patch",
                      "files": {"../../escape.py": "v.py"}})


class _TargetTmp(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.work = Path(self._td.name)
        self.root = self.work / "proj"
        self.root.mkdir()
        self.source = self.work / "variant_mod.py"
        self.source.write_text("VALUE = 2\n", encoding="utf-8")

    def target(self) -> ProjectTarget:
        manifest = TargetManifest.from_dict({
            "name": "confine", "kind": "shell",
            "benchmark_command": "python -c \"print(1)\"",
        })
        return ProjectTarget(self.root, manifest)


class PatchConfinementTests(_TargetTmp):
    def _assert_outside_untouched(self, outside: Path) -> None:
        self.assertFalse(outside.exists(),
                         f"patch escaped the target root: {outside}")

    def test_relative_patch_applies_and_reverts(self) -> None:
        target = self.target()
        (self.root / "pkg").mkdir()
        dest = self.root / "pkg" / "mod.py"
        dest.write_text("VALUE = 1\n", encoding="utf-8")
        variant = Variant(name="ok", mode="patch",
                          files={"pkg/mod.py": str(self.source)})
        snap = target.apply_variant(variant)
        self.assertIn("VALUE = 2", dest.read_text(encoding="utf-8"))
        target.revert_variant(snap, variant)
        self.assertEqual(dest.read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_runtime_blocks_parent_traversal_destination(self) -> None:
        target = self.target()
        outside = self.work / "escape.py"
        variant = Variant(name="evil", mode="patch",
                          files={"../escape.py": str(self.source)})
        with self.assertRaises(TargetSafetyError):
            target.apply_variant(variant)
        self._assert_outside_untouched(outside)

    def test_runtime_blocks_absolute_destination(self) -> None:
        target = self.target()
        outside = self.work / "abs_evil.py"
        variant = Variant(name="evil", mode="patch",
                          files={str(outside): str(self.source)})
        with self.assertRaises(TargetSafetyError):
            target.apply_variant(variant)
        self._assert_outside_untouched(outside)

    @unittest.skipUnless(os.name == "posix", "symlink confinement is POSIX")
    def test_runtime_blocks_symlink_parent_escape(self) -> None:
        outside_dir = self.work / "outside"
        outside_dir.mkdir()
        link = self.root / "link"
        link.symlink_to(outside_dir, target_is_directory=True)
        target = self.target()
        variant = Variant(name="evil", mode="patch",
                          files={"link/evil.py": str(self.source)})
        with self.assertRaises(TargetSafetyError):
            target.apply_variant(variant)
        self._assert_outside_untouched(outside_dir / "evil.py")


class Pep561MarkerTests(unittest.TestCase):
    def test_py_typed_marker_present(self) -> None:
        marker = ROOT / "mycelium_accel" / "py.typed"
        self.assertTrue(marker.exists(), "PEP 561 marker must ship in-package")
        self.assertEqual(marker.read_bytes(), b"", "py.typed is an empty marker")

    def test_pyproject_declares_package_data(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
        package_data = (pyproject["tool"]["setuptools"]["package-data"]
                        ["mycelium_accel"])
        self.assertIn("py.typed", package_data)


if __name__ == "__main__":
    unittest.main()
