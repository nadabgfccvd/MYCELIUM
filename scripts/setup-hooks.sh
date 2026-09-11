#!/usr/bin/env bash
# W3.4: point git at the versioned hooks (run once per clone).
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
chmod +x .githooks/pre-push
echo "hooks installed: $(git config core.hooksPath)/pre-push"
