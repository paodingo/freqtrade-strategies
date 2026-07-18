#!/bin/bash
# Registry-driven dry-run trade monitor. The Python implementation keeps exact
# per-trade state so a close event includes the trade and its reasons.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "$PYTHON_BIN" "$PROJECT_DIR/scripts/check_trades.py" "$@"
