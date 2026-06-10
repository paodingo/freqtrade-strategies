#!/bin/bash
# Start a freqtrade dry-run bot with automatic data refresh.
# Usage: ./scripts/start_bot.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${CONFIG:-/freqtrade/project/user_data/config_btc_futures_v65.json}"
DATADIR="${DATADIR:-/freqtrade/project/user_data/data}"
PAIR="${PAIR:-BTC/USDT:USDT}"
STRATEGY="${STRATEGY:-RegimeAwareV65}"
CONTAINER="${CONTAINER:-freqtrade-v65}"
PORT="${PORT:-8081}"
AUTH="${FREQTRADE_API_AUTH:-freqtrader:freqtrade}"

# 1. Refresh market data
echo "[$(date)] Downloading fresh data..."
docker run --rm \
  -v "$PROJECT_DIR:/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "$PAIR" \
  --timeframes 15m 1h 4h \
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
  -p "127.0.0.1:$PORT:$PORT" \
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
  -u "$AUTH"

echo "[$(date)] Bot started. Check status: docker logs -f $CONTAINER"
