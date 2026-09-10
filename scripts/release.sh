#!/usr/bin/env bash
# V3.1: one-command release — build + twine + clean-venv verify + tag.
# The version number stays deliberate: pass the TAG explicitly (no auto-bump).
# Usage: scripts/release.sh v1.2.0 [--full]
#   --full also runs scripts/ci_local.sh first (~1 min).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -lt 1 ]]; then
  echo "usage: scripts/release.sh vX.Y.Z [--full]"
  echo "  builds, twine-checks, verifies in a clean venv, then tags."
  echo "  --full: run scripts/ci_local.sh first."
  exit 0
fi
TAG="$1"
FULL="${2:-}"

if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "release.sh: bad TAG '$TAG' (want vX.Y.Z)" >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "release.sh: working tree dirty — commit first" >&2
  exit 1
fi
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "release.sh: tag $TAG already exists" >&2
  exit 1
fi

# Q3.5: versions + CHANGES must agree with the tag before anything builds.
python3 scripts/release_check.py "$TAG" || exit 1

if [[ "$FULL" == "--full" ]]; then
  echo "=== 0/4 full suite ==="
  bash scripts/ci_local.sh
fi

echo "=== 1/4 build ==="
rm -rf dist build
python -m build

echo "=== 2/4 twine ==="
python -m twine check dist/*

echo "=== 3/4 clean-venv verify ==="
VENV=$(mktemp -d)/venv
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q dist/*.whl
"$VENV/bin/mycelium-accel" --version
"$VENV/bin/mycelium-accel" doctor | tail -n 1
"$VENV/bin/mycelium-accel" history --help > /dev/null && echo "history OK"

echo "=== 4/4 tag $TAG ==="
git tag "$TAG"
echo "RELEASED $TAG — next (manual): git push origin main $TAG"
