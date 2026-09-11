"""Project-agnostic target harness: manifests, runners, variant application.

Auto-detection order: explicit manifest > python > cargo > cmake > node > go > shell.
"""
from __future__ import annotations

from pathlib import Path

from .base import (
    DEFAULT_EXECUTABLE_ALLOWLIST,
    MANIFEST_FILENAME,
    CommandRunner,
    FileSnapshot,
    ProjectTarget,
    TargetManifest,
    TargetRunResult,
    TargetSafetyError,
    Variant,
)
from .cargo_target import CargoTarget
from .cmake_target import CmakeTarget
from .go_target import GoTarget
from .node_target import NodeTarget
from .python_target import PythonTarget
from .shell_target import ShellTarget

KIND_TO_TARGET = {
    "shell": ShellTarget,
    "python": PythonTarget,
    "cargo": CargoTarget,
    "cmake": CmakeTarget,
    "go": GoTarget,
    "node": NodeTarget,
}

KIND_TO_DEFAULT_MANIFEST = {
    "shell": ShellTarget.default_manifest,
    "python": PythonTarget.default_manifest,
    "cargo": CargoTarget.default_manifest,
    "cmake": CmakeTarget.default_manifest,
    "go": GoTarget.default_manifest,
    "node": NodeTarget.default_manifest,
}


def detect_kind(root: Path) -> str:
    """Best-effort project kind detection for a directory.

    Preserve the established precedence for polyglot projects while covering
    common lock/config-only roots that have no source file yet.
    """
    if any((root / name).exists() for name in (
        "pyproject.toml", "setup.py", "benchmark.py", "requirements.txt", "uv.lock",
    )):
        return "python"
    if (root / "Cargo.toml").exists():
        return "cargo"
    if (root / "CMakeLists.txt").exists():
        return "cmake"
    if any((root / name).exists() for name in ("package.json", "deno.json", "deno.jsonc")):
        return "node"
    if (root / "go.mod").exists():
        return "go"
    return "shell"


def load_target(root: Path, manifest_path: Path | None = None) -> ProjectTarget:
    """Build the right ProjectTarget for ``root``.

    Manifest priority: explicit ``manifest_path`` > ``root/mycelium.target.json``
    > convention-derived defaults for the detected kind.
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Target directory not found: {root}")
    if manifest_path is not None:
        manifest = TargetManifest.load(manifest_path)
    elif (root / MANIFEST_FILENAME).exists():
        manifest = TargetManifest.load(root)
    else:
        kind = detect_kind(root)
        manifest = KIND_TO_DEFAULT_MANIFEST[kind](root)
    target_cls = KIND_TO_TARGET.get(manifest.kind, ShellTarget)
    return target_cls(root, manifest)


__all__ = [
    "CargoTarget",
    "CmakeTarget",
    "GoTarget",
    "CommandRunner",
    "DEFAULT_EXECUTABLE_ALLOWLIST",
    "FileSnapshot",
    "MANIFEST_FILENAME",
    "NodeTarget",
    "ProjectTarget",
    "PythonTarget",
    "ShellTarget",
    "TargetManifest",
    "TargetRunResult",
    "TargetSafetyError",
    "Variant",
    "detect_kind",
    "load_target",
]
