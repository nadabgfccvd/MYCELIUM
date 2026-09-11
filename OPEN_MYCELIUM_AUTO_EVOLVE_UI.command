#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export MYCELIUM_UI_HOST=0.0.0.0
export MYCELIUM_UI_PORT="${MYCELIUM_UI_PORT:-8765}"
python scripts/mycelium_ui_server.py
