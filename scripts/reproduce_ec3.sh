#!/usr/bin/env bash
# EC3 (Fase 2): harness contra more-itertools real (pinado), variante len() em ilen().
# Requer rede (clone) + pytest. O PR é aberto manualmente com o pack em docs/EC3_PR_PACK.md.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

PIN="19ddb972845ab0e5b9b7449d3fd5930781407441"
TARGET="${EC3_TARGET:-/tmp/ec3mi}"

if [ ! -d "$TARGET/.git" ]; then
  git clone https://github.com/more-itertools/more-itertools.git "$TARGET"
fi
cd "$TARGET"
git fetch -q origin "$PIN" 2>/dev/null || true
git checkout -q "$PIN"

cp $REPO/examples/ec3/benchmark_ilen.py .
cp $REPO/examples/ec3/make_variant.py .
cp $REPO/examples/ec3/mycelium.target.json .
python make_variant.py

cd "$REPO"
python -m mycelium_accel accelerate --target "$TARGET" \
  --seeds 101,103,107,109,113,127,131 --no-apply \
  | tee .mycelium_benchmarks/ec3_report.json | tail -n 30
