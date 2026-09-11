"""Ciclo 1 — doc-truth guards: docs must match measured reality.

Extends the docs<->parser gate (test_docs_parser) with two invariants that
drift silently and have already drifted once:

1. Version single-source: ``pyproject.toml`` and ``mycelium_accel.__version__``
   must agree (release.sh bumps both; this catches manual edits).
2. README's "Estrutura do repositório" tree must list EXACTLY the set of
   top-level ``*.py`` modules in ``mycelium_accel/`` — no phantoms, no
   omissions (7 modules were missing before this guard existed).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import tomllib

from mycelium_accel import __version__

ROOT = Path(__file__).resolve().parent.parent


class VersionTruthTests(unittest.TestCase):
    def test_pyproject_version_matches_package(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as fh:
            data = tomllib.load(fh)
        declared = data["project"]["version"]
        self.assertEqual(
            declared,
            __version__,
            "pyproject.toml and mycelium_accel.__version__ drifted apart",
        )


class StructureTruthTests(unittest.TestCase):
    """README's repository tree must mirror the real package layout."""

    def _readme_tree_block(self) -> str:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```text\n(.*?)```", text, flags=re.DOTALL)
        trees = [b for b in blocks if "mycelium_accel" in b and "├─" in b]
        self.assertTrue(trees, "README 'Estrutura do repositório' block not found")
        return trees[0]

    def _listed_py_modules(self, tree: str) -> set[str]:
        names = re.findall(r"^[\W_]+?(\w+\.py)\s*$", tree, flags=re.MULTILINE)
        return set(names)

    # Conventionally omitted from the README tree (never changes name).
    _OMITTED = {"__init__.py"}

    def test_readme_lists_exactly_real_modules(self) -> None:
        tree = self._readme_tree_block()
        listed = self._listed_py_modules(tree)
        real = {p.name for p in (ROOT / "mycelium_accel").glob("*.py")} - self._OMITTED
        self.assertEqual(
            listed,
            real,
            "README structure tree is stale: "
            f"missing={sorted(real - listed)} phantom={sorted(listed - real)}",
        )

    def test_readme_tree_names_the_real_root(self) -> None:
        tree = self._readme_tree_block()
        first = tree.strip().splitlines()[0]
        self.assertNotIn(
            "mycelium-prototype",
            first,
            "README tree still uses the pre-rename root name",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
