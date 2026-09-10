"""Bounded translation validation for LLVM IR via Alive2 (when available).

Alive2 performs automatic SMT-backed translation validation of LLVM IR
pairs. This adapter is a *thin, honest wrapper*: if ``alive-tv`` is not
installed the adapter reports ``skipped`` — it never fabricates a proof.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Alive2Report:
    status: str  # "verified" | "refuted" | "skipped" | "error"
    tool: str = "alive-tv"
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def alive2_available() -> bool:
    return shutil.which("alive-tv") is not None


def verify_translation(src_ir: Path, opt_ir: Path, *, timeout_seconds: float = 60.0) -> Alive2Report:
    """Run bounded translation validation between two LLVM IR files."""
    if not alive2_available():
        return Alive2Report(status="skipped", details="alive-tv not installed on this host.")
    try:
        completed = subprocess.run(
            ["alive-tv", str(src_ir), str(opt_ir)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return Alive2Report(status="error", details="alive-tv timed out.")
    output = (completed.stdout + "\n" + completed.stderr).strip()
    if "0 incorrect transformations" in output and completed.returncode == 0:
        return Alive2Report(status="verified", details=output[-800:])
    if completed.returncode != 0 or "incorrect" in output.lower():
        return Alive2Report(status="refuted", details=output[-800:])
    return Alive2Report(status="error", details=output[-800:])
