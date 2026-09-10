"""MLIR equality-saturation / transform-dialect orchestration (when available).

Dialect-agnostic global rewriting (DialEgg/egglog-style) and fine-grained
pipeline control (MLIR transform dialect) require an MLIR toolchain. As with
the Alive2 adapter, this wrapper is honest: no toolchain → ``skipped``.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MlirEqsatReport:
    status: str  # "optimized" | "skipped" | "error"
    pipeline: str = ""
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def mlir_opt_available() -> bool:
    return shutil.which("mlir-opt") is not None


def run_transform_pipeline(
    input_mlir: Path,
    output_mlir: Path,
    *,
    transform_script: Path | None = None,
    passes: str = "",
    timeout_seconds: float = 120.0,
) -> MlirEqsatReport:
    """Drive mlir-opt with a transform-dialect script (or explicit passes)."""
    if not mlir_opt_available():
        return MlirEqsatReport(status="skipped", details="mlir-opt not installed on this host.")
    command = ["mlir-opt", str(input_mlir)]
    if transform_script is not None:
        command += [f"--transform-script={transform_script}"]
    if passes:
        command += [f"--pass-pipeline={passes}"]
    command += ["-o", str(output_mlir)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return MlirEqsatReport(status="error", details="mlir-opt timed out.")
    if completed.returncode != 0:
        return MlirEqsatReport(status="error", details=completed.stderr[-800:])
    return MlirEqsatReport(status="optimized", pipeline=passes or "transform-script", details=completed.stderr[-400:])
