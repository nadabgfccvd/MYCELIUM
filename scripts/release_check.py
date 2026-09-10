#!/usr/bin/env python3
"""Q3.5: release self-checks — version consistency + CHANGES entry.

Called by ``scripts/release.sh`` before building; unit-tested directly
(tests never tag). Returns the list of errors (empty = shippable).
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def check(tag: str, root: Path) -> list[str]:
    errors: list[str] = []
    version = tag[1:] if tag.startswith("v") else tag
    try:
        py_version = tomllib.loads((root / "pyproject.toml").read_bytes().decode())["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot read pyproject version: {exc}"]
    init_text = (root / "mycelium_accel" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    init_version = match.group(1) if match else "<missing>"
    if py_version != version or init_version != version:
        errors.append(
            f"version mismatch: tag={version} pyproject={py_version} __init__={init_version}"
        )
    try:
        changes = (root / "CHANGES.md").read_text(encoding="utf-8")
    except OSError as exc:
        return errors + [f"cannot read CHANGES.md: {exc}"]
    if version not in changes and tag not in changes:
        errors.append(f"CHANGES.md has no entry for {tag}")
    return errors


def main() -> int:
    (tag,) = sys.argv[1:]
    errors = check(tag, Path.cwd())
    for error in errors:
        print(f"release.sh: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
