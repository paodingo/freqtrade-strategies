#!/bin/bash
# Market data refresh + bot health check
# Run via cron: 0 */6 * * * /path/to/scripts/refresh_data.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="/freqtrade/project/user_data/config_btc_futures_v63.json"
DATADIR="/freqtrade/project/user_data/data"
PAIR="BTC/USDT:USDT"
BOTS=(
  "freqtrade-v63:8080"
  "freqtrade-v65:8081"
  "freqtrade-v66:8082"
)

echo "[$(date)] Refreshing market data..."

docker run --rm \
  -v "$PROJECT_DIR:/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "$PAIR" \
  --timeframes 15m 1h 4h \
  --timerange 20240101- \
  --config "$CONFIG" \
  --trading-mode futures \
  -d "$DATADIR" 2>&1 | grep -E "Download|ERROR|length"

for bot in "${BOTS[@]}"; do
  CONTAINER="${bot%%:*}"
  PORT="${bot##*:}"

  if ! docker ps --filter "name=^/${CONTAINER}$" --filter "status=running" --format "{{.Names}}" | grep -qx "$CONTAINER"; then
    echo "[$(date)] $CONTAINER not running. Starting container..."
    docker start "$CONTAINER"
    sleep 5
  fi

  if curl -sf "http://localhost:$PORT/api/v1/ping" >/dev/null; then
    echo "[$(date)] $CONTAINER API healthy on localhost:$PORT."
  else
    echo "[$(date)] $CONTAINER API is not responding on localhost:$PORT."
  fi
done

echo "[$(date)] Data refresh complete."
