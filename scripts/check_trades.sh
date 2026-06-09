#!/bin/bash
# Monitor the V6/V6.1 comparison bots and print TRADE_ALERT lines on changes.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="${TRADE_MONITOR_STATE_FILE:-$PROJECT_DIR/user_data/trade_monitor_state.json}"
AUTH="${FREQTRADE_API_AUTH:-freqtrader:freqtrade}"
BOTS=(
  "V6:8080"
  "V6.1:8081"
)

if ! command -v jq >/dev/null 2>&1; then
  echo "TRADE_ALERT: jq is not installed on the server; trade monitor cannot parse API responses."
  exit 0
fi

mkdir -p "$(dirname "$STATE_FILE")"
[ -s "$STATE_FILE" ] || echo "{}" > "$STATE_FILE"

prev_state="$(cat "$STATE_FILE")"
current_state="{}"
changes=""

for bot in "${BOTS[@]}"; do
  label="${bot%%:*}"
  port="${bot##*:}"

  count_json="$(curl -sf -u "$AUTH" "http://localhost:$port/api/v1/count" 2>/dev/null)"
  if [ -z "$count_json" ]; then
    changes="${changes}${label}: API count endpoint is not responding on localhost:${port}.\n"
    continue
  fi

  profit_json="$(curl -sf -u "$AUTH" "http://localhost:$port/api/v1/profit" 2>/dev/null)"
  if [ -z "$profit_json" ]; then
    changes="${changes}${label}: API profit endpoint is not responding on localhost:${port}.\n"
    continue
  fi

  open_trades="$(echo "$count_json" | jq -r '.current // 0')"
  total_trades="$(echo "$profit_json" | jq -r '.trade_count // 0')"
  closed_trades="$(echo "$profit_json" | jq -r '.closed_trade_count // 0')"
  profit_all_coin="$(echo "$profit_json" | jq -r '.profit_all_coin // 0')"
  latest_trade_date="$(echo "$profit_json" | jq -r '.latest_trade_date // ""')"

  current_state="$(echo "$current_state" | jq \
    --arg label "$label" \
    --argjson open "$open_trades" \
    --argjson total "$total_trades" \
    --argjson closed "$closed_trades" \
    --arg profit "$profit_all_coin" \
    --arg latest "$latest_trade_date" \
    '.[$label] = {
      open: $open,
      total: $total,
      closed: $closed,
      profit_all_coin: $profit,
      latest_trade_date: $latest
    }')"

  prev_bot="$(echo "$prev_state" | jq -r --arg label "$label" '.[$label] // empty')"
  [ -n "$prev_bot" ] || continue

  prev_open="$(echo "$prev_bot" | jq -r '.open // 0')"
  prev_total="$(echo "$prev_bot" | jq -r '.total // 0')"
  prev_closed="$(echo "$prev_bot" | jq -r '.closed // 0')"

  new_open=$((open_trades - prev_open))
  new_total=$((total_trades - prev_total))
  new_closed=$((closed_trades - prev_closed))

  if [ "$new_open" -gt 0 ] || [ "$new_closed" -gt 0 ] || [ "$new_total" -gt 0 ]; then
    changes="${changes}${label}: open=${open_trades} total=${total_trades} closed=${closed_trades} profit_all_coin=${profit_all_coin} latest=${latest_trade_date}"
    [ "$new_open" -gt 0 ] && changes="${changes} new_open=${new_open}"
    [ "$new_closed" -gt 0 ] && changes="${changes} new_closed=${new_closed}"
    [ "$new_total" -gt 0 ] && changes="${changes} new_total=${new_total}"
    changes="${changes}\n"
  fi
done

echo "$current_state" > "$STATE_FILE"

if [ -n "$changes" ]; then
  echo -e "TRADE_ALERT:${changes}"
fi
