"""Generic command-driven target: any project driven purely by commands."""
from __future__ import annotations

from pathlib import Path

from .base import ProjectTarget, TargetManifest


class ShellTarget(ProjectTarget):
    """Project that is fully described by its manifest commands."""

    @classmethod
    def default_manifest(cls, root: Path) -> TargetManifest:
        return TargetManifest(name=root.name or "shell-target", kind="shell")
