"""V3.1: release.sh guards (never tags from tests — help + validation only)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release.sh"
sys.path.insert(0, str(ROOT / "scripts"))
import release_check  # noqa: E402


@unittest.skipIf(os.name == "nt",
                     "release.sh is a posix release tool (bash/mktemp/venv-bin); "
                     "the bash available on Windows CI cannot run it reliably")
class ReleaseScriptTests(unittest.TestCase):
    def test_help(self) -> None:
        proc = subprocess.run(["bash", str(SCRIPT), "--help"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("vX.Y.Z", proc.stdout)

    def test_bad_tag_refused(self) -> None:
        proc = subprocess.run(["bash", str(SCRIPT), "nope"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("bad TAG", proc.stderr)

    def test_version_mismatch_refused_before_build(self) -> None:
        # Hermetic: script copies + fixtures in tmp (NOT a git repo, so the
        # dirty/tag guards pass through and the version check is reached).
        import shutil

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / "scripts", root / "scripts")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "x"\nversion = "1.0.0"\n', encoding="utf-8")
            pkg = root / "mycelium_accel"
            pkg.mkdir()
            (pkg / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
            (root / "CHANGES.md").write_text("# CHANGES\n", encoding="utf-8")
            proc = subprocess.run(["bash", str(root / "scripts" / "release.sh"), "v9.9.9"],
                                  capture_output=True, text=True, cwd=root)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("version mismatch", proc.stderr)
            self.assertFalse((root / "dist").exists(), "build must not start")


class ReleaseCheckTests(unittest.TestCase):
    def _fixture(self, root: Path, *, version: str, init_version: str, changes: str) -> None:
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
        pkg = root / "mycelium_accel"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(f'__version__ = "{init_version}"\n', encoding="utf-8")
        (root / "CHANGES.md").write_text(changes, encoding="utf-8")

    def test_all_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, version="2.0.0", init_version="2.0.0",
                          changes="# CHANGES\n\n## 2.0.0 big one (tag v2.0.0)\n")
            self.assertEqual(release_check.check("v2.0.0", root), [])

    def test_pyproject_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, version="2.0.1", init_version="2.0.0",
                          changes="## v2.0.0\n")
            errors = release_check.check("v2.0.0", root)
            self.assertEqual(len(errors), 1)
            self.assertIn("version mismatch", errors[0])

    def test_init_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, version="2.0.0", init_version="1.9.9",
                          changes="## v2.0.0\n")
            self.assertTrue(any("version mismatch" in e
                                for e in release_check.check("v2.0.0", root)))

    def test_missing_changes_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, version="2.0.0", init_version="2.0.0",
                          changes="# CHANGES\n\n## 1.9.9 old\n")
            errors = release_check.check("v2.0.0", root)
            self.assertEqual(errors, ["CHANGES.md has no entry for v2.0.0"])


if __name__ == "__main__":
    unittest.main()
