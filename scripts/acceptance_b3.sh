#!/usr/bin/env bash
# B3: simula um terceiro — 5 comandos até um relatório completo, sem editar nada.
#   1. doctor        2. accelerate init   3. accelerate (mede)   4. run (engine)   5. growth-regime
set -euo pipefail
cd "$(dirname "$0")/.."

DEMO=$(mktemp -d)/third-party
mkdir -p "$DEMO"
cp examples/python-manifest/benchmark.py "$DEMO/benchmark.py"

echo "=== [1/5] doctor ==="
python -m mycelium_accel doctor

echo "=== [2/5] accelerate init ==="
python -m mycelium_accel accelerate init --target "$DEMO"

echo "=== [3/5] accelerate (mede fast vs slow) ==="
python -m mycelium_accel accelerate --target "$DEMO" --seeds 101,103,107 --no-apply | tail -n 12

echo "=== [4/5] engine run ==="
python -m mycelium_accel run --seed 101 --state-dir "$DEMO/state" --rounds 5

echo "=== [5/5] growth-regime ==="
python -m mycelium_accel growth-regime --state-dir "$DEMO/state" --markdown | head -n 15

echo "ACCEPTANCE B3 VERDE — terceiro chegou a relatórios em 5 comandos"
