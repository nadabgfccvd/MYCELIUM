"""Project-agnostic target harness primitives (Roadmap Phase 1).

A *target* is any directory with a ``mycelium.target.json`` manifest that
declares how to prepare/build/test/benchmark it and which variants exist.
This is the "caixa-preta reprodutível" layer: MYCELIUM Auto-evolve can measure and
compare arbitrary projects as black boxes before any language-aware
rewriting exists.

Safety properties (per the project constraints):

* every command runs confined to the target directory, with a timeout;
* only allowlisted executables may be invoked (shell=False, shlex-split);
* file-modifying variants are snapshotted first and rolled back on failure;
* a kill file (``KILL``) in the state dir aborts long benchmark sweeps.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Sequence

MANIFEST_FILENAME = "mycelium.target.json"

DEFAULT_EXECUTABLE_ALLOWLIST = {
    "python", "python3", "pip", "pip3",
    "cargo", "rustc", "rustup",
    "go",  # C6: `go build/test` drive Go targets (same trust as cargo)
    "cmake", "make", "ninja", "ctest",
    "cc", "c++", "gcc", "g++", "clang", "clang++",
    "node", "npm", "npx", "yarn", "pnpm",
    "sh", "bash", "env", "echo", "true",
    "git", "tar", "patch",
}

def canonical_executable(name: str) -> str:
    """Trust mapping: versioned CPython (python3.13, ...) == python3.

    Auto-detection emits sys.executable's basename, so manifests must stay valid
    under any CPython 3.x. Same interpreter family the user already allowlisted.
    """
    import re as _re

    # Windows: auto-detection emits sys.executable's basename ("python.exe").
    # Strip the platform suffix so it maps like posix "python". Allowlist
    # membership is still required after normalization.
    stem = name[:-4] if name.lower().endswith(".exe") else name
    return "python3" if _re.fullmatch(r"python3\.\d+t?", stem) else stem


ENV_PASSTHROUGH = {
    "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
    "CARGO_HOME", "RUSTUP_HOME", "NODE_ENV", "VIRTUAL_ENV",
    "CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "MAKEFLAGS",
}


class TargetSafetyError(RuntimeError):
    """Raised when a manifest command violates the sandbox policy."""


@dataclass(slots=True)
class Variant:
    """One named variant of a target.

    Modes
    -----
    env    : only set ``env`` variables (plus optional ``args``).
    args   : append ``args`` to the benchmark command.
    patch  : copy files from ``files`` ({relative_path: absolute_or_manifest_relative_source})
             into the target before running; originals are restored after.
    script : run ``apply_command`` before and (optional) ``revert_command``
             after measurement. Snapshotted artifact paths are restored.
    profile: like env, but also sets the seed env var for reproducibility.
    """

    name: str
    mode: str = "env"
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    apply_command: str | None = None
    revert_command: str | None = None
    description: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Variant:
        if not isinstance(payload, dict):  # Q1.3: friendly, never AttributeError
            raise ValueError(
                f"Variant must be a JSON object, got {type(payload).__name__}."
            )
        for key in ("env", "files"):  # Q1.3: .items() on non-dict crashed
            if key in payload and not isinstance(payload[key], dict):
                raise ValueError(f"Variant {key!r} must be a JSON object.")
        mode = str(payload.get("mode", "env"))
        if mode not in {"env", "args", "patch", "script", "profile"}:
            raise ValueError(f"Unsupported variant mode: {mode}")
        return cls(
            name=str(payload["name"]),
            mode=mode,
            env={str(k): str(v) for k, v in payload.get("env", {}).items()},
            args=[str(a) for a in payload.get("args", [])],
            files={str(k): str(v) for k, v in payload.get("files", {}).items()},
            apply_command=payload.get("apply_command"),
            revert_command=payload.get("revert_command"),
            description=str(payload.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TargetManifest:
    """Declarative description of how to drive an arbitrary project."""

    name: str = ""
    kind: str = "shell"  # shell | python | cargo | cmake | node | go
    prepare_command: str | None = None
    build_command: str | None = None
    test_command: str | None = None
    benchmark_command: str | None = None
    clean_command: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    seed_env_var: str = "MYCELIUM_SEED"
    metrics_parser: str = "time"  # time | json_stdout | regex:<pattern>
    metric_name: str = "seconds"
    lower_is_better: bool = True
    variants: list[Variant] = field(default_factory=list)
    variant_application_mode: str = "env"
    warmup: int = 1
    repeats: int = 5
    timeout_seconds: float = 120.0
    executable_allowlist: list[str] = field(default_factory=lambda: sorted(DEFAULT_EXECUTABLE_ALLOWLIST))
    manifest_version: str = "1.0"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TargetManifest:
        if not isinstance(payload, dict):
            raise ValueError(
                f"Manifest must be a JSON object, got {type(payload).__name__}. "
                "See docs/API_STABLE_1.0.md."
            )
        known = {
            "name", "kind", "prepare_command", "build_command", "test_command",
            "benchmark_command", "clean_command", "artifact_paths", "seed_env_var",
            "metrics_parser", "metric_name", "lower_is_better", "variants",
            "variant_application_mode", "warmup", "repeats", "timeout_seconds",
            "executable_allowlist", "manifest_version",
        }
        unknown = set(payload) - known
        if unknown:
            raise ValueError(
                f"Unknown manifest keys: {sorted(unknown)}. "
                f"Known keys: {sorted(known)}. See docs/API_STABLE_1.0.md."
            )
        version = str(payload.get("manifest_version", "1.0"))
        if version != "1.0":
            raise ValueError(
                f"Unsupported manifest_version {version!r} (this mycelium-accel reads 1.0). "
                "See docs/API_STABLE_1.0.md."
            )
        variants = [Variant.from_dict(item) for item in payload.get("variants", [])]
        return cls(
            name=str(payload.get("name", "")),
            kind=str(payload.get("kind", "shell")),
            prepare_command=payload.get("prepare_command"),
            build_command=payload.get("build_command"),
            test_command=payload.get("test_command"),
            benchmark_command=payload.get("benchmark_command"),
            clean_command=payload.get("clean_command"),
            artifact_paths=[str(p) for p in payload.get("artifact_paths", [])],
            seed_env_var=str(payload.get("seed_env_var", "MYCELIUM_SEED")),
            metrics_parser=str(payload.get("metrics_parser", "time")),
            metric_name=str(payload.get("metric_name", "seconds")),
            lower_is_better=bool(payload.get("lower_is_better", True)),
            variants=variants,
            variant_application_mode=str(payload.get("variant_application_mode", "env")),
            warmup=int(payload.get("warmup", 1)),
            repeats=int(payload.get("repeats", 5)),
            timeout_seconds=float(payload.get("timeout_seconds", 120.0)),
            executable_allowlist=[str(e) for e in payload.get("executable_allowlist", sorted(DEFAULT_EXECUTABLE_ALLOWLIST))],
            manifest_version=str(payload.get("manifest_version", "1.0")),
        )

    def validate(self) -> list[str]:  # noqa: C901 — Q3.2: per-field check chain.
        """Friendly, early errors (v1 API). Empty list = valid."""
        import shlex as _shlex

        errors: list[str] = []
        allow = set(self.executable_allowlist)
        for field_name in ("prepare_command", "build_command", "test_command",
                           "benchmark_command", "clean_command"):
            cmd = getattr(self, field_name)
            if not cmd:
                continue
            try:
                argv = _shlex.split(cmd)
            except ValueError as exc:
                errors.append(f"{field_name}: cannot parse ({exc})")
                continue
            if not argv:
                errors.append(f"{field_name}: empty command")
            elif canonical_executable(argv[0].split("/")[-1]) not in allow:
                errors.append(
                    f"{field_name}: executable {argv[0]!r} is not allowlisted "
                    "(runs would fail at sandbox time; fix the manifest now — "
                    "either use an allowlisted tool or add it to "
                    "'executable_allowlist' in mycelium.target.json)"
                )
        for variant in self.variants:
            for field_name in ("apply_command", "revert_command"):
                cmd = getattr(variant, field_name)
                if not cmd:
                    continue
                first = cmd.strip().split()[0].split("/")[-1] if cmd.strip() else ""
                if canonical_executable(first) not in allow:
                    errors.append(f"variant {variant.name!r} {field_name}: {first!r} not allowlisted")
        if self.repeats < 1:
            errors.append(f"repeats must be >= 1 (got {self.repeats})")
        if self.warmup < 0:
            errors.append(f"warmup must be >= 0 (got {self.warmup})")
        return errors

    @classmethod
    def load(cls, path: Path) -> TargetManifest:
        manifest_path = path if path.is_file() else path / MANIFEST_FILENAME
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = cls.from_dict(payload)
        errors = manifest.validate()
        if errors:
            raise ValueError(
                "Invalid mycelium.target.json (" + str(manifest_path) + "):\n  - "
                + "\n  - ".join(errors)
            )
        return manifest

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["variants"] = [variant.to_dict() for variant in self.variants]
        return payload


@dataclass(slots=True)
class TargetRunResult:
    command: list[str]
    returncode: int
    seconds: float
    stdout_tail: str
    stderr_tail: str
    metrics: dict[str, float] = field(default_factory=dict)
    seed: int | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CommandRunner:
    """Confined, allowlisted, timed command execution."""

    TAIL_LIMIT = 4096

    def __init__(
        self,
        root: Path,
        *,
        allowlist: Sequence[str] | None = None,
        timeout_seconds: float = 120.0,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.allowlist = set(allowlist or DEFAULT_EXECUTABLE_ALLOWLIST)
        self.timeout_seconds = timeout_seconds
        self.extra_env = dict(extra_env or {})

    def _check_command(self, argv: list[str]) -> None:
        if not argv:
            raise TargetSafetyError("Empty command is not allowed.")
        executable = os.path.basename(argv[0])
        if canonical_executable(executable) not in self.allowlist:
            raise TargetSafetyError(
                f"Executable '{executable}' is not in the allowlist for this target."
            )
        for token in argv[1:]:
            if token.startswith("/") and not token.startswith(str(self.root)):
                # Absolute paths outside the sandbox root are rejected unless
                # they point to interpreter/toolchain files handled above.
                if not token.startswith(("/usr/", "/bin/", "/opt/", "/tmp/")):
                    raise TargetSafetyError(f"Suspicious absolute path in command: {token}")

    def build_env(self, overrides: dict[str, str] | None = None) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items() if key in ENV_PASSTHROUGH}
        env.update(self.extra_env)
        if overrides:
            env.update({str(k): str(v) for k, v in overrides.items()})
        return env

    def run(
        self,
        command: str,
        *,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> TargetRunResult:
        argv = shlex.split(command)
        self._check_command(argv)
        merged_env: dict[str, str] = dict(env) if env else self.build_env()
        if seed is not None:
            merged_env = {**merged_env, "MYCELIUM_SEED": str(seed)}
        started = time.perf_counter()
        # Q2.1: Popen (not run) so Ctrl-C/timeout can kill the whole process
        # group — children start a new session and would otherwise outlive us.
        proc = subprocess.Popen(
            argv,
            cwd=self.root,
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout or self.timeout_seconds)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            proc.communicate()  # reap
            elapsed = time.perf_counter() - started
            return TargetRunResult(
                command=argv,
                returncode=-signal.SIGKILL,
                seconds=elapsed,
                stdout_tail="",
                stderr_tail=f"TIMEOUT after {elapsed:.1f}s",
                seed=seed,
            )
        except KeyboardInterrupt:
            _kill_tree(proc)
            proc.wait()
            raise
        elapsed = time.perf_counter() - started
        return TargetRunResult(
            command=argv,
            returncode=proc.returncode,
            seconds=elapsed,
            stdout_tail=stdout[-self.TAIL_LIMIT:],
            stderr_tail=stderr[-self.TAIL_LIMIT:],
            seed=seed,
        )


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """Best-effort kill of a spawned benchmark and its children (Q2.1)."""
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:  # Windows has no process groups here; kill the direct child
            proc.kill()
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


class FileSnapshot:
    """Snapshot/rollback helper for file-modifying variants."""

    def __init__(self, root: Path, paths: Sequence[str]) -> None:
        self.root = root
        self._backup_dir: Path | None = None
        self._paths: list[str] = [str(p) for p in paths]

    def __enter__(self) -> FileSnapshot:
        backup_root = Path(os.environ.get("TMPDIR", "/tmp"))
        self._backup_dir = backup_root / f"mycelium-snapshot-{os.getpid()}-{time.time_ns()}"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        for rel in self._paths:
            source = self.root / rel
            if not source.exists():
                continue
            dest = self._backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
        return self

    def restore(self) -> None:
        if self._backup_dir is None:
            return
        for rel in self._paths:
            backup = self._backup_dir / rel
            target = self.root / rel
            if backup.exists():
                if target.exists():
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if backup.is_dir():
                    shutil.copytree(backup, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.restore()
        if self._backup_dir is not None:
            shutil.rmtree(self._backup_dir, ignore_errors=True)
            self._backup_dir = None


class ProjectTarget:
    """Black-box driver for a project directory described by a manifest."""

    def __init__(self, root: Path, manifest: TargetManifest) -> None:
        self.root = root.resolve()
        self.manifest = manifest
        self.runner = CommandRunner(
            self.root,
            allowlist=manifest.executable_allowlist,
            timeout_seconds=manifest.timeout_seconds,
        )

    # -- lifecycle ------------------------------------------------------
    def prepare(self, seed: int) -> TargetRunResult | None:
        if self.manifest.prepare_command:
            return self.runner.run(self.manifest.prepare_command, seed=seed)
        return None

    def build(self) -> TargetRunResult | None:
        if self.manifest.build_command:
            result = self.runner.run(self.manifest.build_command)
            if not result.ok:
                raise RuntimeError(f"Build failed: {result.stderr_tail[-400:]}")
            return result
        return None

    def test(self) -> TargetRunResult | None:
        if self.manifest.test_command:
            return self.runner.run(self.manifest.test_command)
        return None

    def clean(self) -> None:
        if self.manifest.clean_command:
            self.runner.run(self.manifest.clean_command)

    # -- variants --------------------------------------------------------
    def build_env(self) -> dict[str, str]:
        return self.runner.build_env()

    def variant_env(self, variant: Variant, seed: int | None) -> dict[str, str]:
        env = self.runner.build_env(variant.env)
        if seed is not None:
            env[self.manifest.seed_env_var] = str(seed)
        return env

    def apply_variant(self, variant: Variant) -> FileSnapshot:
        """Apply the file-script part of a variant; caller manages the snapshot."""
        touched = list(variant.files) + list(self.manifest.artifact_paths)
        snapshot = FileSnapshot(self.root, touched)
        snapshot.__enter__()
        try:
            if variant.mode == "patch":
                for rel_path, source_path in variant.files.items():
                    src = Path(source_path)
                    if not src.is_absolute():
                        src = self.root / src
                    dest = self.root / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
            if variant.apply_command:
                result = self.runner.run(variant.apply_command)
                if not result.ok:
                    raise RuntimeError(
                        f"Variant '{variant.name}' apply failed: {result.stderr_tail[-400:]}"
                    )
        except Exception:
            snapshot.__exit__(None, None, None)
            raise
        return snapshot

    def revert_variant(self, snapshot: FileSnapshot, variant: Variant) -> None:
        try:
            if variant.revert_command:
                self.runner.run(variant.revert_command)
        finally:
            snapshot.__exit__(None, None, None)
