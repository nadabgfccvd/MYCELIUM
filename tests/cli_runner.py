"""V1.3: in-process CLI runner — same argv parsing + exit codes, no spawn.

Drop-in for ``subprocess.run([sys.executable, "-m", "mycelium_accel", ...])``
in tests that don't need process isolation (~30-100 ms saved per call).
True-subprocess anchors stay in: test_quickstart, test_examples,
test_provenance (cwd-relative), test_racing (via API), test_ui_smoke (server).
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch


def cli(*argv: str, input: str | None = None) -> Any:
    """Run the CLI in-process; returns (returncode, stdout, stderr)."""
    from mycelium_accel.__main__ import main

    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with patch("sys.argv", ["mycelium-accel", *argv]):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                if input is not None:
                    with patch("sys.stdin", io.StringIO(input)):
                        main()
                else:
                    main()
            except SystemExit as exc:
                if isinstance(exc.code, int):
                    code = exc.code
                else:
                    # interpreter behavior: SystemExit("msg") prints msg to stderr, exits 1
                    code = 1
                    if exc.code is not None:
                        print(exc.code, file=stderr)
    return SimpleNamespace(returncode=code, stdout=stdout.getvalue(), stderr=stderr.getvalue())
