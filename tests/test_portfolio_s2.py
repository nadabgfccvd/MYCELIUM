"""S2 Cycle 7 — hermetic guards for the NEW real-world portfolio (P4/P5/P6).

The live runs need network and the pinned third-party libraries
(scripts/reproduce_portfolio_s2.sh), so they are NOT part of CI. These tests
protect the *shipped artifacts* without any of that:

* the three new manifests parse into TargetManifest with the right variants;
* every new bench/gate script byte-compiles;
* the shipped Unidecode patch's fast path is EXECUTED against the unchanged
  upstream loop over synthetic character tables, including fuzz, edge
  codepoints, surrogates and every ``errors`` policy (no network, no Unidecode
  install — a tiny in-memory package shim is injected).
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import warnings
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from pathlib import Path

from mycelium_accel.targets.base import TargetManifest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts" / "portfolio"
DATA = ROOT / "docs" / "data" / "portfolio"
FIXTURE_PRISTINE = ROOT / "tests" / "fixtures" / "unidecode_1.3.8_pristine_init.py"


class ManifestAssetsTests(unittest.TestCase):
    def _manifest(self, leaf: str) -> TargetManifest:
        return TargetManifest.load(ASSETS / "manifests" / leaf)

    def test_p4_unidecode_patch_manifest(self) -> None:
        m = self._manifest("mycelium.target.unidecode.json")
        self.assertEqual(len(m.variants), 1)
        v = m.variants[0]
        self.assertEqual(v.mode, "patch")
        self.assertEqual(v.name, "str-translate-fastpath")
        self.assertEqual(v.files,
                         {"unidecode/__init__.py": "variant_init_patched.py"})
        self.assertEqual(m.metric_name, "seconds")

    def test_p5_p6_env_manifests(self) -> None:
        for leaf in ("mycelium.target.natsort.json",
                     "mycelium.target.markdown.json"):
            with self.subTest(manifest=leaf):
                m = self._manifest(leaf)
                self.assertEqual(len(m.variants), 1)
                v = m.variants[0]
                self.assertEqual(v.mode, "env")
                self.assertEqual(v.env.get("PYTHONOPTIMIZE"), "1")
                self.assertTrue(m.benchmark_command.startswith("python bench_"))

    def test_portfolio_scripts_bytecompile(self) -> None:
        import py_compile

        for leaf in (
            "bench_unidecode.py", "digest_gate_unidecode.py",
            "bench_natsort.py", "bench_markdown.py",
            "digest_gate_pylib_s2.py",
        ):
            with self.subTest(script=leaf):
                py_compile.compile(str(ASSETS / leaf), doraise=True)

    def test_patch_and_full_file_present_and_nonempty(self) -> None:
        patch = DATA / "unidecode_translate_fastpath.patch"
        full = DATA / "unidecode_init_translate_fastpath.py"
        text = full.read_text(encoding="utf-8")
        self.assertIn("return string.translate(table)", text)
        self.assertIn("def _unidecode_loop", text)
        self.assertIn("unidecode/__init__.py", patch.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Execute the SHIPPED patched file with fake unidecode.x### data modules.
# ---------------------------------------------------------------------------

# section -> list of replacement strings (index == codepoint position)
_FAKE_TABLES: dict[int, list[str | None]] = {
    0x00: [""] * 0x80 + [f"a{i:02x}" for i in range(0x80, 0x100)],
    0x01: [f"b{i:02x}" for i in range(0x40)] + [None] * (0x100 - 0x40),
    0x41: [f"cyr{i:02x}" for i in range(0x100)],
    0xE0: [None] * 0x20 + [f"gr{i:02x}" for i in range(0xE0)],
    0x4E0: [f"han{i:02x}" for i in range(0x60)] + [None] * (0x100 - 0x60),
}


class _FakeTableLoader(Loader):
    def __init__(self, section: int) -> None:
        self.section = section

    def create_module(self, spec):  # noqa: ANN001
        return types.ModuleType(spec.name)

    def exec_module(self, module: types.ModuleType) -> None:
        if self.section not in _FAKE_TABLES:
            raise ModuleNotFoundError(module.__name__)  # unconfigured -> no data
        module.data = _FAKE_TABLES[self.section]


class _FakeFinder:
    def find_spec(self, fullname: str, path, target=None):  # noqa: ANN001
        if fullname == "unidecode":
            return importlib.util.spec_from_loader(
                fullname, loader=None, is_package=True)
        if fullname.startswith("unidecode.x"):
            section = int(fullname.rsplit("x", 1)[1], 16)
            return ModuleSpec(fullname, _FakeTableLoader(section))
        return None


def _load_patched_unidecode() -> types.ModuleType:
    """Exec the shipped patched __init__.py as the ``unidecode`` package."""
    mod = types.ModuleType("unidecode")
    mod.__path__ = []  # mark as package; submodules come from the fake finder
    sys.modules["unidecode"] = mod
    source = (DATA / "unidecode_init_translate_fastpath.py").read_text(
        encoding="utf-8")
    exec(compile(source, "unidecode_init_translate_fastpath.py", "exec"),
         mod.__dict__)
    return mod


class UnidecodeFastPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._finder = _FakeFinder()
        sys.meta_path.insert(0, cls._finder)
        cls.mod = _load_patched_unidecode()

    @classmethod
    def tearDownClass(cls) -> None:
        sys.meta_path.remove(cls._finder)
        for name in list(sys.modules):
            if name == "unidecode" or name.startswith("unidecode."):
                del sys.modules[name]

    def test_fast_path_matches_loop_on_fuzz(self) -> None:
        rng = random.Random(20260910)
        sections = list(_FAKE_TABLES)
        for _ in range(400):
            chars: list[str] = []
            for _ in range(rng.randrange(0, 120)):
                bucket = rng.randrange(10)
                if bucket < 6:
                    section = rng.choice(sections)
                    cp = section * 256 + rng.randrange(0, 0x100)
                elif bucket < 8:
                    cp = rng.randrange(0x20, 0x7F)  # ASCII
                elif bucket == 8:
                    cp = rng.choice((0xF0000, 0xE0000, 0x10FFFF, 0xE000))
                else:
                    cp = rng.choice((0xD800, 0xD83D, 0xDFFF))  # surrogates
                chars.append(chr(cp))
            s = "".join(chars)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fast = self.mod.unidecode(s)
                loop = self.mod._unidecode_loop(s, "ignore", "?")
            self.assertEqual(
                fast, loop,
                msg=f"fast path diverged from loop for {s!r}: {fast!r} vs {loop!r}")

    def test_known_mappings_and_ascii_passthrough(self) -> None:
        # ASCII is returned untouched by the ascii fast branch
        self.assertEqual(self.mod.unidecode("Hello, World 123!"),
                         "Hello, World 123!")
        # A character present in a fake table maps to its cell
        c = chr(0x41 * 256 + 0x05)
        self.assertEqual(self.mod.unidecode(c), "cyr05")
        # A character beyond all tables (PUA) is dropped under ignore
        self.assertEqual(self.mod.unidecode("x\U000F0000y"), "xy")

    def test_error_policies_fall_back_to_loop(self) -> None:
        missing = "x\U000F0000y"
        self.assertEqual(self.mod.unidecode(missing, errors="replace",
                                            replace_str="#"), "x#y")
        self.assertEqual(self.mod.unidecode(missing, errors="preserve"),
                         "x\U000F0000y")
        with self.assertRaises(self.mod.UnidecodeError) as ctx:
            self.mod.unidecode("a\U000F0000b", errors="strict")
        self.assertEqual(ctx.exception.index, 1)
        # Invalid errors only surfaces once the loop hits an unmapped char
        # (pure-ASCII input short-circuits before any policy branch).
        with self.assertRaises(self.mod.UnidecodeError):
            self.mod.unidecode("a\U000F0000", errors="bogus")

    def test_surrogate_warns_and_agrees(self) -> None:
        s = "a\ud83db"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            out = self.mod.unidecode(s)
            loop = self.mod._unidecode_loop(s, "ignore", "?")
        self.assertEqual(out, loop)
        self.assertTrue(any(issubclass(w.category, RuntimeWarning)
                            for w in caught))

    def test_short_table_position_out_of_range_is_none(self) -> None:
        # section 1 table only covers 0x00..0x3f
        in_range = chr(0x1 * 256 + 0x10)
        out_range = chr(0x1 * 256 + 0x80)
        self.assertEqual(self.mod.unidecode(in_range), "b10")
        self.assertEqual(self.mod.unidecode(out_range), "")


class AllPortfolioManifestsTests(unittest.TestCase):
    """Every shipped portfolio manifest must load and be benchmarkable."""

    def test_all_manifests_load(self) -> None:
        paths = sorted((ASSETS / "manifests").glob("mycelium.target.*.json"))
        self.assertGreaterEqual(len(paths), 6)  # 3 original + P4/P5/P6
        for path in paths:
            with self.subTest(manifest=path.name):
                m = TargetManifest.load(path)
                self.assertTrue(m.benchmark_command)
                self.assertTrue(m.test_command)
                self.assertEqual(m.metric_name, "seconds")
                self.assertTrue(m.lower_is_better)
                self.assertTrue(m.variants)
                for variant in m.variants:
                    self.assertTrue(variant.name)
                    self.assertIn(variant.mode,
                                  {"env", "args", "patch", "script", "profile"})


# Expected decision direction locked into the archived raw sweeps (S2 cases).
_EXPECTED_DIRECTION = {
    "unidecode": "accept",   # CI strictly positive
    "natsort": "reject_neg",  # CI strictly negative
    "markdown": "reject_crosses_zero",  # CI spans zero
}


class ArchivedEvidenceTests(unittest.TestCase):
    """Claims in CASE docs must match the archived raw sweep artifacts."""

    def _sweep(self, name: str) -> dict:
        return json.loads((DATA / f"{name}_sweep.json").read_text("utf-8"))

    def test_every_archived_sweep_has_canonical_schema(self) -> None:
        paths = sorted(DATA.glob("*_sweep.json"))
        self.assertGreaterEqual(len(paths), 6)
        for path in paths:
            with self.subTest(sweep=path.name):
                d = json.loads(path.read_text("utf-8"))
                self.assertEqual(d["metric"], "seconds")
                self.assertTrue(d["lower_is_better"])
                candidates = [s["candidate"] for s in d["summaries"]]
                self.assertIn("baseline", candidates)
                self.assertEqual(len(candidates), 2)  # baseline + one variant
                for summary in d["summaries"]:
                    self.assertTrue(summary.get("runs"))
                for comp in d["comparisons"]:
                    self.assertIsInstance(comp["ci_low"], float)
                    self.assertIsInstance(comp["ci_high"], float)
                    self.assertIsInstance(comp["p_value"], float)

    def test_s2_decisions_match_archived_confidence_intervals(self) -> None:
        for name, direction in _EXPECTED_DIRECTION.items():
            with self.subTest(case=name):
                comp = self._sweep(name)["comparisons"][0]
                lo, hi = comp["ci_low"], comp["ci_high"]
                if direction == "accept":
                    self.assertGreater(lo, 0.0,
                                       f"{name} should accept (CI > 0)")
                elif direction == "reject_neg":
                    self.assertLess(hi, 0.0,
                                    f"{name} CI should be strictly negative")
                else:  # reject_crosses_zero
                    self.assertLess(lo, 0.0)
                    self.assertGreaterEqual(hi, 0.0)

    def test_archived_unidecode_summary_has_wall_level_gap(self) -> None:
        # Independent of the paired test: the median wall time ordering must
        # also favor the variant (guards against a sign-flipped archive).
        import statistics

        d = self._sweep("unidecode")
        med = {
            s["candidate"]: statistics.median(
                r["value"] for r in s["runs"] if r.get("ok"))
            for s in d["summaries"]
        }
        self.assertLess(med["str-translate-fastpath"], med["baseline"])


class PatchReproductionTests(unittest.TestCase):
    """The shipped .patch must rebuild the shipped patched file from pristine."""

    @unittest.skipUnless(os.name == "posix" and shutil.which("git"),
                         "git apply is a POSIX/git tool")
    def test_patch_applied_to_fixture_equals_shipped_file(self) -> None:
        patch = DATA / "unidecode_translate_fastpath.patch"
        shipped = DATA / "unidecode_init_translate_fastpath.py"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pkg = root / "unidecode"
            pkg.mkdir()
            shutil.copy(FIXTURE_PRISTINE, pkg / "__init__.py")
            proc = subprocess.run(
                ["git", "apply", str(patch)], cwd=root,
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                (pkg / "__init__.py").read_text(encoding="utf-8"),
                shipped.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
