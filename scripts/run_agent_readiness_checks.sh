#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

node --check scripts/guard_harness_diff.js
node --check scripts/guard_no_secret_material.js
node --check scripts/guard_trading_surface.js

node scripts/guard_harness_diff.js
node scripts/guard_no_secret_material.js
node scripts/guard_trading_surface.js
