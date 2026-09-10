#!/usr/bin/env bash
# Roadmap F4 — dogfood gate semanal: mede throughput do engine e barra
# regressão de performance. Relatório datado em .mycelium_benchmarks/.
# Falha (exit 1) se rounds/s cair >2% vs. baseline persistido.
# Baseline é MACHINE-SPECIFIC (gitignored): após trocar de máquina,
# apague .mycelium_benchmarks/dogfood-baseline.json para recalibrar.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT_DIR=".mycelium_benchmarks"
mkdir -p "$OUT_DIR"
TS=$(date -u +%Y%m%dT%H%M%SZ)
TMP_STATE=$(mktemp -d)/dogfood_state
ROUNDS=60

# W4: median-of-3 — single samples vary ±5% on shared hosts; the 2% gate
# needs a robust estimator (same threshold, ~3 s cost).
RPS=""
for i in 1 2 3; do
  START=$(date +%s.%N)
  python -m mycelium_accel run --seed 101 --state-dir "$TMP_STATE" --rounds "$ROUNDS" > /dev/null
  END=$(date +%s.%N)
  RPS="$RPS $(python3 -c "print($ROUNDS / max(0.001, $END - $START))")"
done
RPS=$(python3 -c "import statistics; print(statistics.median(map(float, '$RPS'.split())))")

REPORT="$OUT_DIR/dogfood-$TS.json"
BASELINE_FILE="$OUT_DIR/dogfood-baseline.json"
python3 - "$REPORT" "$RPS" "$ROUNDS" << 'PYEOF'
import json, sys
report = {"timestamp": sys.argv[1].split("dogfood-")[1].replace(".json", ""),
          "rounds": int(sys.argv[3]), "rounds_per_second": float(sys.argv[2])}
open(sys.argv[1], "w").write(json.dumps(report, indent=2))
print(json.dumps(report))
PYEOF

if [ -f "$BASELINE_FILE" ]; then
  BASE=$(python3 -c "import json; print(json.load(open('$BASELINE_FILE'))['rounds_per_second'])")
  python3 -c "
import json, sys
base = float('$BASE'); now = float('$RPS')
drop = (base - now) / base
print(f'baseline={base:.2f} rps agora={now:.2f} rps queda={drop*100:.2f}%')
sys.exit(1 if drop > 0.02 else 0)
" || { echo "DOGFOOD GATE FALHOU: regressão de throughput >2%"; exit 1; }
else
  cp "$REPORT" "$BASELINE_FILE"
  echo "baseline criado: $BASELINE_FILE"
fi
echo "DOGFOOD GATE VERDE"
