"""DX: environment check (`mycelium-accel doctor`, Roadmap B3).

Reports PASS/WARN/FAIL per check as JSON or human text. Exit code 0 unless a
FAIL check exists (WARNs never fail — e.g. missing optional toolchains).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class Check:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def run_checks(state_dir: str = ".mycelium_state", target: str | None = None) -> list[Check]:
    checks: list[Check] = []
    if target is not None:
        checks.extend(check_manifest(Path(target)))

    # 1. python version
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 11):
        checks.append(Check("python", "PASS", f"{major}.{minor} (>= 3.11)"))
    else:
        checks.append(Check("python", "FAIL", f"{major}.{minor} < 3.11"))

    # 2. pytest available (test gate)
    try:
        import pytest  # noqa: F401
        checks.append(Check("pytest", "PASS", "importável"))
    except ImportError:
        checks.append(Check("pytest", "WARN", "ausente — fallback: unittest"))

    # 3. compilers / build tools
    for tool in ("gcc", "cc", "cmake", "make", "cargo", "node"):
        found = shutil.which(tool)
        checks.append(Check(f"tool:{tool}", "PASS" if found else "WARN",
                            found or "não encontrado (opcional)"))

    # 4. git (versionamento / tags de release)
    git = shutil.which("git")
    checks.append(Check("git", "PASS" if git else "WARN", git or "não encontrado (opcional)"))

    # 5. state dir writable
    try:
        state_path = Path(state_dir)
        state_path.mkdir(parents=True, exist_ok=True)
        probe = state_path / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(Check("state_dir", "PASS", f"gravável: {state_path}"))
    except OSError as exc:
        checks.append(Check("state_dir", "FAIL", f"sem escrita: {exc}"))

    # 6. formal toolchains (B5 — honestamente opcionais)
    for tool in ("alive-tv", "mlir-opt"):
        found = shutil.which(tool)
        checks.append(Check(f"formal:{tool}", "PASS" if found else "WARN",
                            found or "ausente — validadores reportam skipped"))

    # 7. temp + process spawn (sandbox precisa de subprocesso)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "x").write_text("1", encoding="utf-8")
        checks.append(Check("sandbox_tmp", "PASS", "tmp gravável"))
    except OSError as exc:
        checks.append(Check("sandbox_tmp", "FAIL", str(exc)))

    # 8. package importable under new name
    try:
        import mycelium_accel  # noqa: F401
        checks.append(Check("import", "PASS", "mycelium_accel importável"))
    except ImportError as exc:
        checks.append(Check("import", "FAIL", str(exc)))

    return checks


SAFE_FIXES = ("manifest_version stamp (1.0)", "executable_allowlist sort/dedupe")


def check_manifest(root: Path) -> list[Check]:
    """H1.1: validate mycelium.target.json in a project directory."""
    from .targets.base import MANIFEST_FILENAME, TargetManifest

    path = root / MANIFEST_FILENAME if root.is_dir() else root
    if not path.is_file():
        return [Check("manifest", "FAIL",
                      f"not found: {path} (run: accelerate init --target {root} --yes)")]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [Check("manifest", "FAIL", f"invalid JSON: {exc}")]
    try:
        TargetManifest.load(path)
    except ValueError as exc:
        first = str(exc).splitlines()[1:2]
        return [Check("manifest", "FAIL", first[0].strip("- ") if first else str(exc))]
    if "manifest_version" not in raw:
        return [Check("manifest", "WARN",
                      "valid but missing manifest_version (fix: doctor --target DIR --fix)")]
    return [Check("manifest", "PASS", f"valid v1: {path}")]


def fix_manifest(root: Path) -> list[str]:
    """H1.1: apply only the safe fixes; returns human descriptions."""
    from .targets.base import MANIFEST_FILENAME

    path = root / MANIFEST_FILENAME if root.is_dir() else root
    raw = json.loads(path.read_text(encoding="utf-8"))
    done: list[str] = []
    if "manifest_version" not in raw:
        raw["manifest_version"] = "1.0"
        done.append("stamped manifest_version=1.0")
    allow = raw.get("executable_allowlist")
    if isinstance(allow, list) and allow != sorted(set(allow)):
        raw["executable_allowlist"] = sorted(set(allow))
        done.append("sorted/deduped executable_allowlist")
    if done:
        from .sweep_cache import _atomic_write_text  # C4: crash-safe fix

        _atomic_write_text(path, json.dumps(raw, indent=2, sort_keys=True))
    return done


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="check mycelium-accel environment")
    parser.add_argument("--state-dir", default=".mycelium_state")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--target", default=None)
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args(argv)

    fixed: list[str] = []
    if args.fix:
        if not args.target:
            print("mycelium-accel: --fix needs --target DIR", file=sys.stderr)
            return 2
        try:
            fixed = fix_manifest(Path(args.target))
        except (ValueError, OSError) as exc:
            print(f"mycelium-accel: cannot fix manifest: {exc}", file=sys.stderr)
            return 1
        for item in fixed:
            print(f"fixed: {item}")
        if not fixed:
            print("fixed: nothing to do (manifest already clean)")

    checks = run_checks(args.state_dir, args.target)
    failed = [c for c in checks if c.status == "FAIL"]
    if args.json:
        print(json.dumps({"checks": [c.to_dict() for c in checks],
                          "ok": not failed}, indent=2))
    else:
        for check in checks:
            print(f"[{check.status:4s}] {check.name:16s} {check.detail}")
        print("DOCTOR OK" if not failed else "DOCTOR FALHOU")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
