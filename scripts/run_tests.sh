#!/bin/bash
# Run the local production-readiness smoke tests used by this repo.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

node --check dashboard/server.js
node --check dashboard/lib/interpretation.js
node --check dashboard/public/app.js
node --test tests/test_dashboard_interpretation.js
node --test tests/test_dashboard_public_metadata.js
node --test tests/test_monitor_store.js
python3 -m py_compile scripts/format_trade_alert.py

docker run --rm --entrypoint python \
  -v "$PROJECT_DIR:/freqtrade/project" \
  -w /freqtrade/project \
  freqtradeorg/freqtrade:stable \
  -m unittest -v \
  tests.test_format_trade_alert \
  tests.test_regime_aware_v6 \
  tests.test_regime_aware_v61 \
  tests.test_regime_aware_v62 \
  tests.test_regime_aware_v63 \
  tests.test_regime_aware_v64 \
  tests.test_regime_aware_v65 \
  tests.test_regime_aware_v66 \
  tests.test_regime_aware_v66_alpha_family \
  tests.test_trade_supervisor_filter \
  tests.test_risk_manager \
  tests.test_regime_detector
