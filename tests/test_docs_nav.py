"""C9 — docs site nav: every user-facing page linked, no dangling refs.

Historical records (ROADMAP_*, EXECUTION_*, EVAL_*, GATE_*, M*_*, BENCH_*,
EC3_PR_PACK, VELOCITY_BASELINE, QUALITY_BASELINE, TUTORIAL-adjacent notes)
stay out of the nav by design — they are reachable via git, not the site.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# User-facing pages: forgetting one in mkdocs.yml nav reds this test.
USER_DOCS = [
    "QUICKSTART.md",
    "index.md",
    "TUTORIAL_10MIN.md",
    "CASE_MYCELIUM_20260909.md",
    "CASE_C_FLAGS_20260909.md",
    "CASE_EC3_20260909.md",
    "CASE_EC4_20260909.md",
    "S2_PARALLEL_PROOF_20260910.md",
    "RUNS.md",
    "RELEASE.md",
    "KILLSWITCH_SANDBOX_CHECKLIST.md",
    "SELF_IMPROVEMENT.md",
    "PERFORMANCE.md",
    "ARCHITECTURE.md",
    "API_STABLE_1.0.md",
    "ERRORS.md",
    "adr/0001-integrations.md",
    "adr/0002-open-growth-decision.md",
]


class DocsNavTests(unittest.TestCase):
    def test_user_docs_are_in_nav(self) -> None:
        nav = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        for doc in USER_DOCS:
            with self.subTest(doc=doc):
                self.assertIn(doc, nav)

    def test_nav_refs_exist(self) -> None:
        nav = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        refs = set(re.findall(r"[\w./-]+\.md", nav))
        self.assertGreater(len(refs), 10)
        for ref in sorted(refs):
            with self.subTest(ref=ref):
                self.assertTrue((ROOT / "docs" / ref).is_file(), f"dangling: {ref}")

    def test_user_docs_exist(self) -> None:
        for doc in USER_DOCS:
            with self.subTest(doc=doc):
                self.assertTrue((ROOT / "docs" / doc).is_file())


if __name__ == "__main__":
    unittest.main()
