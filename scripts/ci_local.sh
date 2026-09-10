#!/usr/bin/env bash
# Roadmap F2 — plano B sem GitHub: mesmos passos do CI, localmente.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 1/3 install ==="
pip install -e . -q 2>&1 | tail -n 2 || pip install .

echo "=== 2/3 tests ==="
if command -v pytest > /dev/null; then
  pytest -q
else
  python -m unittest discover -s tests
fi

echo "=== 3/3 smoke ==="
RM_DIR=$(mktemp -d)/smoke_state
python -m mycelium_accel run --seed 101 --state-dir "$RM_DIR" --rounds 5
python -m mycelium_accel growth-regime --state-dir "$RM_DIR" > /dev/null
echo "CI LOCAL VERDE"
