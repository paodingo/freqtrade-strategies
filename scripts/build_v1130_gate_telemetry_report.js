#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1130_observation");
const JSON_OUT = path.join(OUT_DIR, "v1130_gate_telemetry_report.json");
const MD_OUT = path.join(OUT_DIR, "v1130_gate_telemetry_report.md");

const PAIRS = [
  "ETH/USDT:USDT",
  "SOL/USDT:USDT",
  "DOGE/USDT:USDT",
  "LINK/USDT:USDT",
  "XRP/USDT:USDT",
  "BCH/USDT:USDT",
];

const latest = [
  {
    pair: "ETH/USDT:USDT",
    candle_time: "2026-07-08T03:00:00Z",
    gate: "not_candidate",
    enter_long: 0,
    enter_short: 0,
    enter_tag: "",
    failed_conditions: ["return", "range"],
    alpha_flags: [
      "longCrowding",
      "topTraderAccountLongCrowding",
      "takerSellPressure",
    ],
    metrics: {
      return_ratio: 0.0025158,
      range_ratio: 0.0033384,
      rsi: 41.37,
      volume_ratio: 0.881,
    },
  },
  {
    pair: "SOL/USDT:USDT",
    candle_time: "2026-07-08T03:00:00Z",
    gate: "not_candidate",
    enter_long: 0,
    enter_short: 0,
    enter_tag: "",
    failed_conditions: ["return", "range", "rsi"],
    alpha_flags: ["takerSellPressure"],
    metrics: {
      return_ratio: 0.002531,
      range_ratio: 0.0037869,
      rsi: 30.19,
      volume_ratio: 0.96,
    },
  },
  {
    pair: "DOGE/USDT:USDT",
    candle_time: "2026-07-08T03:00:00Z",
    gate: "not_candidate",
    enter_long: 0,
    enter_short: 0,
    enter_tag: "",
    failed_conditions: ["return", "range", "rsi", "volume"],
    alpha_flags: ["takerSellPressure"],
    metrics: {
      return_ratio: 0.0019207,
      range_ratio: 0.0028755,
      rsi: 32.95,
      volume_ratio: 0.73,
    },
  },
  {
    pair: "LINK/USDT:USDT",
    candle_time: "2026-07-08T03:00:00Z",
    gate: "not_candidate",
    enter_long: 0,
    enter_short: 0,
    enter_tag: "",
    failed_conditions: ["return", "range", "rsi", "volume"],
    alpha_flags: ["takerSellPressure"],
    metrics: {
      return_ratio: 0.0027223,
      range_ratio: 0.0032321,
      rsi: 34.33,
      volume_ratio: 0.714,
    },
  },
  {
    pair: "XRP/USDT:USDT",
    candle_time: "2026-07-08T03:00:00Z",
    gate: "not_candidate",
    enter_long: 0,
    enter_short: 0,
    enter_tag: "",
    failed_conditions: ["return", "range", "volume"],
    alpha_flags: ["takerSellPressure"],
    metrics: {
      return_ratio: 0.0029094,
      range_ratio: 0.0034448,
      rsi: 39.64,
      volume_ratio: 0.767,
    },
  },
  {
    pair: "BCH/USDT:USDT",
    candle_time: "2026-07-08T03:00:00Z",
    gate: "not_candidate",
    enter_long: 0,
    enter_short: 0,
    enter_tag: "",
    failed_conditions: ["return", "range"],
    alpha_flags: ["takerSellPressure"],
    metrics: {
      return_ratio: 0.0018433,
      range_ratio: 0.0043071,
      rsi: 47.26,
      volume_ratio: 0.879,
    },
  },
];

const enabledExamples = [
  ["ETH/USDT:USDT", "2026-07-07T14:45:00Z"],
  ["SOL/USDT:USDT", "2026-07-06T13:30:00Z"],
  ["SOL/USDT:USDT", "2026-07-07T14:45:00Z"],
  ["DOGE/USDT:USDT", "2026-07-06T15:30:00Z"],
  ["DOGE/USDT:USDT", "2026-07-06T16:00:00Z"],
  ["LINK/USDT:USDT", "2026-07-07T14:45:00Z"],
  ["XRP/USDT:USDT", "2026-07-07T14:45:00Z"],
  ["BCH/USDT:USDT", "2026-07-06T02:15:00Z"],
  ["BCH/USDT:USDT", "2026-07-07T14:45:00Z"],
].map(([pair, candle_time]) => ({
  pair,
  candle_time,
  gate: "enabled_crash_rebound_long",
  enter_long: 1,
  enter_tag: "v1130_crash_rebound_long",
}));

