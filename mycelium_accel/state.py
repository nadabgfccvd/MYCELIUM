from __future__ import annotations

import pickle
from pathlib import Path

from .audit import load_payload, save_payload
from .model import EngineState


STATE_FILENAME = {"json": "state.json", "pickle": "state.pkl"}
KILL_FILENAME = "KILL"


class StateCorruptError(RuntimeError):
    """State or checkpoint file is corrupt, truncated, or not loadable.

    Ciclo 4 (R): raised at the load point (never a raw json/pickle
    traceback at the CLI); carries the file path and the underlying cause.
    """


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


# Decode failures that mean "the bytes on disk are unusable" (json.JSONDecodeError
# is a ValueError; truncated pickles raise UnpicklingError/EOFError).
_DECODE_ERRORS = (ValueError, pickle.UnpicklingError, EOFError)
# Structural failures that mean "the payload decoded but is not a state".
_SHAPE_ERRORS = (KeyError, TypeError, AttributeError)


def load_state(state_dir: Path, backend: str = "auto") -> EngineState:
    path = state_file(state_dir, backend)
    if backend != "auto" and not path.exists():
        path = state_file(state_dir, "auto")
    resolved_backend = state_backend_for_path(path)
    try:
        payload = load_payload(path, resolved_backend)
    except _DECODE_ERRORS as exc:
        raise StateCorruptError(
            f"state file {path} is corrupt or truncated ({type(exc).__name__}: {exc})"
        ) from exc
    try:
        return EngineState.from_dict(payload)
    except _SHAPE_ERRORS as exc:
        raise StateCorruptError(
            f"state file {path} has invalid content ({type(exc).__name__}: {exc})"
        ) from exc


def load_checkpoint_payload(path: Path) -> dict:
    """Load a checkpoint payload, mapping decode/shape failures to StateCorruptError."""
    backend = state_backend_for_path(path)
    try:
        payload = load_payload(path, backend)
    except _DECODE_ERRORS as exc:
        raise StateCorruptError(
            f"checkpoint {path} is corrupt or truncated ({type(exc).__name__}: {exc})"
        ) from exc
    if not isinstance(payload, dict):
        raise StateCorruptError(f"checkpoint {path} has invalid content (not a mapping)")
    return payload
