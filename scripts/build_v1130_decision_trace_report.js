#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1130_observation");
const JSON_OUT = path.join(OUT_DIR, "v1130_decision_trace_report.json");
const MD_OUT = path.join(OUT_DIR, "v1130_decision_trace_report.md");
const INPUT_JSON = process.env.V1130_DECISION_TRACE_INPUT_JSON || "";

function readJson(file) {
  if (!file) {
    throw new Error("V1130_DECISION_TRACE_INPUT_JSON is required");
  }
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function state(value, source) {
  if (value === undefined || value === null) {
    return { state: "unknown", value: null, source };
  }
  return { state: "observed", value, source };
}

function buildTraceRows(watchRows) {
  return watchRows.map((row) => ({
    pair: row.pair,
    timeframe: "15m",
    candle_time: row.candle_time,
    source_kind: "watch_only_ohlcv_report",
    strict_gate: row.strict_gate || "unknown",
    watch_gate: row.watch_gate || "unknown",
    return_ratio: state(row.metrics?.return_ratio, "watch_only_telemetry"),
    range_ratio: state(row.metrics?.range_ratio, "watch_only_telemetry"),
    rsi: state(row.metrics?.rsi, "watch_only_telemetry"),
    volume_ratio: state(row.metrics?.volume_ratio, "watch_only_telemetry"),
    alpha_flags: { state: "unknown", value: null, source: "not_available_in_ohlcv_feather" },
    taker_buy_pressure: { state: "unknown", value: null, source: "not_available_in_ohlcv_feather" },
    taker_sell_pressure: { state: "unknown", value: null, source: "not_available_in_ohlcv_feather" },
    pairlist_included: { state: "unknown", value: null, source: "logs_tail_pairlist_not_per_candle" },
    protection_blocked: { state: "unknown", value: null, source: "not_available_in_existing_sources" },
    wallet_or_stake_blocked: { state: "unknown", value: null, source: "not_available_in_existing_sources" },
    max_open_trades_blocked: { state: "unknown", value: null, source: "not_available_in_existing_sources" },
    enter_long: { state: "derived", value: 0, source: "watch_only_report_boundary" },
    enter_tag: { state: "not_applicable", value: "", source: "watch_only_report_boundary" },
    blocked_reason: row.watch_gate === "not_candidate"
      ? { state: "derived", value: row.failed_watch_conditions || [], source: "watch_only_telemetry" }
      : { state: "unknown", value: ["alpha_taker_protection_unknown"], source: "watch_only_telemetry" },
    data_quality: {
      state: "insufficient",
      value: "OHLCV available; alpha/taker/protection decision path unavailable",
      source: "task90_source_plan",
    },
  }));
}

function buildReport(input) {
  const watch = input.watch_only_report;
  if (!watch || !Array.isArray(watch.latest_rows)) {
    throw new Error("input.watch_only_report.latest_rows is required");
  }

  const latestTraceRows = buildTraceRows(watch.latest_rows);
  const strictExamples = buildTraceRows((watch.strict_examples || []).slice(-20));
  const watchOnlyExamples = buildTraceRows((watch.watch_only_examples || []).slice(-20));

  return {
    metadata: {
      strategy: "RegimeAwareV1130CrashReboundShadow",
      version: "V11.30",
      report_status: "decision_trace_from_existing_read_only_sources",
      generated_at: new Date().toISOString(),
      input_generated_at: input.metadata?.generated_at || null,
      can_place_orders: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      reads_secret: false,
      runs_backtest: false,
      writes_sqlite: false,
      starts_or_stops_bot: false,
    },
    sources: input.sources || [],
    runtime: input.runtime || {},
    watch_summary: watch.summary,
    latest_trace_rows: latestTraceRows,
    strict_candidate_examples: strictExamples,
    watch_only_candidate_examples: watchOnlyExamples,
    observed: {
      ohlcv_fields: ["return_ratio", "range_ratio", "rsi", "volume_ratio"],
      v1130_trades: input.runtime?.v1130_trades || watch.observed_runtime?.v1130_trades || null,
      v1130_orders: input.runtime?.v1130_orders || watch.observed_runtime?.v1130_orders || null,
      container_state: input.runtime?.container_state || null,
    },
    derived: {
      latest_strict_gate: latestTraceRows.map((row) => ({ pair: row.pair, gate: row.strict_gate })),
      latest_watch_gate: latestTraceRows.map((row) => ({ pair: row.pair, gate: row.watch_gate })),
      watch_only_candidate_count: watch.summary?.watch_only_enabled ?? null,
    },
    missing_or_unknown: [
      "alpha_flags",
      "taker_buy_pressure",
      "taker_sell_pressure",
      "protection_blocked",
      "wallet_or_stake_blocked",
      "max_open_trades_blocked",
      "live_strategy_final_enter_long_reason",
    ],
    classification: {
      state: "insufficient",
      value: "Existing sources do not expose the final live strategy decision path.",
      next_required_task: "Task 92: V11.30 decision trace observation window",
    },
    limitations: [
      "This collector reads prepared input only and does not connect to exchange APIs.",
      "It does not read secrets or bot configs.",
      "It does not modify strategy behavior or bot runtime state.",
      "It cannot prove alpha/taker/protection blocks without an authorized source.",
      "It cannot conclude whether V11.30 can replace V10.8.2.",
    ],
  };
}

function assertReport(report) {
  for (const key of [
    "can_place_orders",
    "modifies_strategy",
    "modifies_bot_config",
    "reads_secret",
    "runs_backtest",
    "writes_sqlite",
    "starts_or_stops_bot",
  ]) {
    if (report.metadata[key] !== false) {
      throw new Error(`${key} must be false`);
    }
  }
  for (const row of report.latest_trace_rows) {
    if (row.enter_long.value !== 0) {
      throw new Error("decision trace must not emit enter_long=1");
    }
  }
}

function markdown(report) {
  const latestRows = report.latest_trace_rows.map((row) => (
    `| \`${row.pair}\` | \`${row.candle_time}\` | \`${row.strict_gate}\` | \`${row.watch_gate}\` | \`${row.blocked_reason.state}\` | \`${Array.isArray(row.blocked_reason.value) ? row.blocked_reason.value.join(", ") : row.blocked_reason.value}\` |`
  )).join("\n");

  return `# V11.30 Decision Trace Report

## Summary

This report combines existing read-only evidence into a V11.30 decision trace.

Result:

- OHLCV-derived gate fields are available.
- V11.30 runtime counts are available.
- Alpha/taker/protection/final live decision path remains unknown.
- No order-capable behavior is emitted by this report.

## Metadata

- strategy: \`${report.metadata.strategy}\`
- version: \`${report.metadata.version}\`
- generated at: \`${report.metadata.generated_at}\`
- can place orders: \`${report.metadata.can_place_orders}\`
- modifies strategy: \`${report.metadata.modifies_strategy}\`
- modifies bot config: \`${report.metadata.modifies_bot_config}\`
- reads secret: \`${report.metadata.reads_secret}\`

## Latest Decision Trace Rows

| pair | candle time | strict gate | watch gate | blocked state | blocked reason |
|---|---|---|---|---|---|
${latestRows}

## Observed

- OHLCV fields: \`${report.observed.ohlcv_fields.join(", ")}\`
- V11.30 trades: \`${report.observed.v1130_trades?.value ?? "unknown"}\`
- V11.30 orders: \`${report.observed.v1130_orders?.value ?? "unknown"}\`
- container state: \`${report.observed.container_state?.value ?? "unknown"}\`

## Derived

- watch-only candidate count: \`${report.derived.watch_only_candidate_count}\`
- latest strict gates: \`${report.derived.latest_strict_gate.map((item) => `${item.pair}:${item.gate}`).join("; ")}\`
- latest watch gates: \`${report.derived.latest_watch_gate.map((item) => `${item.pair}:${item.gate}`).join("; ")}\`

## Missing Or Unknown

${report.missing_or_unknown.map((item) => `- \`${item}\``).join("\n")}

## Classification

- state: \`${report.classification.state}\`
- value: ${report.classification.value}
- next required task: ${report.classification.next_required_task}

## Limitations

${report.limitations.map((item) => `- ${item}`).join("\n")}
`;
}

function main() {
  const report = buildReport(readJson(INPUT_JSON));
  assertReport(report);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`);
  fs.writeFileSync(MD_OUT, markdown(report));
  console.log(`wrote ${path.relative(ROOT, JSON_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, MD_OUT)}`);
}

main();
