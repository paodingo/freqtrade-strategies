#!/usr/bin/env bash
set -euo pipefail

CONTAINER="freqtrade-v1130-crash-rebound-shadow"
CONFIG="/freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json"
DATADIR="/freqtrade/project/user_data/data"
PAIRS=(
  "ETH/USDT:USDT"
  "SOL/USDT:USDT"
  "DOGE/USDT:USDT"
  "LINK/USDT:USDT"
  "XRP/USDT:USDT"
  "BCH/USDT:USDT"
)
TIMEFRAMES=("15m" "4h")

utc_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

echo "[$(utc_now)] V11.30 market data refresh: starting"

if ! docker ps --filter "name=^/${CONTAINER}$" --filter "status=running" --format "{{.Names}}" | grep -qx "${CONTAINER}"; then
  echo "[$(utc_now)] V11.30 market data refresh: target container is not running: ${CONTAINER}" >&2
  exit 1
fi

docker exec "${CONTAINER}" freqtrade download-data \
  --config "${CONFIG}" \
  --datadir "${DATADIR}" \
  --trading-mode futures \
  --timeframes "${TIMEFRAMES[@]}" \
  --pairs "${PAIRS[@]}" \
  --data-format-ohlcv feather

docker exec -i "${CONTAINER}" python - <<'PY'
import json
import os
import time

import pandas as pd

base = "/freqtrade/project/user_data/data/futures"
pairs = ["ETH", "SOL", "DOGE", "LINK", "XRP", "BCH"]
timeframes = ["15m", "4h"]
rows = []

for pair in pairs:
    for timeframe in timeframes:
        path = f"{base}/{pair}_USDT_USDT-{timeframe}-futures.feather"
        item = {"pair": pair, "timeframe": timeframe, "path": path, "exists": os.path.exists(path)}
        if item["exists"]:
            df = pd.read_feather(path, columns=["date"])
            item["rows"] = int(len(df))
            item["latest_date"] = pd.Timestamp(df["date"].iloc[-1]).isoformat() if len(df) else None
        rows.append(item)

print(json.dumps({
    "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "files": rows,
}, indent=2))
PY

echo "[$(utc_now)] V11.30 market data refresh: completed"
