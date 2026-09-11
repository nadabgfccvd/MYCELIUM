#!/usr/bin/env bash
# EC2 (B4): refaz o experimento de flags C e re-deriva o veredito.
# Requer: gcc + make (ver `mycelium-accel doctor`). Offline por design.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v gcc > /dev/null || ! command -v make > /dev/null; then
  echo "EC2 requer gcc+make (doctor reporta WARN sem eles). Abortando."
  exit 2
fi
python -m mycelium_accel accelerate --target examples/c \
  --seeds 101,103,107,109,113,127,131 --no-apply \
  | tee .mycelium_benchmarks/ec2_report.json | tail -n 40
