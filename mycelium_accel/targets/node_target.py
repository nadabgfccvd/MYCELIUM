"""Node.js project target."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import ProjectTarget, TargetManifest


class NodeTarget(ProjectTarget):
    """Node project driven by package.json scripts."""

    @classmethod
    def default_manifest(cls, root: Path) -> TargetManifest:
        manifest = TargetManifest(name=root.name or "node-target", kind="node")
        package_json = root / "package.json"
        if not package_json.exists() or not shutil.which("npm"):
            return manifest
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}
        if "build" in scripts:
            manifest.build_command = "npm run build"
        if "test" in scripts:
            manifest.test_command = "npm test --silent"
        for bench_name in ("bench", "benchmark"):
            if bench_name in scripts:
                manifest.benchmark_command = f"npm run {bench_name}"
                break
        manifest.timeout_seconds = 300.0
        return manifest
