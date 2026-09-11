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


PLACEHOLDER = "INSIRA-ORGAO"


def publish_readiness(root: Path) -> list[str]:
    """Pre-upload gates that the normal version check does not enforce.

    A wheel whose project URLs / badges still point at the ``INSIRA-ORGAO``
    placeholder would publish broken repository links to PyPI. The project is
    not pushed to a real org yet, so this stays an *opt-in* strict check
    (``--strict-publish``) rather than blocking local tagging. It also
    confirms the PEP 561 typing marker will ship in the wheel.
    """
    errors: list[str] = []
    pyproject = root / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read pyproject.toml: {exc}"]
    if PLACEHOLDER in text:
        errors.append(
            f"pyproject.toml still has the {PLACEHOLDER!r} repository slug — "
            "set a real Homepage/Repository/Issues URL before uploading to PyPI"
        )
    for doc in ("README.md", "mkdocs.yml", "CITATION.cff"):
        path = root / doc
        if path.exists() and PLACEHOLDER in path.read_text(encoding="utf-8"):
            errors.append(f"{doc} still has the {PLACEHOLDER!r} repository slug")
    if not (root / "mycelium_accel" / "py.typed").exists():
        errors.append("mycelium_accel/py.typed marker missing (PEP 561 typing not shipped)")
    return errors


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
    args = [a for a in sys.argv[1:] if a != "--strict-publish"]
    strict_publish = "--strict-publish" in sys.argv[1:]
    if len(args) != 1:
        print("usage: release_check.py [--strict-publish] vX.Y.Z", file=sys.stderr)
        return 2
    (tag,) = args
    errors = check(tag, Path.cwd())
    if strict_publish:
        errors += publish_readiness(Path.cwd())
    for error in errors:
        print(f"release.sh: {error}", file=sys.stderr)
    if not errors and strict_publish:
        print("publish readiness OK")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
