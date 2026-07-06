#!/bin/bash
# Monitor the active dry-run comparison bots and print TRADE_ALERT lines on changes.
# API alerts are debounced: short endpoint glitches are recorded in state but do
# not alert until they repeat across consecutive monitor runs.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="${TRADE_MONITOR_STATE_FILE:-$PROJECT_DIR/user_data/trade_monitor_state.json}"
LOCK_FILE="${TRADE_MONITOR_LOCK_FILE:-$STATE_FILE.lock}"
FORMATTER="${TRADE_ALERT_FORMATTER:-$PROJECT_DIR/scripts/format_trade_alert.py}"
AUTH="${FREQTRADE_API_AUTH:-freqtrader:freqtrade}"
API_TIMEOUT_SECONDS="${TRADE_MONITOR_API_TIMEOUT_SECONDS:-8}"
API_RETRY_ATTEMPTS="${TRADE_MONITOR_API_RETRY_ATTEMPTS:-2}"
API_RETRY_SLEEP_SECONDS="${TRADE_MONITOR_API_RETRY_SLEEP_SECONDS:-1}"
API_FAILURE_ALERT_THRESHOLD="${TRADE_MONITOR_API_FAILURE_ALERT_THRESHOLD:-3}"

BOTS=(
  "V11.29 Current Research Candidate:8122"
  "V10.8.2 Historical Profit Benchmark:8091"
)

if ! command -v jq >/dev/null 2>&1; then
  echo "TRADE_ALERT: jq is not installed on the server; trade monitor cannot parse API responses."
  exit 0
fi

mkdir -p "$(dirname "$STATE_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi
[ -s "$STATE_FILE" ] || echo "{}" > "$STATE_FILE"

if ! prev_state="$(jq -c '.' "$STATE_FILE" 2>/dev/null)"; then
  prev_state="{}"
fi
current_state="{}"
changes=""

append_change() {
  changes="${changes}$1\n\n"
}

append_event() {
  local payload="$1"
  local formatted
  formatted="$(printf "%s" "$payload" | python3 "$FORMATTER" 2>/dev/null)"
  if [ -n "$formatted" ]; then
    append_change "$formatted"
  fi
}

fetch_endpoint() {
  local port="$1"
  local endpoint="$2"
  local attempt=1
  local raw

  while [ "$attempt" -le "$API_RETRY_ATTEMPTS" ]; do
    if raw="$(curl --max-time "$API_TIMEOUT_SECONDS" -sf -u "$AUTH" "http://localhost:${port}/api/v1/${endpoint}" 2>/dev/null)"; then
      if printf "%s" "$raw" | jq -c '.' 2>/dev/null; then
        return 0
      fi
    fi

    if [ "$attempt" -lt "$API_RETRY_ATTEMPTS" ]; then
      sleep "$API_RETRY_SLEEP_SECONDS"
    fi
    attempt=$((attempt + 1))
  done

  return 0
}

json_set_bot() {
  local label="$1"
  local payload="$2"
  current_state="$(echo "$current_state" | jq --arg label "$label" --argjson payload "$payload" '.[$label] = $payload')"
}

record_api_failure() {
  local label="$1"
  local port="$2"
  local prev_bot="$3"
  local prev_ok="$4"
  local failed_endpoints_json="$5"
  local prev_failures
  local failures
  local payload

  prev_failures="$(echo "$prev_bot" | jq -r 'if type == "object" then (.consecutive_api_failures // 0) else 0 end')"
  failures=$((prev_failures + 1))

  if [ "$failures" -lt "$API_FAILURE_ALERT_THRESHOLD" ]; then
    payload="$(jq -n \
      --argjson previous "$prev_bot" \
      --argjson ok true \
      --arg port "$port" \
      --arg error "Transient Freqtrade API read failure; alert suppressed until repeated." \
      --argjson failed_endpoints "$failed_endpoints_json" \
      --argjson failures "$failures" \
      --argjson threshold "$API_FAILURE_ALERT_THRESHOLD" \
      'if ($previous | type) == "object"
       then $previous + {ok: $ok, port: $port, api_probe_ok: false, consecutive_api_failures: $failures, api_failure_alert_threshold: $threshold, failed_endpoints: $failed_endpoints, error: $error}
       else {ok: $ok, port: $port, api_probe_ok: false, consecutive_api_failures: $failures, api_failure_alert_threshold: $threshold, failed_endpoints: $failed_endpoints, error: $error}
       end')"
    json_set_bot "$label" "$payload"
    return 0
  fi

  payload="$(jq -n \
    --argjson ok false \
    --arg port "$port" \
    --arg error "Freqtrade API read failed repeatedly; bot state is not fully observable." \
    --argjson failed_endpoints "$failed_endpoints_json" \
    --argjson failures "$failures" \
    --argjson threshold "$API_FAILURE_ALERT_THRESHOLD" \
    '{ok: $ok, port: $port, api_probe_ok: false, consecutive_api_failures: $failures, api_failure_alert_threshold: $threshold, failed_endpoints: $failed_endpoints, error: $error}')"
  json_set_bot "$label" "$payload"

  if [ "$prev_ok" != "false" ] || [ "$prev_failures" -lt "$API_FAILURE_ALERT_THRESHOLD" ]; then
    append_event "$(jq -n \
      --arg type "api_error" \
      --arg label "$label" \
      --arg port "$port" \
      --argjson failed_endpoints "$failed_endpoints_json" \
      --argjson failures "$failures" \
      --argjson threshold "$API_FAILURE_ALERT_THRESHOLD" \
      '{type: $type, label: $label, port: $port, failed_endpoints: $failed_endpoints, consecutive_failures: $failures, threshold: $threshold}')"
  fi
}

