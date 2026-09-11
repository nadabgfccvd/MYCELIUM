#!/usr/bin/env bash
# Roadmap F3 — encadeia N fatias de self-improve-daemon no mesmo state-dir.
# Uso: bash scripts/run_slices.sh [--slices 4] [--slice-seconds 1500]
#        [--state-dir .mycelium_state_longrun] [--seed 101] [--extra-args "..."]
set -euo pipefail
cd "$(dirname "$0")/.."

SLICES=4
SLICE_SECONDS=1500
STATE_DIR=".mycelium_state_longrun"
SEED=101
EXTRA_ARGS="--rounds-per-cycle 10 --benchmark-rounds 8 --benchmark-seeds 101,103,107,109,113,127,131 --guard-workers 4 --semantic-mutation-rate 0.3"

while [ $# -gt 0 ]; do
  case "$1" in
    --slices) SLICES="$2"; shift 2;;
    --slice-seconds) SLICE_SECONDS="$2"; shift 2;;
    --state-dir) STATE_DIR="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    --extra-args) EXTRA_ARGS="$2"; shift 2;;
    *) echo "flag desconhecida: $1"; exit 2;;
  esac
done

mkdir -p reports
for i in $(seq 1 "$SLICES"); do
  echo "===== fatia $i/$SLICES ($(date -u +%FT%TZ)) ====="
  # shellcheck disable=SC2086
  python -m mycelium_accel self-improve-daemon \
    --seed "$SEED" --state-dir "$STATE_DIR" \
    --time-budget-seconds "$SLICE_SECONDS" $EXTRA_ARGS \
    | tee "reports/slice-${i}-$(date -u +%Y%m%dT%H%M%SZ).log" | tail -n 5
  if [ -f "$STATE_DIR/KILL" ]; then
    echo "kill-switch presente — interrompendo encadeamento após fatia $i."
    break
  fi
done

echo "===== verificação de continuidade ====="
python scripts/verify_run_continuity.py --state-dir "$STATE_DIR"
