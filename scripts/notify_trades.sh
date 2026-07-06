#!/bin/bash
# Send notifications when check_trades.sh reports trade changes.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CHECK_SCRIPT="${TRADE_CHECK_SCRIPT:-$PROJECT_DIR/scripts/check_trades.sh}"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-/home/ubuntu/.openclaw/openclaw.json}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
OPENCLAW_TIMEOUT_SECONDS="${OPENCLAW_TIMEOUT_SECONDS:-20}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:--5116417103}"
OPENCLAW_NOTIFY_TARGETS="${OPENCLAW_NOTIFY_TARGETS:-}"
DELIVERY_LOG="${TRADE_NOTIFY_DELIVERY_LOG:-$PROJECT_DIR/user_data/notification_delivery.log}"

log_delivery() {
  mkdir -p "$(dirname "$DELIVERY_LOG")"
  printf "%s channel=%s status=%s detail=%s\n" \
    "$(date -Is)" \
    "$1" \
    "$2" \
    "$3" \
    >> "$DELIVERY_LOG"
}

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

telegram_token() {
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
  printf "%s" "$token"
}

send_telegram() {
  token="$(telegram_token)"
  if [ -z "$token" ]; then
    echo "TRADE_NOTIFY: Telegram bot token is not configured."
    log_delivery telegram failed "missing-token"
    return 0
  fi

  if telegram_output="$(curl -fsS \
    "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${message}" \
    2>&1 >/dev/null)"; then
    log_delivery telegram ok "sent"
  else
    log_delivery telegram failed "${telegram_output:-curl-failed}"
    echo "TRADE_NOTIFY: Telegram notification failed."
  fi
}

send_openclaw_targets() {
  # Uses: openclaw message send
  # OPENCLAW_NOTIFY_TARGETS accepts comma-separated specs:
  #   channel:target
  #   channel:account:target
  # Example: openclaw-weixin:account:target
  if [ -z "$OPENCLAW_NOTIFY_TARGETS" ]; then
    log_delivery openclaw skipped "no-targets"
    return 0
  fi
  if ! command -v "$OPENCLAW_BIN" >/dev/null 2>&1; then
    echo "TRADE_NOTIFY: OpenClaw CLI is not available."
    log_delivery openclaw failed "cli-missing"
    return 0
  fi

  old_ifs="$IFS"
  IFS=","
  for spec in $OPENCLAW_NOTIFY_TARGETS; do
    IFS=":" read -r channel account target rest <<EOF
$spec
EOF
    if [ -z "$channel" ]; then
      continue
    fi
    if [ -z "$target" ]; then
      target="$account"
      account=""
    fi
    if [ -n "$rest" ]; then
      target="${target}:${rest}"
    fi
    if [ -z "$target" ]; then
      echo "TRADE_NOTIFY: OpenClaw target is empty for ${channel}."
      log_delivery openclaw failed "${channel}:empty-target"
      continue
    fi

    if [ -n "$account" ]; then
      delivery="{\"mode\":\"announce\",\"channel\":\"${channel}\",\"to\":\"${target}\",\"accountId\":\"${account}\"}"
      if openclaw_output="$(timeout "$OPENCLAW_TIMEOUT_SECONDS" "$OPENCLAW_BIN" message send \
        --channel "$channel" \
        --account "$account" \
        --target "$target" \
        --delivery "$delivery" \
        --message "$message" 2>&1)"; then
        message_id="$(printf "%s" "$openclaw_output" | sed -n 's/.*Message ID: //p' | tail -1)"
        log_delivery openclaw ok "${channel}:${message_id:-sent}"
      else
        log_delivery openclaw failed "${channel}:${openclaw_output:-send-failed}"
        echo "TRADE_NOTIFY: OpenClaw notification failed for ${channel}."
      fi
    else
      if openclaw_output="$(timeout "$OPENCLAW_TIMEOUT_SECONDS" "$OPENCLAW_BIN" message send \
        --channel "$channel" \
        --target "$target" \
        --message "$message" 2>&1)"; then
        message_id="$(printf "%s" "$openclaw_output" | sed -n 's/.*Message ID: //p' | tail -1)"
        log_delivery openclaw ok "${channel}:${message_id:-sent}"
      else
        log_delivery openclaw failed "${channel}:${openclaw_output:-send-failed}"
        echo "TRADE_NOTIFY: OpenClaw notification failed for ${channel}."
      fi
    fi
  done
  IFS="$old_ifs"
}

send_telegram
send_openclaw_targets
