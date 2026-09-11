"""S2 Ciclo 9 — hermetic guards for the competitor sieve comparison.

The compiled competitors (mypyc/Cython .so) need gcc and are built by
``scripts/run_competitor_sieve.sh`` (manual). These tests protect everything
that is checkable WITHOUT a compiler:

* the safe pure-Python MYCELIUM variant (bulk-slice sieve) is *correct*: it
  matches the classic implementation and known pi(n) constants over many n;
* the correctness gate passes against BOTH kernels and reproduces the pin;
* the manifest/contract for the patch variant is valid;
* the archived competitor JSON artifacts agree on the checksum, and the
  documented ordering/decision matches the recorded data (claims cannot drift
  from evidence).
"""
from __future__ import annotations

import importlib.util
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mycelium_accel.targets.base import TargetManifest

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "scripts" / "competitors"
ART = ROOT / "docs" / "data" / "competitors"

# Independent reference (distinct, list-of-int Eratosthenes) used only here.
def _ref_primes(n: int) -> list[int]:
    if n < 3:
        return []
    sieve = [True] * n
    sieve[0] = sieve[1] = False
    for p in range(2, int(n**0.5) + 1):
        if sieve[p]:
            for k in range(p * p, n, p):
                sieve[k] = False
    return [i for i in range(n) if sieve[i]]


def _load(leaf: str, name: str):
    path = COMP / leaf
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SieveEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.classic = _load("kernel.py", "sieve_classic")
        cls.slice_ = _load("kernel_mycelium.py", "sieve_slice")

    def test_all_three_implementations_agree(self) -> None:
        sizes = [0, 1, 2, 3, 4, 5, 6, 10, 11, 30, 100, 1000, 100_000]
        known = {0: 0, 10: 4, 100: 25, 1000: 168, 100_000: 9592}
        for n in sizes:
            a = self.classic.primes_below(n)
            b = self.slice_.primes_below(n)
            ref = _ref_primes(n)
            self.assertEqual(a, ref, f"classic diverged at n={n}")
            self.assertEqual(b, ref, f"bulk-slice diverged at n={n}")
            if n in known:
                self.assertEqual(len(b), known[n])

    def test_million_prime_constants(self) -> None:
        primes = self.slice_.primes_below(1_000_000)
        self.assertEqual(len(primes), 78_498)        # pi(10^6)
        self.assertEqual(sum(primes), 37_550_402_023)

    def test_bulk_slice_is_a_python_pure_portable_artifact(self) -> None:
        # The MYCELIUM contender imports stdlib only (no compiler artifacts).
        text = (COMP / "kernel_mycelium.py").read_text(encoding="utf-8")
        self.assertIn("bytearray", text)
        self.assertNotIn("cdef", text)
        self.assertNotIn("mypyc", text)


class SieveDigestGateTests(unittest.TestCase):
    def _workdir(self) -> Path:
        td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
        w = Path(td)
        for leaf in ("digest_gate_sieve.py", "kernel.py", "kernel_mycelium.py"):
            shutil.copy(COMP / leaf, w / leaf)
        return w

    def _run_gate(self, w: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "digest_gate_sieve.py"], cwd=w,
            capture_output=True, text=True)

    def test_gate_passes_on_classic_and_on_patched_kernel(self) -> None:
        w = self._workdir()
        first = self._run_gate(w)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("sieve digest gate OK", first.stdout)
        # Apply the patch: replace kernel.py with the bulk-slice variant.
        shutil.copy(w / "kernel_mycelium.py", w / "kernel.py")
        second = self._run_gate(w)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout.strip(), second.stdout.strip())

    def test_gate_rejects_a_corrupt_kernel(self) -> None:
        w = self._workdir()
        (w / "kernel.py").write_text(
            "def primes_below(n):\n    return [2, 3]\n", encoding="utf-8")
        proc = self._run_gate(w)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("gate FAILED", proc.stderr)


class SieveManifestTests(unittest.TestCase):
    def test_manifest_contract(self) -> None:
        m = TargetManifest.load(COMP / "manifests" / "mycelium.target.sieve.json")
        self.assertEqual(len(m.variants), 1)
        v = m.variants[0]
        self.assertEqual(v.mode, "patch")
        self.assertEqual(v.files, {"kernel.py": "kernel_mycelium.py"})
        self.assertEqual(m.metric_name, "seconds")

    def test_python_sources_bytecompile(self) -> None:
        for leaf in ("kernel.py", "kernel_mycelium.py", "kernel_mypyc.py",
                     "kernel_mypyc_fast.py", "bench_cli.py",
                     "digest_gate_sieve.py", "setup_cython.py"):
            with self.subTest(file=leaf):
                py_compile.compile(str(COMP / leaf), doraise=True)


class ArchivedSieveEvidenceTests(unittest.TestCase):
    IMPLS = ("cpython", "cpython_O", "mycelium", "mypyc", "mypyc_fast",
             "cython", "cython_fast")

    def _row(self, impl: str) -> dict:
        return json.loads((ART / f"sieve_{impl}.json").read_text("utf-8"))

    def test_all_approaches_produce_identical_checksums(self) -> None:
        for impl in self.IMPLS:
            with self.subTest(impl=impl):
                d = self._row(impl)
                self.assertEqual(d["count_1m"], 78_498)
                self.assertEqual(d["sum_1m"], 37_550_402_023)

    def test_documented_ordering_matches_artifacts(self) -> None:
        seconds = {impl: self._row(impl)["seconds"] for impl in self.IMPLS}
        # The safe pure-Python variant must clearly beat classic CPython.
        self.assertLess(seconds["mycelium"], 0.75 * seconds["cpython"])
        # -O without asserts is no real win (documented as inert/noise).
        self.assertGreater(seconds["cpython_O"], 0.8 * seconds["cpython"])
        # The fully-typed Cython build is the only approach ahead of the
        # portable pure-Python variant, and only by a modest margin.
        self.assertLessEqual(seconds["cython_fast"], seconds["mycelium"] * 1.25)

    def test_mycelium_decision_artifact_accepts(self) -> None:
        d = json.loads((ART / "sieve_mycelium_decision.json").read_text("utf-8"))
        self.assertEqual(d["best_candidate"], "bulk-slice-sieve")
        comp = d["comparisons"][0]
        self.assertGreater(comp["ci_low"], 0.0)
        self.assertLessEqual(comp["p_value_corrected"], 0.05)


if __name__ == "__main__":
    unittest.main()
