"""Sessão 2, Ciclo 1 — hygiene & documentary-truth guards.

These freeze the concrete fixes from the first cycle of the second autonomous
session so they cannot silently regress:

* the zero-variant first-run decision says *no variants* (not "not enough
  paired data") and points the user at the next step;
* the README rename banner is well-formed Markdown (a bold/code span was left
  unclosed once and rendered the rest of the block as raw punctuation);
* the ``.desktop`` launcher is relocatable (no hardcoded ``$HOME`` path);
* packaging metadata uses the PEP 639 SPDX license expression (the TOML-table
  form and the ``License ::`` classifier emit setuptools deprecation warnings);
* the LICENSE file names a holder and the shipped shell launchers keep their
  executable bit (on POSIX).
"""
from __future__ import annotations

import os
import tomllib
import unittest
from pathlib import Path

from mycelium_accel.accelerate_generic import decide_best_candidate
from mycelium_accel.bench import BenchmarkRun, BenchmarkSweep, CandidateSummary
from mycelium_accel.bench import summarize_runs

ROOT = Path(__file__).resolve().parent.parent


def _baseline_only_sweep() -> BenchmarkSweep:
    runs = [
        BenchmarkRun("baseline", seed, "seconds", 0.01 * seed / 100.0, 0.01, True)
        for seed in (101, 103, 107)
    ]
    return BenchmarkSweep(
        target="t",
        metric="seconds",
        lower_is_better=True,
        summaries=[summarize_runs("baseline", runs)],
        comparisons=[],
    )


class ZeroVariantTruthTests(unittest.TestCase):
    def test_no_variants_is_distinct_from_insufficient_data(self) -> None:
        best, reasons, _ = decide_best_candidate(_baseline_only_sweep(), "baseline")
        self.assertIsNone(best)
        self.assertEqual(len(reasons), 1)
        self.assertIn("variants", reasons[0])
        self.assertIn("accelerate init", reasons[0])

    def test_challenger_without_pairs_uses_pairing_reason_not_empty_reason(self) -> None:
        sweep = _baseline_only_sweep()
        # A challenger that produced nothing shares zero paired seeds — the
        # engine must report a pairing problem, never the "no variants" line.
        sweep.summaries.append(CandidateSummary(
            "ghost", [], float("inf"), 0.0, float("inf"), float("inf"), float("inf")))
        best, reasons, _ = decide_best_candidate(sweep, "baseline")
        self.assertIsNone(best)
        self.assertTrue(reasons)
        self.assertFalse(any("defines only a baseline" in r for r in reasons))
        self.assertTrue(any("paired seeds" in r for r in reasons))


class ReadmeTruthTests(unittest.TestCase):
    def test_rename_banner_markdown_well_formed(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        # The fixed line closes both the code span and the bold span.
        self.assertIn("→ **`mycelium-accel`**,\n", text)
        # The previous malformed form (stray doubled backtick, unclosed bold).
        self.assertNotIn("**`mycelium-accel``,", text)


class LauncherHygieneTests(unittest.TestCase):
    def test_desktop_launcher_is_relocatable(self) -> None:
        text = (ROOT / "OPEN_MYCELIUM_AUTO_EVOLVE_UI.desktop").read_text(encoding="utf-8")
        self.assertNotIn("/home/user/", text)
        self.assertNotIn("mycelium-prototype", text)
        self.assertIn("%k", text)  # derives its folder from its own location
        self.assertIn("OPEN_MYCELIUM_AUTO_EVOLVE_UI.sh", text)

    def test_no_hardcoded_home_in_launchers_and_scripts(self) -> None:
        offenders = []
        for path in list(ROOT.glob("OPEN_MYCELIUM_AUTO_EVOLVE_UI.*")) + list((ROOT / "scripts").glob("*.py")):
            if "/home/user/" in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    @unittest.skipUnless(os.name == "posix", "executable bit is POSIX-specific")
    def test_shell_launchers_are_executable(self) -> None:
        scripts = list((ROOT / "scripts").glob("*.sh"))
        launchers = list(ROOT.glob("OPEN_MYCELIUM_AUTO_EVOLVE_UI.*"))
        missing = [
            str(p.relative_to(ROOT))
            for p in scripts + launchers
            if p.suffix in {".sh", ".command"} and not os.access(p, os.X_OK)
        ]
        self.assertEqual(missing, [], f"chmod +x the shipped shell launchers: {missing}")


class PackagingLicenseTests(unittest.TestCase):
    def test_pyproject_uses_pep639_spdx_license(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
        project = data["project"]
        self.assertEqual(project.get("license"), "MIT")
        self.assertEqual(project.get("license-files"), ["LICENSE"])
        self.assertFalse(
            any(c.startswith("License ::") for c in project.get("classifiers", [])),
            "PEP 639: drop the 'License ::' classifier in favour of the SPDX expression",
        )
        # build backend must be new enough to parse the expression
        self.assertTrue(
            any("setuptools>=77" in req for req in data["build-system"]["requires"])
        )

    def test_license_file_names_a_holder(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 MYCELIUM-Accel contributors", license_text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
