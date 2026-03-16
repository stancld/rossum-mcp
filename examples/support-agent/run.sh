#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$SCRIPT_DIR/bin:$PATH"

cd "$SCRIPT_DIR/resources"

claude --model claude-haiku-4-5-20251001 --dangerously-skip-permissions "start"
