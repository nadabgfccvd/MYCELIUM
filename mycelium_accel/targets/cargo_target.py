"""Rust/Cargo project target."""
from __future__ import annotations

import shutil
from pathlib import Path

from .base import ProjectTarget, TargetManifest


class CargoTarget(ProjectTarget):
    """Cargo project; variants typically inject RUSTFLAGS / profiles / features."""

    @classmethod
    def default_manifest(cls, root: Path) -> TargetManifest:
        manifest = TargetManifest(name=root.name or "cargo-target", kind="cargo")
        if shutil.which("cargo"):
            manifest.build_command = "cargo build --release"
            manifest.test_command = "cargo test --release"
            if (root / "benches").is_dir():
                manifest.benchmark_command = "cargo bench"
            manifest.clean_command = None  # do not nuke target/ implicitly
            manifest.timeout_seconds = 600.0
        return manifest
