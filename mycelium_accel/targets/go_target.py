"""Go project target (C6)."""
from __future__ import annotations

import shutil
from pathlib import Path

from .base import ProjectTarget, TargetManifest

# First `1234 ns/op` number wins: scaffolds with several Benchmark* funcs
# measure the first one until the user narrows `-bench` (documented, not magic).
GO_BENCH_PARSER = r"regex:(?P<ns_per_op>[0-9]+)\s+ns/op"


class GoTarget(ProjectTarget):
    """Go module; variants typically inject GOFLAGS/GOMAXPROCS/GOGC via env."""

    @classmethod
    def default_manifest(cls, root: Path) -> TargetManifest:
        manifest = TargetManifest(
            name=root.name or "go-target",
            kind="go",
            metric_name="ns_per_op",
            metrics_parser=GO_BENCH_PARSER,
        )
        if shutil.which("go"):
            manifest.build_command = "go build ./..."
            if list(root.glob("*_test.go")):
                manifest.test_command = "go test ./..."
                # -run XXX skips unit tests; -benchtime 100x keeps the scaffold
                # fast and fixed-cost (real runs tune this up via --wizard).
                manifest.benchmark_command = "go test -run XXX -bench . -benchtime 100x ."
            manifest.timeout_seconds = 600.0
        return manifest
