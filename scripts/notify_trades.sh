#!/bin/bash
# Send a Telegram notification when check_trades.sh reports trade changes.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CHECK_SCRIPT="${TRADE_CHECK_SCRIPT:-$PROJECT_DIR/scripts/check_trades.sh}"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-/home/ubuntu/.openclaw/openclaw.json}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:--5116417103}"

output="$("$CHECK_SCRIPT" 2>&1)"

if [ -z "$output" ]; then
  exit 0
fi

if ! printf "%s" "$output" | grep -q "^TRADE_ALERT:"; then
  printf "%s\n" "$output"
  exit 0
fi

message="$(printf "%s" "$output" | sed 's/^TRADE_ALERT:[[:space:]]*//')"
message="交易 / 运行提醒
${message}"

if [ "${NOTIFY_DRY_RUN:-0}" = "1" ]; then
  printf "%s\n" "$message"
  exit 0
fi

token="${TELEGRAM_BOT_TOKEN:-}"
if [ -z "$token" ] && [ -r "$OPENCLAW_CONFIG" ]; then
  token="$(python3 - "$OPENCLAW_CONFIG" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)
print(data.get("channels", {}).get("telegram", {}).get("botToken", ""))
PY
)"
fi

if [ -z "$token" ]; then
  echo "TRADE_ALERT: Telegram bot token is not configured."
  exit 0
fi

curl -fsS \
  "https://api.telegram.org/bot${token}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${message}" \
  >/dev/null
