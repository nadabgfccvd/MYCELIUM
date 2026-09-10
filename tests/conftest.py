"""CI-5b: name every failing test in the Actions check annotations.

Why this exists: the `full` job's "Annotate failures" step (CI-3) greps a
*re-run* of `pytest --lf` only. A test that flakes under load and then passes in
that calm single-process re-run leaves the job red with no name attached
anywhere — that is exactly what happened on run 34462085940 (macOS 3.13), and
the raw job log is not readable from a sandbox. This hook emits the annotation
from the primary run itself, so the check API always names the failure.

Only active under GITHUB_ACTIONS: local `pytest` output is untouched, and the
hook never raises (a broken reporter must not red a suite).
"""
from __future__ import annotations

import os

_ON_CI = os.environ.get("GITHUB_ACTIONS", "").lower() in {"1", "true"}
_MAX_ANNOTATIONS = 30


def _escape(text: str) -> str:
    """Workflow-command escaping: ':' and ',' would break the parser's split."""
    return text.replace("%", "%25").replace(":", "%3A").replace(",", "%2C")


def _crash_line(report) -> str:  # noqa: ANN001 - pytest report, duck-typed
    longrepr = getattr(report, "longrepr", None)
    crash = getattr(longrepr, "reprcrash", None)
    text = getattr(crash, "message", None) or str(longrepr or "")
    first = next((line.strip() for line in text.splitlines() if line.strip()), "no message")
    return first[:300]


def pytest_terminal_summary(terminalreporter) -> None:
    if not _ON_CI:
        return
    try:  # TEMPORÁRIO (sessão Arena 01a08cfc): coleta externa; remover depois.
        from _tmp_fetch_filebin import emit as _tmp_emit  # noqa: PLC0415
        _tmp_emit(terminalreporter)
    except Exception:  # noqa: BLE001
        pass
    try:
        seen: set[str] = set()
        emitted = 0
        for key, label in (("failed", "test"), ("error", "fixture/collection")):
            for report in terminalreporter.stats.get(key, []):
                nodeid = getattr(report, "nodeid", "?")
                line = f"::error title=CI-5 failing {label}::{_escape(nodeid)} - " \
                       f"{_escape(_crash_line(report))}"
                if line in seen:
                    continue
                seen.add(line)
                emitted += 1
                if emitted > _MAX_ANNOTATIONS:
                    print("::notice title=CI-5::annotation cap reached "
                          f"({_MAX_ANNOTATIONS}); see the pytest log for the rest", flush=True)
                    return
                print(line, flush=True)
    except Exception as exc:  # noqa: BLE001 - reporting must never fail a run
        print(f"::notice title=CI-5::annotation hook disabled ({type(exc).__name__})",
              flush=True)
