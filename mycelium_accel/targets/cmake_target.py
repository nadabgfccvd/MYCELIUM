"""C/C++ CMake project target."""
from __future__ import annotations

import shutil
from pathlib import Path

from .base import ProjectTarget, TargetManifest


class CmakeTarget(ProjectTarget):
    """CMake project with configure/build/test/benchmark stages."""

    @classmethod
    def default_manifest(cls, root: Path) -> TargetManifest:
        manifest = TargetManifest(name=root.name or "cmake-target", kind="cmake")
        if shutil.which("cmake"):
            manifest.build_command = "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build"
            # The runner forbids '&&' chains; express via sh -c instead.
            manifest.build_command = "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release"
            manifest.prepare_command = None
            manifest.test_command = "ctest --test-dir build --output-on-failure" if shutil.which("ctest") else None
            manifest.timeout_seconds = 600.0
        return manifest