for bot in "${BOTS[@]}"; do
  label="${bot%%:*}"
  port="${bot##*:}"
  failed_endpoints=()

  prev_bot="$(echo "$prev_state" | jq -c --arg label "$label" '.[$label] // null')"
  prev_ok="$(echo "$prev_bot" | jq -r 'if type == "object" and has("ok") then (.ok | tostring) else empty end')"

  config_json="$(fetch_endpoint "$port" "show_config")"
  if [ -z "$config_json" ]; then
    failed_endpoints+=("show_config")
    failed_endpoints_json="$(printf '%s\n' "${failed_endpoints[@]}" | jq -R . | jq -sc '.')"
    record_api_failure "$label" "$port" "$prev_bot" "$prev_ok" "$failed_endpoints_json"
    continue
  fi

  bot_state="$(echo "$config_json" | jq -r '.state // "unknown"')"
  runmode="$(echo "$config_json" | jq -r '.runmode // "unknown"')"
  strategy="$(echo "$config_json" | jq -r '.strategy // "unknown"')"
  stake_amount="$(echo "$config_json" | jq -r '.stake_amount // ""')"
  max_open_trades="$(echo "$config_json" | jq -r '.max_open_trades // 0')"

  if [ "$bot_state" != "running" ]; then
    profit_json="$(fetch_endpoint "$port" "profit")"
    [ -n "$profit_json" ] || profit_json="{}"
    total_trades="$(printf "%s" "$profit_json" | jq -r '.trade_count // 0')"
    closed_trades="$(printf "%s" "$profit_json" | jq -r '.closed_trade_count // 0')"
    profit_all_coin="$(printf "%s" "$profit_json" | jq -r '.profit_all_coin // 0')"
    profit_closed_coin="$(printf "%s" "$profit_json" | jq -r '.profit_closed_coin // .profit_all_coin // 0')"
    latest_trade_date="$(printf "%s" "$profit_json" | jq -r '.latest_trade_date // ""')"
    state_payload="$(jq -n \
      --argjson ok true \
      --arg state "$bot_state" \
      --arg runmode "$runmode" \
      --arg strategy "$strategy" \
      --arg stake_amount "$stake_amount" \
      --arg max_open_trades "$max_open_trades" \
      --argjson open 0 \
      --arg total "$total_trades" \
      --arg closed "$closed_trades" \
      --arg profit "$profit_all_coin" \
      --arg profit_closed "$profit_closed_coin" \
      --arg latest "$latest_trade_date" \
      '{ok: $ok, api_probe_ok: true, consecutive_api_failures: 0, state: $state, runmode: $runmode, strategy: $strategy, stake_amount: $stake_amount, max_open_trades: $max_open_trades, open: $open, total: ($total | tonumber), closed: ($closed | tonumber), profit_all_coin: $profit, profit_closed_coin: $profit_closed, latest_trade_date: $latest, open_summary: []}')"
    json_set_bot "$label" "$state_payload"

    if [ "$prev_ok" = "false" ]; then
      append_event "$(jq -n \
        --arg type "api_recovered" \
        --arg label "$label" \
        --arg state "$bot_state" \
        --arg runmode "$runmode" \
        --arg strategy "$strategy" \
        '{type: $type, label: $label, state: $state, runmode: $runmode, strategy: $strategy}')"
    fi

    prev_state_value="$(echo "$prev_bot" | jq -r '.state // empty')"
    if [ "$prev_state_value" != "$bot_state" ]; then
      append_event "$(jq -n \
        --arg type "bot_state" \
        --arg label "$label" \
        --arg state "$bot_state" \
        '{type: $type, label: $label, state: $state}')"
    fi
    continue
  fi

  count_json="$(fetch_endpoint "$port" "count")"
  [ -n "$count_json" ] || failed_endpoints+=("count")
  profit_json="$(fetch_endpoint "$port" "profit")"
  [ -n "$profit_json" ] || failed_endpoints+=("profit")
  status_json="$(fetch_endpoint "$port" "status")"
  [ -n "$status_json" ] || failed_endpoints+=("status")

  if [ "${#failed_endpoints[@]}" -gt 0 ]; then
    failed_endpoints_json="$(printf '%s\n' "${failed_endpoints[@]}" | jq -R . | jq -sc '.')"
    record_api_failure "$label" "$port" "$prev_bot" "$prev_ok" "$failed_endpoints_json"
    continue
  fi

  open_trades="$(echo "$count_json" | jq -r '.current // 0')"
  total_trades="$(echo "$profit_json" | jq -r '.trade_count // 0')"
  closed_trades="$(echo "$profit_json" | jq -r '.closed_trade_count // 0')"
  profit_all_coin="$(echo "$profit_json" | jq -r '.profit_all_coin // 0')"
  profit_closed_coin="$(echo "$profit_json" | jq -r '.profit_closed_coin // 0')"
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
    --arg profit_closed "$profit_closed_coin" \
    --arg latest "$latest_trade_date" \
    --argjson open_summary "$open_summary" \
    '.[$label] = {
      ok: true,
      api_probe_ok: true,
      consecutive_api_failures: 0,
      state: $state,
      runmode: $runmode,
      strategy: $strategy,
      stake_amount: $stake_amount,
      max_open_trades: $max_open_trades,
      open: $open,
      total: $total,
      closed: $closed,
      profit_all_coin: $profit,
      profit_closed_coin: $profit_closed,
      latest_trade_date: $latest,
      open_summary: $open_summary
    }')"

  if [ "$prev_ok" = "false" ]; then
    append_event "$(jq -n \
      --arg type "api_recovered" \
      --arg label "$label" \
      --arg state "$bot_state" \
      --arg runmode "$runmode" \
      --arg strategy "$strategy" \
      '{type: $type, label: $label, state: $state, runmode: $runmode, strategy: $strategy}')"
  fi

  [ "$prev_bot" != "null" ] || continue

  prev_open="$(echo "$prev_bot" | jq -r '.open // 0')"
  prev_total="$(echo "$prev_bot" | jq -r '.total // 0')"
  prev_closed="$(echo "$prev_bot" | jq -r '.closed // 0')"
  prev_profit_closed_coin="$(echo "$prev_bot" | jq -r '.profit_closed_coin // .profit_all_coin // 0')"
  prev_open_summary="$(echo "$prev_bot" | jq -c '.open_summary // []')"

  new_open=$((open_trades - prev_open))
  new_total=$((total_trades - prev_total))
  new_closed=$((closed_trades - prev_closed))
  closed_profit_delta="$(jq -n \
    --arg current "$profit_closed_coin" \
    --arg previous "$prev_profit_closed_coin" \
    '($current | tonumber) - ($previous | tonumber)')"
  new_open_alerted=0

  if { [ "$new_open" -gt 0 ] || { [ "$open_summary" != "$prev_open_summary" ] && [ "$open_trades" -gt 0 ] && [ "$prev_open" -eq 0 ]; }; }; then
    first_trade="$(echo "$open_summary" | jq -c '.[0]')"
    append_event "$(jq -n \
      --arg type "new_open" \
      --arg label "$label" \
      --argjson open "$open_trades" \
      --argjson total "$total_trades" \
      --argjson closed "$closed_trades" \
      --arg profit_all_coin "$profit_all_coin" \
      --arg latest_trade_date "$latest_trade_date" \
      --argjson trade "$first_trade" \
      '{type: $type, label: $label, open: $open, total: $total, closed: $closed, profit_all_coin: $profit_all_coin, latest_trade_date: $latest_trade_date, trade: $trade}')"
    new_open_alerted=1
  fi

  if [ "$new_closed" -gt 0 ]; then
    append_event "$(jq -n \
      --arg type "closed" \
      --arg label "$label" \
      --argjson closed_delta "$new_closed" \
      --argjson open "$open_trades" \
      --argjson total "$total_trades" \
      --argjson closed "$closed_trades" \
      --arg profit_all_coin "$profit_all_coin" \
      --arg closed_profit_delta "$closed_profit_delta" \
      --arg latest_trade_date "$latest_trade_date" \
      '{type: $type, label: $label, closed_delta: $closed_delta, open: $open, total: $total, closed: $closed, profit_all_coin: $profit_all_coin, closed_profit_delta: $closed_profit_delta, latest_trade_date: $latest_trade_date}')"
  elif [ "$new_total" -gt 0 ] && [ "$new_open_alerted" -eq 0 ]; then
    append_event "$(jq -n \
      --arg type "count_change" \
      --arg label "$label" \
      --argjson open "$open_trades" \
      --argjson total "$total_trades" \
      --argjson closed "$closed_trades" \
      --arg profit_all_coin "$profit_all_coin" \
      --arg latest_trade_date "$latest_trade_date" \
      '{type: $type, label: $label, open: $open, total: $total, closed: $closed, profit_all_coin: $profit_all_coin, latest_trade_date: $latest_trade_date}')"
  fi
done

tmp_state="$(mktemp "${STATE_FILE}.tmp.XXXXXX")"
printf "%s\n" "$current_state" > "$tmp_state"
mv "$tmp_state" "$STATE_FILE"

if [ -n "$changes" ]; then
  echo -e "TRADE_ALERT:${changes}"
fi
