#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1130_observation");
const JSON_OUT = path.join(OUT_DIR, "v1130_watch_only_telemetry_report.json");
const MD_OUT = path.join(OUT_DIR, "v1130_watch_only_telemetry_report.md");
const INPUT_JSON = process.env.V1130_WATCH_ONLY_TELEMETRY_INPUT_JSON || "";

function readJson(file) {
  if (!file) {
    throw new Error("V1130_WATCH_ONLY_TELEMETRY_INPUT_JSON is required");
  }
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function countWhere(rows, predicate) {
  return rows.filter(predicate).length;
}

function byKey(rows, keyFn) {
  const out = {};
  for (const row of rows) {
    const key = keyFn(row);
    out[key] = (out[key] || 0) + 1;
  }
  return out;
}

function normalizeInput(input) {
  const latestRows = input.latest_rows || input.latest || [];
  const windowRows = input.window_rows || [];
  const watchEnabledRows = windowRows.filter((row) => row.watch_enabled === true);
  const strictEnabledRows = windowRows.filter((row) => row.strict_enabled === true);
  const watchOnlyRows = windowRows.filter((row) => row.watch_enabled === true && row.strict_enabled !== true);
  const watchBlockedRows = windowRows.filter((row) => row.watch_candidate === true && row.watch_enabled !== true);
  const strictBlockedRows = windowRows.filter((row) => row.strict_candidate === true && row.strict_enabled !== true);

  return {
    metadata: {
      strategy: "RegimeAwareV1130CrashReboundShadow",
      version: "V11.30",
      report_status: "watch_only_telemetry",
      generated_at: new Date().toISOString(),
      source: input.metadata?.source || "read_only_watch_telemetry_input",
      input_generated_at: input.metadata?.generated_at || null,
      timeframe: input.metadata?.timeframe || "15m",
      pairs: input.metadata?.pairs || [],
      observation_window: input.metadata?.observation_window || "latest_240_candles_per_pair",
      strict_gate: "v1130_crash_rebound_long",
      watch_gate: "v1130_loose_range_watch",
      watch_only_range_threshold: 0.008,
      strict_range_threshold: 0.012,
      can_place_orders: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      reads_secret: false,
      runs_backtest: false,
      writes_sqlite: false,
      starts_or_stops_bot: false,
    },
    data_sources: input.data_sources || [],
    latest_rows: latestRows,
    summary: {
      rows: windowRows.length,
      filter_scope: input.metadata?.filter_scope || "unknown",
      enabled_interpretation: "OHLCV gate pass only; alpha/taker filters are unknown unless provided by input.",
      pairs: input.metadata?.pairs || [...new Set(windowRows.map((row) => row.pair).filter(Boolean))],
      latest_candle_time: latestRows.map((row) => row.candle_time).filter(Boolean).sort().at(-1) || null,
      strict_candidates: countWhere(windowRows, (row) => row.strict_candidate === true),
      strict_enabled: strictEnabledRows.length,
      strict_blocked: strictBlockedRows.length,
      watch_candidates: countWhere(windowRows, (row) => row.watch_candidate === true),
      watch_enabled: watchEnabledRows.length,
      watch_blocked: watchBlockedRows.length,
      watch_only_enabled: watchOnlyRows.length,
      not_candidate: countWhere(windowRows, (row) => row.strict_candidate !== true && row.watch_candidate !== true),
      watch_enabled_by_pair: byKey(watchEnabledRows, (row) => row.pair || "unknown"),
      watch_only_enabled_by_pair: byKey(watchOnlyRows, (row) => row.pair || "unknown"),
      watch_enabled_by_day: byKey(watchEnabledRows, (row) => String(row.candle_time || "unknown").slice(0, 10)),
    },
    observed_runtime: input.observed_runtime || {
      v1130_trades: { state: "unknown", value: null, source: "not_provided" },
      v1130_orders: { state: "unknown", value: null, source: "not_provided" },
      v1130_open_trades: { state: "unknown", value: null, source: "not_provided" },
    },
    watch_only_examples: watchOnlyRows.slice(-20),
    strict_examples: strictEnabledRows.slice(-20),
    blocked_examples: watchBlockedRows.slice(-20),
    limitations: [
      "Watch-only telemetry does not set enter_long and cannot place orders.",
      "This report does not modify the live V11.30 strategy or bot config.",
      "This report does not prove profitability, fill quality, fees, funding, slippage, or latency.",
      "Observed zero trades/orders must not be interpreted as strategy failure without separate cause investigation.",
      "This report does not conclude whether V11.30 can replace V10.8.2.",
    ],
    recommendation: {
      status: "continue_watch_only_observation",
      next_task: "Task 89: V11.30 live observation strict-vs-watch-only comparison",
    },
  };
}

function assertReport(report) {
  const meta = report.metadata;
  const mustBeFalse = [
    "can_place_orders",
    "modifies_strategy",
    "modifies_bot_config",
    "reads_secret",
    "runs_backtest",
    "writes_sqlite",
    "starts_or_stops_bot",
  ];
  for (const key of mustBeFalse) {
    if (meta[key] !== false) {
      throw new Error(`${key} must be false`);
    }
  }
  if (!Array.isArray(report.latest_rows)) {
    throw new Error("latest_rows must be an array");
  }
  for (const row of report.latest_rows) {
    if (row.enter_long === 1 || row.can_place_order === true) {
      throw new Error("watch-only rows must not be order-capable");
    }
  }
}

function markdown(report) {
  const latestRows = report.latest_rows
    .map((row) => `| \`${row.pair}\` | \`${row.candle_time}\` | \`${row.strict_gate || "not_candidate"}\` | \`${row.watch_gate || "not_candidate"}\` | \`${row.watch_enabled === true}\` | \`${(row.failed_strict_conditions || []).join(", ")}\` | \`${(row.failed_watch_conditions || []).join(", ")}\` |`)
    .join("\n") || "| none | none | none | none | false | none | none |";
  const pairRows = Object.entries(report.summary.watch_enabled_by_pair)
    .map(([pair, count]) => `| \`${pair}\` | ${count} |`)
    .join("\n") || "| none | 0 |";
  const dayRows = Object.entries(report.summary.watch_enabled_by_day)
    .map(([day, count]) => `| \`${day}\` | ${count} |`)
    .join("\n") || "| none | 0 |";
  const watchOnlyRows = report.watch_only_examples
    .map((row) => `- \`${row.pair}\` \`${row.candle_time}\` range=\`${row.metrics?.range_ratio ?? "unknown"}\` return=\`${row.metrics?.return_ratio ?? "unknown"}\``)
    .join("\n") || "- none";

  return `# V11.30 Watch-Only Telemetry Report

## Summary

This report records V11.30 strict-gate versus loose-range watch-only telemetry.

It is not a trading signal implementation and cannot place orders.

Here, \`enabled\` means the read-only input passed the OHLCV gate conditions in
the telemetry model. Alpha/taker filters are \`${report.summary.filter_scope}\`,
so this must not be interpreted as a live \`enter_long\` signal.

## Metadata

- strategy: \`${report.metadata.strategy}\`
- version: \`${report.metadata.version}\`
- generated at: \`${report.metadata.generated_at}\`
- input generated at: \`${report.metadata.input_generated_at}\`
- source: \`${report.metadata.source}\`
- timeframe: \`${report.metadata.timeframe}\`
- can place orders: \`${report.metadata.can_place_orders}\`
- modifies strategy: \`${report.metadata.modifies_strategy}\`
- modifies bot config: \`${report.metadata.modifies_bot_config}\`
- reads secret: \`${report.metadata.reads_secret}\`

## Window Summary

| metric | value |
|---|---:|
| rows | ${report.summary.rows} |
| filter scope | ${report.summary.filter_scope} |
| strict candidates | ${report.summary.strict_candidates} |
| strict enabled | ${report.summary.strict_enabled} |
| strict blocked | ${report.summary.strict_blocked} |
| watch candidates | ${report.summary.watch_candidates} |
| watch enabled | ${report.summary.watch_enabled} |
| watch blocked | ${report.summary.watch_blocked} |
| watch-only enabled | ${report.summary.watch_only_enabled} |
| not candidate | ${report.summary.not_candidate} |

## Latest Rows

| pair | candle time | strict gate | watch gate | watch enabled | strict failed | watch failed |
|---|---|---|---|---|---|---|
${latestRows}

## Watch Enabled By Pair

| pair | count |
|---|---:|
${pairRows}

## Watch Enabled By Day

| day | count |
|---|---:|
${dayRows}

## Watch-Only Examples

${watchOnlyRows}

## Runtime Evidence

- V11.30 trades: \`${report.observed_runtime.v1130_trades.value}\` (\`${report.observed_runtime.v1130_trades.state}\`)
- V11.30 orders: \`${report.observed_runtime.v1130_orders.value}\` (\`${report.observed_runtime.v1130_orders.state}\`)
- V11.30 open trades: \`${report.observed_runtime.v1130_open_trades.value}\` (\`${report.observed_runtime.v1130_open_trades.state}\`)

## Limitations

${report.limitations.map((item) => `- ${item}`).join("\n")}

## Recommendation

- status: \`${report.recommendation.status}\`
- next task: ${report.recommendation.next_task}
`;
}

function main() {
  const report = normalizeInput(readJson(INPUT_JSON));
  assertReport(report);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`);
  fs.writeFileSync(MD_OUT, markdown(report));
  console.log(`wrote ${path.relative(ROOT, JSON_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, MD_OUT)}`);
}

main();
