#!/bin/bash
# Run the local production-readiness smoke tests used by this repo.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

node --check dashboard/server.js
node --check dashboard/public/app.js

docker run --rm --entrypoint python \
  -v "$PROJECT_DIR:/freqtrade/project" \
  -w /freqtrade/project \
  freqtradeorg/freqtrade:stable \
  -m unittest -v \
  tests.test_regime_aware_v6 \
  tests.test_regime_aware_v61 \
  tests.test_regime_aware_v62 \
  tests.test_risk_manager \
  tests.test_regime_detector
