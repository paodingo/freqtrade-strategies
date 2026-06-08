#!/bin/bash
# Start freqtrade bot with automatic data refresh
# Usage: ./scripts/start_bot.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="/freqtrade/project/user_data/config_btc_futures_v61.json"
DATADIR="/freqtrade/project/user_data/data"
PAIR="BTC/USDT:USDT"
STRATEGY="RegimeAwareV61"
CONTAINER="freqtrade-v61"
PORT="8081"

# 1. Refresh market data
echo "[$(date)] Downloading fresh data..."
docker run --rm \
  -v "$PROJECT_DIR:/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "$PAIR" \
  --timeframes 1h 4h \
  --timerange 20240101- \
  --config "$CONFIG" \
  -d "$DATADIR"

# 2. Start/restart the bot
echo "[$(date)] Starting freqtrade bot with $STRATEGY..."
docker stop "$CONTAINER" 2>/dev/null || true
docker rm "$CONTAINER" 2>/dev/null || true

docker run -d \
  --name "$CONTAINER" \
  --restart unless-stopped \
  -p "$PORT:$PORT" \
  -v "$PROJECT_DIR:/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy "$STRATEGY" \
  --strategy-path /freqtrade/project/strategies \
  --config "$CONFIG" \
  --datadir "$DATADIR"

# 3. Start the bot via API
sleep 8
curl -s -X POST "http://localhost:$PORT/api/v1/start" \
  -H "Content-Type: application/json" \
  -d '{}' \
  -u freqtrader:freqtrade

echo "[$(date)] Bot started. Check status: docker logs -f $CONTAINER"
