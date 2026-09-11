#!/usr/bin/env bash
# EC1 (B2): refaz o experimento de dogfooding e re-deriva o veredito.
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/ec1_dogfood.py --rounds 30 \
  --seeds 101,103,107,109,113,127,131 \
  --out .mycelium_benchmarks/ec1_report.json
echo "---"
echo "veredito em .mycelium_benchmarks/ec1_report.json (.verdict)"
