"""Ciclo 2 (Q) — toolchain validators: the honesty contract, tested.

ADR-0001 keeps ``llvm_alive2``/``mlir_eqsat`` as honest integration stubs:
no toolchain on the host → ``skipped`` (never a fabricated proof). That
contract was 0% covered — untested honesty is indistinguishable from luck.
Every status path is exercised here with a fake toolchain on PATH:

- alive-tv: skipped / verified / refuted (rc!=0) / refuted ("incorrect" in
  output) / error (rc==0 without the verified marker) / timeout;
- mlir-opt: skipped / optimized / error / timeout / command construction
  (transform-script vs pass-pipeline).

Fault-injection is built in: a report that lied (e.g. "verified" on rc!=0)
would flip exactly one assertion below.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mycelium_accel.validators import llvm_alive2, mlir_eqsat


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class Alive2Tests(unittest.TestCase):
    def test_skipped_without_toolchain(self) -> None:
        with mock.patch.object(llvm_alive2.shutil, "which", return_value=None):
            self.assertFalse(llvm_alive2.alive2_available())
            report = llvm_alive2.verify_translation(Path("a.ll"), Path("b.ll"))
        self.assertEqual(report.status, "skipped")
        self.assertIn("not installed", report.details)
        self.assertEqual(report.to_dict()["status"], "skipped")

    def _run(self, completed: subprocess.CompletedProcess[str] | None, **run_kwargs: object):
        """verify_translation with a fake toolchain present on PATH."""
        with (
            mock.patch.object(llvm_alive2.shutil, "which", return_value="/fake/bin/alive-tv"),
            mock.patch.object(
                llvm_alive2.subprocess, "run", **({"return_value": completed} if completed else run_kwargs)
            ) as fake_run,
        ):
            report = llvm_alive2.verify_translation(Path("a.ll"), Path("b.ll"))
        return report, fake_run

    def test_verified_on_clean_run(self) -> None:
        report, fake_run = self._run(
            _completed(0, stdout="Summary:\n0 incorrect transformations", stderr="")
        )
        self.assertEqual(report.status, "verified")
        cmd = fake_run.call_args.args[0]
        self.assertEqual(cmd[:2], ["alive-tv", str(Path("a.ll"))])
        self.assertEqual(cmd[2], str(Path("b.ll")))

    def test_refuted_on_nonzero_exit(self) -> None:
        report, _ = self._run(_completed(1, stdout="", stderr="1 incorrect transformations"))
        self.assertEqual(report.status, "refuted")

    def test_refuted_on_incorrect_marker_even_with_zero_exit(self) -> None:
        report, _ = self._run(_completed(0, stdout="", stderr="WARNING: 1 incorrect transformation"))
        self.assertEqual(report.status, "refuted")

    def test_error_on_zero_exit_without_marker(self) -> None:
        report, _ = self._run(_completed(0, stdout="garbage output", stderr=""))
        self.assertEqual(report.status, "error")

    def test_error_on_timeout(self) -> None:
        report, _ = self._run(None, side_effect=subprocess.TimeoutExpired(cmd="alive-tv", timeout=60))
        self.assertEqual(report.status, "error")
        self.assertIn("timed out", report.details)

    def test_to_dict_roundtrip(self) -> None:
        report = llvm_alive2.Alive2Report(status="skipped", details="x")
        self.assertEqual(report.to_dict(), {"status": "skipped", "tool": "alive-tv", "details": "x"})


class MlirEqsatTests(unittest.TestCase):
    def test_skipped_without_toolchain(self) -> None:
        with mock.patch.object(mlir_eqsat.shutil, "which", return_value=None):
            self.assertFalse(mlir_eqsat.mlir_opt_available())
            report = mlir_eqsat.run_transform_pipeline(Path("in.mlir"), Path("out.mlir"))
        self.assertEqual(report.status, "skipped")
        self.assertIn("not installed", report.details)

    def _run(
        self, completed: subprocess.CompletedProcess[str] | None, **run_kwargs: object
    ):
        with (
            mock.patch.object(mlir_eqsat.shutil, "which", return_value="/fake/bin/mlir-opt"),
            mock.patch.object(
                mlir_eqsat.subprocess, "run", **({"return_value": completed} if completed else run_kwargs)
            ) as fake_run,
        ):
            report = mlir_eqsat.run_transform_pipeline(
                Path("in.mlir"), Path("out.mlir"), passes="canonicalize"
            )
        return report, fake_run

    def test_optimized_on_success(self) -> None:
        report, _ = self._run(_completed(0, stdout="", stderr="(S) 0 ops"))
        self.assertEqual(report.status, "optimized")
        self.assertEqual(report.pipeline, "canonicalize")

    def test_error_on_failure(self) -> None:
        report, _ = self._run(_completed(2, stdout="", stderr="error: unknown pass"))
        self.assertEqual(report.status, "error")
        self.assertIn("unknown pass", report.details)

    def test_error_on_timeout(self) -> None:
        report, _ = self._run(None, side_effect=subprocess.TimeoutExpired(cmd="mlir-opt", timeout=120))
        self.assertEqual(report.status, "error")
        self.assertIn("timed out", report.details)

    def test_transform_script_builds_command(self) -> None:
        with (
            mock.patch.object(mlir_eqsat.shutil, "which", return_value="/fake/bin/mlir-opt"),
            mock.patch.object(mlir_eqsat.subprocess, "run", return_value=_completed(0)) as fake_run,
        ):
            script = Path("transform.mlir")
            report = mlir_eqsat.run_transform_pipeline(
                Path("in.mlir"), Path("out.mlir"), transform_script=script
            )
        self.assertEqual(report.status, "optimized")
        self.assertEqual(report.pipeline, "transform-script")
        cmd = fake_run.call_args.args[0]
        self.assertIn(f"--transform-script={script}", cmd)
        self.assertNotIn("--pass-pipeline=", " ".join(cmd))

    def test_passes_builds_command(self) -> None:
        report, fake_run = self._run(_completed(0))
        self.assertEqual(report.status, "optimized")
        cmd = fake_run.call_args.args[0]
        self.assertIn("--pass-pipeline=canonicalize", cmd)
        self.assertEqual(cmd[-2:], ["-o", str(Path("out.mlir"))])

    def test_to_dict_roundtrip(self) -> None:
        report = mlir_eqsat.MlirEqsatReport(status="optimized", pipeline="p", details="d")
        self.assertEqual(
            report.to_dict(), {"status": "optimized", "pipeline": "p", "details": "d"}
        )


class RealFilesystemSkipsTests(unittest.TestCase):
    """Smoke: the skip path works against the real host (no mocks)."""

    def test_alive2_and_mlir_skip_or_run_honestly_on_this_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.ll").write_text("define void @f() {}", encoding="utf-8")
            (root / "b.ll").write_text("define void @f() {}", encoding="utf-8")
            report = llvm_alive2.verify_translation(root / "a.ll", root / "b.ll")
            self.assertIn(report.status, {"skipped", "verified", "refuted", "error"})
            if not llvm_alive2.alive2_available():
                self.assertEqual(report.status, "skipped")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