function buildReport() {
  return {
    metadata: {
      strategy: "RegimeAwareV1130CrashReboundShadow",
      version: "V11.30",
      generated_at: new Date().toISOString(),
      report_status: "gate_telemetry_from_audited_replay",
      source: "task68_read_only_gate_replay",
      timeframe: "15m",
      pairs: PAIRS,
      can_place_orders: false,
      modifies_bot: false,
      reads_secret: false,
      runs_backtest: false,
      downloads_or_refreshes_data: false,
    },
    data_sources: [
      {
        id: "task68",
        path: "reports/audits/task68_v1130_live_gate_replay_latest_candles.md",
        kind: "read_only_gate_replay_audit",
      },
      {
        id: "task72",
        path: "reports/audits/task72_v1130_observation_window_extension.md",
        kind: "read_only_runtime_observation_audit",
      },
    ],
    latest,
    window_summary: {
      rows: 1440,
      rows_per_pair: 240,
      gate_counts: {
        not_candidate: 1429,
        enabled_crash_rebound_long: 9,
        blocked_taker_sell_pressure: 2,
      },
      raw_fail_counts: {
        range: 1400,
        return: 1322,
        volume: 688,
        rsi: 362,
      },
      enabled_examples: enabledExamples,
    },
    zero_trade_interpretation: {
      v1130_sqlite_trades: {
        state: "observed",
        value: 0,
        source_ref: "task72",
        note: "Observed SQLite count; not a strategy failure conclusion.",
      },
      v1130_sqlite_orders: {
        state: "observed",
        value: 0,
        source_ref: "task72",
        note: "Observed SQLite count; not a strategy failure conclusion.",
      },
      latest_gate_status: {
        state: "derived",
        value: "all_latest_checked_pairs_not_candidate",
        source_ref: "task68",
        note: "Latest checked candle did not pass the V11.30 gate for any checked pair.",
      },
    },
    limitations: [
      "This report is generated from audited replay evidence, not from a live V11.30 API.",
      "It does not download or refresh market data.",
      "It does not read secrets, strategies, bot configs, or live SQLite content.",
      "It does not prove profitability or replacement readiness.",
    ],
    recommended_next_tasks: [
      "Task 77: V11.30 post-refresh gate telemetry rerun after approved data maintenance",
      "Task 78: V11.30 live observation window with persisted gate telemetry",
    ],
  };
}

function assertReport(report) {
  if (report.metadata.can_place_orders !== false) {
    throw new Error("can_place_orders must be false");
  }
  if (report.metadata.reads_secret !== false) {
    throw new Error("reads_secret must be false");
  }
  if (report.metadata.runs_backtest !== false) {
    throw new Error("runs_backtest must be false");
  }
  if (report.metadata.downloads_or_refreshes_data !== false) {
    throw new Error("downloads_or_refreshes_data must be false");
  }
  if (report.latest.length !== PAIRS.length) {
    throw new Error("latest must contain one row per pair");
  }
  if (!report.latest.every((row) => row.gate === "not_candidate")) {
    throw new Error("latest rows must preserve audited not_candidate state");
  }
}

function markdown(report) {
  const latestRows = report.latest
    .map((row) => `| \`${row.pair}\` | \`${row.candle_time}\` | \`${row.gate}\` | \`${row.failed_conditions.join(", ")}\` |`)
    .join("\n");
  const gateRows = Object.entries(report.window_summary.gate_counts)
    .map(([gate, count]) => `| \`${gate}\` | ${count} |`)
    .join("\n");
  const failRows = Object.entries(report.window_summary.raw_fail_counts)
    .map(([condition, count]) => `| \`${condition}\` | ${count} |`)
    .join("\n");
  const examples = report.window_summary.enabled_examples
    .map((item) => `- \`${item.pair}\` at \`${item.candle_time}\``)
    .join("\n");

  return `# V11.30 Gate Telemetry Report

## Summary

This report persists the audited Task 68 V11.30 gate replay evidence into JSON
and Markdown artifacts.

Conclusion:

- latest checked candle gate state: \`not_candidate\` for all checked pairs;
- window-level replay found \`9\` enabled crash-rebound examples;
- V11.30 SQLite zero trades/orders from Task 72 remains insufficient evidence;
- this report does not prove profitability or replacement readiness.

## Metadata

- strategy: \`${report.metadata.strategy}\`
- version: \`${report.metadata.version}\`
- generated at: \`${report.metadata.generated_at}\`
- source: \`${report.metadata.source}\`
- timeframe: \`${report.metadata.timeframe}\`
- can place orders: \`${report.metadata.can_place_orders}\`
- reads secret: \`${report.metadata.reads_secret}\`
- runs backtest: \`${report.metadata.runs_backtest}\`
- downloads or refreshes data: \`${report.metadata.downloads_or_refreshes_data}\`

## Latest Candle Gate State

| pair | candle time | gate | failed conditions |
|---|---|---|---|
${latestRows}

## Window Gate Counts

| gate | count |
|---|---:|
${gateRows}

## Raw Fail Counts

| condition | count |
|---|---:|
${failRows}

## Enabled Examples

${examples}

## Zero-Trade Interpretation

- V11.30 trades: \`${report.zero_trade_interpretation.v1130_sqlite_trades.value}\` observed in Task 72.
- V11.30 orders: \`${report.zero_trade_interpretation.v1130_sqlite_orders.value}\` observed in Task 72.
- These are observed counts, not a strategy failure conclusion.
- The latest checked candles did not qualify for entry in the audited replay.

## Limitations

${report.limitations.map((item) => `- ${item}`).join("\n")}

## Recommended Next Tasks

${report.recommended_next_tasks.map((item) => `- ${item}`).join("\n")}
`;
}

function main() {
  const report = buildReport();
  assertReport(report);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`);
  fs.writeFileSync(MD_OUT, markdown(report));
  console.log(`wrote ${path.relative(ROOT, JSON_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, MD_OUT)}`);
}

main();
