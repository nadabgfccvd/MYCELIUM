from __future__ import annotations

import json
import os
import pickle
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from .model import EngineState

PAYLOAD_BACKENDS = {"json", "pickle"}
CHECKPOINT_SUFFIX = {"json": ".json", "pickle": ".pkl"}


class AuditLog:
    def __init__(self, state_dir: Path, checkpoint_backend: str = "json") -> None:
        if checkpoint_backend not in PAYLOAD_BACKENDS:
            raise ValueError(f"Unsupported checkpoint backend: {checkpoint_backend}")
        self.state_dir = state_dir
        self.log_path = state_dir / "audit.log.jsonl"
        self.checkpoint_dir = state_dir / "checkpoints"
        self.checkpoint_backend = checkpoint_backend
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event_type,
            "payload": payload,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), check_circular=False) + "\n")

    def checkpoint(self, state: EngineState) -> Path:
        path = checkpoint_file(self.checkpoint_dir, state.round_index, self.checkpoint_backend)
        save_payload(path, state.to_compact(), self.checkpoint_backend)
        self.append(
            "checkpoint",
            {
                "path": str(path),
                "round": state.round_index,
                "backend": self.checkpoint_backend,
            },
        )
        return path

    def available_checkpoints(self) -> list[Path]:
        return sorted(
            [
                *self.checkpoint_dir.glob("round-*.json"),
                *self.checkpoint_dir.glob("round-*.pkl"),
            ]
        )


def checkpoint_file(checkpoint_dir: Path, round_index: int, backend: str) -> Path:
    if backend not in PAYLOAD_BACKENDS:
        raise ValueError(f"Unsupported checkpoint backend: {backend}")
    return checkpoint_dir / f"round-{round_index:05d}{CHECKPOINT_SUFFIX[backend]}"


def resolve_checkpoint_file(checkpoint_dir: Path, round_index: int) -> Path:
    for backend in ("pickle", "json"):
        candidate = checkpoint_file(checkpoint_dir, round_index, backend)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Checkpoint not found for round {round_index} in {checkpoint_dir}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), check_circular=False)
    os.replace(temp_path, path)


def load_pickle(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected pickle payload in {path}")
    return payload


def save_pickle(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(temp_path, path)


def load_payload(path: Path, backend: str) -> dict[str, Any]:
    if backend == "json":
        return load_json(path)
    if backend == "pickle":
        return load_pickle(path)
    raise ValueError(f"Unsupported backend: {backend}")


def save_payload(path: Path, payload: dict[str, Any], backend: str) -> None:
    if backend == "json":
        save_json(path, payload)
        return
    if backend == "pickle":
        save_pickle(path, payload)
        return
    raise ValueError(f"Unsupported backend: {backend}")
