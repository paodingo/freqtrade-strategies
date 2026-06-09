#!/bin/bash
# Monitor the V6.2/V6.1 comparison bots and print TRADE_ALERT lines on changes.
# Alerts are emitted only when state changes, so a temporary API outage will not
# spam Telegram every minute.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="${TRADE_MONITOR_STATE_FILE:-$PROJECT_DIR/user_data/trade_monitor_state.json}"
AUTH="${FREQTRADE_API_AUTH:-freqtrader:freqtrade}"
BOTS=(
  "V6.2:8080"
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

append_change() {
  changes="${changes}$1\n"
}

fetch_endpoint() {
  local port="$1"
  local endpoint="$2"
  curl -sf -u "$AUTH" "http://localhost:${port}/api/v1/${endpoint}" 2>/dev/null
}

json_set_bot() {
  local label="$1"
  local payload="$2"
  current_state="$(echo "$current_state" | jq --arg label "$label" --argjson payload "$payload" '.[$label] = $payload')"
}

for bot in "${BOTS[@]}"; do
  label="${bot%%:*}"
  port="${bot##*:}"

  prev_bot="$(echo "$prev_state" | jq -c --arg label "$label" '.[$label] // null')"
  prev_ok="$(echo "$prev_bot" | jq -r '.ok // empty')"

  config_json="$(fetch_endpoint "$port" "show_config")"
  count_json="$(fetch_endpoint "$port" "count")"
  profit_json="$(fetch_endpoint "$port" "profit")"
  status_json="$(fetch_endpoint "$port" "status")"

  if [ -z "$config_json" ] || [ -z "$count_json" ] || [ -z "$profit_json" ] || [ -z "$status_json" ]; then
    error_payload="$(jq -n \
      --argjson ok false \
      --arg port "$port" \
      --arg error "Freqtrade API is not responding or trader is not running" \
      '{ok: $ok, port: $port, error: $error}')"
    json_set_bot "$label" "$error_payload"
    if [ "$prev_ok" != "false" ]; then
      append_change "${label}: API 异常或 bot 未运行，localhost:${port} 无法完整读取状态。"
    fi
    continue
  fi

  bot_state="$(echo "$config_json" | jq -r '.state // "unknown"')"
  runmode="$(echo "$config_json" | jq -r '.runmode // "unknown"')"
  strategy="$(echo "$config_json" | jq -r '.strategy // "unknown"')"
  stake_amount="$(echo "$config_json" | jq -r '.stake_amount // ""')"
  max_open_trades="$(echo "$config_json" | jq -r '.max_open_trades // 0')"
  open_trades="$(echo "$count_json" | jq -r '.current // 0')"
  total_trades="$(echo "$profit_json" | jq -r '.trade_count // 0')"
  closed_trades="$(echo "$profit_json" | jq -r '.closed_trade_count // 0')"
  profit_all_coin="$(echo "$profit_json" | jq -r '.profit_all_coin // 0')"
  latest_trade_date="$(echo "$profit_json" | jq -r '.latest_trade_date // ""')"
  open_summary="$(echo "$status_json" | jq -c '[.[] | {
    trade_id,
    pair,
    is_short,
    enter_tag,
    open_rate,
    current_rate,
    stake_amount,
    profit_abs,
    profit_pct,
    stop_loss_abs,
    liquidation_price
  }]')"

  current_state="$(echo "$current_state" | jq \
    --arg label "$label" \
    --arg state "$bot_state" \
    --arg runmode "$runmode" \
    --arg strategy "$strategy" \
    --arg stake_amount "$stake_amount" \
    --arg max_open_trades "$max_open_trades" \
    --argjson open "$open_trades" \
    --argjson total "$total_trades" \
    --argjson closed "$closed_trades" \
    --arg profit "$profit_all_coin" \
    --arg latest "$latest_trade_date" \
    --argjson open_summary "$open_summary" \
    '.[$label] = {
      ok: true,
      state: $state,
      runmode: $runmode,
      strategy: $strategy,
      stake_amount: $stake_amount,
      max_open_trades: $max_open_trades,
      open: $open,
      total: $total,
      closed: $closed,
      profit_all_coin: $profit,
      latest_trade_date: $latest,
      open_summary: $open_summary
    }')"

  if [ "$prev_ok" = "false" ]; then
    append_change "${label}: API 已恢复，当前 ${bot_state}/${runmode}，策略 ${strategy}。"
  fi

  if [ "$bot_state" != "running" ]; then
    prev_state_value="$(echo "$prev_bot" | jq -r '.state // empty')"
    if [ "$prev_state_value" != "$bot_state" ]; then
      append_change "${label}: bot 状态变为 ${bot_state}，当前不会正常交易，请检查。"
    fi
  fi

  [ "$prev_bot" != "null" ] || continue

  prev_open="$(echo "$prev_bot" | jq -r '.open // 0')"
  prev_total="$(echo "$prev_bot" | jq -r '.total // 0')"
  prev_closed="$(echo "$prev_bot" | jq -r '.closed // 0')"
  prev_open_summary="$(echo "$prev_bot" | jq -c '.open_summary // []')"

  new_open=$((open_trades - prev_open))
  new_total=$((total_trades - prev_total))
  new_closed=$((closed_trades - prev_closed))

  if [ "$new_open" -gt 0 ] || [ "$open_summary" != "$prev_open_summary" ] && [ "$open_trades" -gt 0 ] && [ "$prev_open" -eq 0 ]; then
    first_trade="$(echo "$open_summary" | jq -r '.[0] | "\(.pair) \((if .is_short then "做空" else "做多" end)) signal=\(.enter_tag // "-") open=\(.open_rate // "-") current=\(.current_rate // "-") stake=\(.stake_amount // "-") pnl=\(.profit_abs // "-")"')"
    append_change "${label}: 新开仓 ${first_trade}"
  fi

  if [ "$new_closed" -gt 0 ]; then
    append_change "${label}: 有 ${new_closed} 笔交易平仓。open=${open_trades} total=${total_trades} closed=${closed_trades} profit_all_coin=${profit_all_coin} latest=${latest_trade_date}"
  elif [ "$new_total" -gt 0 ]; then
    append_change "${label}: 交易数量变化。open=${open_trades} total=${total_trades} closed=${closed_trades} profit_all_coin=${profit_all_coin} latest=${latest_trade_date}"
  fi
done

echo "$current_state" > "$STATE_FILE"

if [ -n "$changes" ]; then
  echo -e "TRADE_ALERT:${changes}"
fi
