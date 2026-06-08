#!/bin/bash
# Daily data refresh + bot health check
# Run via cron: 0 */6 * * * /path/to/scripts/refresh_data.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="/freqtrade/project/user_data/config_btc_futures_v61.json"
DATADIR="/freqtrade/project/user_data/data"
PAIR="BTC/USDT:USDT"
CONTAINER="freqtrade-v61"
PORT="8081"

echo "[$(date)] Refreshing market data..."

docker run --rm \
  -v "$PROJECT_DIR:/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "$PAIR" \
  --timeframes 1h 4h \
  --timerange 20240101- \
  --config "$CONFIG" \
  -d "$DATADIR" 2>&1 | grep -E "Download|ERROR|length"

# Check if bot is alive
if ! docker ps --filter "name=$CONTAINER" --filter "status=running" | grep -q "$CONTAINER"; then
  echo "[$(date)] Bot not running! Restarting..."
  docker start "$CONTAINER"
  sleep 5
  curl -s -X POST "http://localhost:$PORT/api/v1/start" \
    -H "Content-Type: application/json" \
    -d '{}' \
    -u freqtrader:freqtrade
fi

echo "[$(date)] Data refresh complete."
