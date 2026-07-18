#!/bin/bash
# Deliver registry-driven trade alerts with retries and an append-only audit log.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CHECK_SCRIPT="${TRADE_CHECK_SCRIPT:-$PROJECT_DIR/scripts/check_trades.sh}"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-/home/ubuntu/.openclaw/openclaw.json}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
OPENCLAW_TIMEOUT_SECONDS="${OPENCLAW_TIMEOUT_SECONDS:-20}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:--5116417103}"
OPENCLAW_NOTIFY_TARGETS="${OPENCLAW_NOTIFY_TARGETS:-}"
DELIVERY_LOG="${TRADE_NOTIFY_DELIVERY_LOG:-$PROJECT_DIR/user_data/notification_delivery.log}"
DELIVERY_RETRY_ATTEMPTS="${TRADE_NOTIFY_RETRY_ATTEMPTS:-3}"
EVENT_ID="unknown"

log_delivery() {
  mkdir -p "$(dirname "$DELIVERY_LOG")"
  printf "%s event_id=%s channel=%s status=%s detail=%s\n" \
    "$(date -Is)" "$EVENT_ID" "$1" "$2" "$3" >> "$DELIVERY_LOG"
}

output="$($CHECK_SCRIPT 2>&1)"
[ -n "$output" ] || exit 0
if ! printf "%s" "$output" | grep -q "^TRADE_ALERT:"; then
  printf "%s\n" "$output"
  exit 0
fi

message="$(printf "%s" "$output" | sed 's/^TRADE_ALERT:[[:space:]]*//')"
message="交易 / 运行提醒

${message}"
EVENT_ID="$(printf "%s" "$message" | sha256sum | cut -c1-16)"

if [ "${NOTIFY_DRY_RUN:-0}" = "1" ]; then
  printf "%s\n" "$message"
  exit 0
fi

telegram_token() {
  local token="${TELEGRAM_BOT_TOKEN:-}"
  if [ -z "$token" ] && [ -r "$OPENCLAW_CONFIG" ]; then
    token="$(python3 - "$OPENCLAW_CONFIG" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    print(json.load(handle).get("channels", {}).get("telegram", {}).get("botToken", ""))
PY
)"
  fi
  printf "%s" "$token"
}

send_telegram() {
  local token telegram_output
  token="$(telegram_token)"
  if [ -z "$token" ]; then
    log_delivery telegram failed "missing-token"
    echo "TRADE_NOTIFY: Telegram bot token is not configured."
    return 0
  fi
  if telegram_output="$(curl -fsS \
    --retry "$DELIVERY_RETRY_ATTEMPTS" --retry-all-errors \
    --connect-timeout 8 --max-time 20 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${message}" 2>&1 >/dev/null)"; then
    log_delivery telegram ok "sent"
  else
    log_delivery telegram failed "${telegram_output:-curl-failed}"
    echo "TRADE_NOTIFY: Telegram notification failed."
  fi
}

send_openclaw_targets() {
  # Uses: openclaw message send
  # OPENCLAW_NOTIFY_TARGETS: channel:target or channel:account:target
  # Example: openclaw-weixin:account:target
  if [ -z "$OPENCLAW_NOTIFY_TARGETS" ]; then
    log_delivery openclaw skipped "no-targets"
    return 0
  fi
  if ! command -v "$OPENCLAW_BIN" >/dev/null 2>&1; then
    log_delivery openclaw failed "cli-missing"
    echo "TRADE_NOTIFY: OpenClaw CLI is not available."
    return 0
  fi

  local old_ifs="$IFS"
  local spec channel account target rest attempt sent openclaw_output message_id delivery
  IFS=","
  for spec in $OPENCLAW_NOTIFY_TARGETS; do
    IFS=":" read -r channel account target rest <<EOF
$spec
EOF
    if [ -z "${target:-}" ]; then
      target="${account:-}"
      account=""
    fi
    [ -z "${rest:-}" ] || target="${target}:${rest}"
    if [ -z "${channel:-}" ] || [ -z "${target:-}" ]; then
      log_delivery openclaw failed "invalid-target"
      continue
    fi
    attempt=1
    sent=0
    while [ "$attempt" -le "$DELIVERY_RETRY_ATTEMPTS" ]; do
      if [ -n "${account:-}" ]; then
        delivery="{\"mode\":\"announce\",\"channel\":\"${channel}\",\"to\":\"${target}\",\"accountId\":\"${account}\"}"
        openclaw_output="$(timeout "$OPENCLAW_TIMEOUT_SECONDS" "$OPENCLAW_BIN" message send \
          --channel "$channel" --account "$account" --target "$target" \
          --delivery "$delivery" --message "$message" 2>&1)" && sent=1
      else
        openclaw_output="$(timeout "$OPENCLAW_TIMEOUT_SECONDS" "$OPENCLAW_BIN" message send \
          --channel "$channel" --target "$target" --message "$message" 2>&1)" && sent=1
      fi
      [ "$sent" -eq 0 ] || break
      attempt=$((attempt + 1))
      [ "$attempt" -gt "$DELIVERY_RETRY_ATTEMPTS" ] || sleep 1
    done
    if [ "$sent" -eq 1 ]; then
      message_id="$(printf "%s" "$openclaw_output" | sed -n 's/.*Message ID: //p' | tail -1)"
      log_delivery openclaw ok "${channel}:${message_id:-sent}"
    else
      log_delivery openclaw failed "${channel}:${openclaw_output:-send-failed}"
      echo "TRADE_NOTIFY: OpenClaw notification failed for ${channel}."
    fi
  done
  IFS="$old_ifs"
}

send_telegram
send_openclaw_targets
