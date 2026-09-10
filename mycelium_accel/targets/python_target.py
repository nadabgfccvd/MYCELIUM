"""Python project target with sensible defaults + BENCHMARK_SPEC compatibility."""
from __future__ import annotations

import sys
from pathlib import Path

from .base import ProjectTarget, TargetManifest


class PythonTarget(ProjectTarget):
    """Python project driven by commands; understands repo conventions."""

    @classmethod
    def default_manifest(cls, root: Path) -> TargetManifest:
        python = Path(sys.executable).name or "python3"
        manifest = TargetManifest(name=root.name or "python-target", kind="python", metrics_parser="time")
        if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
            manifest.prepare_command = None  # keep offline-safe: no implicit pip install
        if (root / "tests").is_dir():
            manifest.test_command = f"{python} -m pytest -q"
        if (root / "benchmark.py").exists():
            manifest.benchmark_command = f"{python} benchmark.py"
        return manifest
