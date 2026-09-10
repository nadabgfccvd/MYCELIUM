from __future__ import annotations

from pathlib import Path

from .audit import load_payload, save_payload
from .model import EngineState


STATE_FILENAME = {"json": "state.json", "pickle": "state.pkl"}
KILL_FILENAME = "KILL"


def state_file(state_dir: Path, backend: str = "json") -> Path:
    if backend == "auto":
        for candidate_backend in ("pickle", "json"):
            candidate = state_dir / STATE_FILENAME[candidate_backend]
            if candidate.exists():
                return candidate
        return state_dir / STATE_FILENAME["json"]
    if backend not in STATE_FILENAME:
        raise ValueError(f"Unsupported state backend: {backend}")
    return state_dir / STATE_FILENAME[backend]


def state_backend_for_path(path: Path) -> str:
    if path.suffix == ".pkl":
        return "pickle"
    return "json"


def kill_switch_file(state_dir: Path) -> Path:
    return state_dir / KILL_FILENAME


def save_state(state_dir: Path, state: EngineState, backend: str = "json") -> Path:
    path = state_file(state_dir, backend)
    save_payload(path, state.to_compact(), backend)
    return path


def load_state(state_dir: Path, backend: str = "auto") -> EngineState:
    path = state_file(state_dir, backend)
    if backend != "auto" and not path.exists():
        path = state_file(state_dir, "auto")
    resolved_backend = state_backend_for_path(path)
    return EngineState.from_dict(load_payload(path, resolved_backend))
