"""Durable telemetry (Roadmap Fase F1).

The engine keeps only the last 512 metrics in memory (``metrics_history`` cap).
Long runs (>512 rounds) used to lose history silently. This module provides an
append-only JSONL log — ``<state-dir>/telemetry/metrics.jsonl`` — with one line
per round, plus readers that transparently prefer the durable log when it is
available and fall back to the in-memory history otherwise.

Design rules (project style):
- stdlib only, no threads, no network;
- append is best-effort: telemetry must NEVER break a run;
- readers tolerate partial/corrupt trailing lines (crash-safe tail).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from collections.abc import Sequence
from datetime import UTC


TELEMETRY_DIRNAME = "telemetry"
METRICS_FILENAME = "metrics.jsonl"


def telemetry_path(state_dir: str | Path) -> Path:
    return Path(state_dir) / TELEMETRY_DIRNAME / METRICS_FILENAME


def append_metric(state_dir: str | Path, metric: dict[str, Any]) -> bool:
    """Append one metric dict as a JSON line. Returns True on success.

    Never raises: telemetry failures are silent by design (the run matters
    more than the log). Callers that need a guarantee should check the
    return value.
    """
    try:
        path = telemetry_path(state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metric, default=str) + "\n")
        return True
    except OSError:
        return False


def read_metrics(  # noqa: C901 — Q3.2: metrics-parser dispatch.
    state_dir: str | Path,
    *,
    limit: int | None = None,
    from_round: int | None = None,
) -> list[dict[str, Any]]:
    """Read the durable JSONL log. Skips blank/corrupt lines.

    Args:
        limit: max number of most-recent entries to return (None = all).
        from_round: only return entries with ``round`` >= this value.
    """
    path = telemetry_path(state_dir)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue  # crash-safe tail: ignore partial last line
                if not isinstance(payload, dict):
                    continue
                if from_round is not None:
                    try:
                        if int(payload.get("round", -1)) < from_round:
                            continue
                    except (TypeError, ValueError):
                        continue
                entries.append(payload)
    except OSError:
        return entries
    if limit is not None and limit >= 0:
        entries = entries[-limit:] if limit else []
    return entries


def metrics_count(state_dir: str | Path) -> int:
    """Count durable entries without parsing them fully (fast path)."""
    path = telemetry_path(state_dir)
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def full_history(
    in_memory: Sequence[dict[str, Any]],
    state_dir: str | Path | None,
) -> list[dict[str, Any]]:
    """Best available history: durable JSONL wins when it covers more rounds.

    Falls back to ``in_memory`` when the log is missing/empty/shorter (e.g.
    fresh state dirs, legacy states, unit tests). Never raises.
    """
    memory = list(in_memory)
    if state_dir is None:
        return memory
    try:
        durable = read_metrics(state_dir)
    except Exception:  # noqa: BLE001 - telemetry must never break readers
        return memory
    if len(durable) >= len(memory):
        return durable
    return memory


# -- provenance (Fase 1.1): ambient artifacts must say where they came from --

def stamp_provenance(
    payload: dict[str, Any],
    producer: str,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Attach a ``provenance`` block (producer + origin + timestamp). Mutates."""
    from datetime import datetime

    payload["provenance"] = {
        "producer": producer,
        "state_dir": str(state_dir) if state_dir is not None else None,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "package": "mycelium-accel",
    }
    return payload


def check_provenance(
    payload: dict[str, Any] | None,
    expected_state_dir: str | Path | None,
) -> tuple[bool, str]:
    """(ok, reason) — ok=False when the artifact should not be trusted blindly.

    Reasons: ``missing`` (legacy, unstamped), ``foreign`` (stamped for another
    state-dir), ``ok``.
    """
    if not payload:
        return True, "empty"
    prov = payload.get("provenance")
    if not isinstance(prov, dict):
        return False, "missing (legacy artifact without provenance)"
    origin = prov.get("state_dir")
    if origin is None:
        return True, "ok (synthetic, no state-dir)"
    if expected_state_dir is None:
        return True, "ok (no expected origin)"
    if str(Path(origin)) != str(Path(str(expected_state_dir))):
        return False, f"foreign (from {origin}, current is {expected_state_dir})"
    return True, "ok"
