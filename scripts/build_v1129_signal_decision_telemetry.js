#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join("reports", "v1129_execution_validation");
const JSON_OUT = path.join(OUT_DIR, "signal_decision_telemetry_sample.json");
const MD_OUT = path.join(OUT_DIR, "signal_decision_telemetry_sample.md");

const SOURCE_TASK28 = path.join("reports", "audits", "task28_v1129_zero_trade_signal_audit.md");
const SOURCE_TASK29 = path.join("reports", "audits", "task29_v1129_signal_decision_telemetry_plan.md");

const V1129_WHITELIST = [
  "BTC/USDT:USDT",
  "ETH/USDT:USDT",
  "SOL/USDT:USDT",
  "BNB/USDT:USDT",
  "XRP/USDT:USDT",
  "DOGE/USDT:USDT",
  "ADA/USDT:USDT",
  "LINK/USDT:USDT",
  "AVAX/USDT:USDT",
  "LTC/USDT:USDT",
  "TRX/USDT:USDT",
  "BCH/USDT:USDT",
];

function nowShanghaiIso() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day}T${byType.hour}:${byType.minute}:${byType.second}+08:00`;
}

function field(state, value = null, confidence = "unknown", notes = "", sourceRefs = []) {
  return {
    state,
    value,
    confidence,
    notes,
    source_refs: sourceRefs,
  };
}

function requireSource(filePath, marker) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`required source is missing: ${filePath}`);
  }
  const content = fs.readFileSync(filePath, "utf8");
  if (marker && !content.includes(marker)) {
    throw new Error(`required marker not found in ${filePath}: ${marker}`);
  }
  return {
    id: path.basename(filePath, ".md"),
    path: filePath.replace(/\\/g, "/"),
    read_status: "read",
    contains_secret_material: false,
  };
}

function localFallbackFreshness(pair) {
  return [
    {
      observed_at: nowShanghaiIso(),
      pair,
      timeframe: "15m",
      latest_candle: field("observed", "2026-07-03T08:45:00+00:00", "medium", "Latest local futures feather candle recorded in Task 28."),
      source: "local_fallback",
      status: "stale",
      reason:
        "Local downloaded/fallback data is older than the Task 28 observation date. This is a risk signal, not a proven zero-trade cause.",
      source_refs: ["task28_v1129_zero_trade_signal_audit", "task29_v1129_signal_decision_telemetry_plan"],
    },
    {
      observed_at: nowShanghaiIso(),
      pair,
      timeframe: "4h",
      latest_candle: field("observed", "2026-07-03T04:00:00+00:00", "medium", "Latest local futures feather candle recorded in Task 28."),
      source: "local_fallback",
      status: "stale",
      reason:
        "Local downloaded/fallback data is older than the Task 28 observation date. Informative 4h freshness still needs runtime/DataProvider proof.",
      source_refs: ["task28_v1129_zero_trade_signal_audit", "task29_v1129_signal_decision_telemetry_plan"],
    },
    {
      observed_at: nowShanghaiIso(),
      pair,
      timeframe: "runtime_dataprovider",
      latest_candle: field("unknown", null, "unknown", "This generator does not attach to the live bot or exchange DataProvider."),
      source: "dataprovider_live",
      status: "unknown",
      reason:
        "Live DataProvider freshness cannot be proven from clean-worktree audit files alone. A later read-only runtime probe is required.",
      source_refs: ["task29_v1129_signal_decision_telemetry_plan"],
    },
  ];
}

function pairDecision(pair) {
  return {
    observed_at: nowShanghaiIso(),
    pair,
    base_timeframe: "15m",
    informative_timeframes: ["4h"],
    candle_time: field("unknown", null, "unknown", "No generated signal dataframe was read."),
    enter_long: field("unknown", null, "unknown", "No signal dataframe was read."),
    enter_short: field("unknown", null, "unknown", "No signal dataframe was read."),
    enter_tag: field("unknown", null, "unknown", "No signal dataframe was read."),
    raw_signal_count: field("unknown", null, "unknown", "Current V11.29 runtime does not emit signal-level telemetry."),
    gate_results: {
      v1118: field("unknown", null, "unknown", "Gate output not observable from Task 28 logs/API."),
      v1122: field("unknown", null, "unknown", "Gate output not observable from Task 28 logs/API."),
      v1124: field("unknown", null, "unknown", "Gate output not observable from Task 28 logs/API."),
      v1127: field("unknown", null, "unknown", "Gate output not observable from Task 28 logs/API."),
      v1129: field("unknown", null, "unknown", "Gate output not observable from Task 28 logs/API."),
    },
    stake_decision: {
      category: field("unknown", null, "unknown", "No stake callback telemetry was read."),
      secret_free: true,
    },
    not_entered_reason: field(
      "unknown",
      "unknown",
      "unknown",
      "Zero trades/orders are observed in Task 28, but the exact no-entry reason is not proven.",
      ["task28_v1129_zero_trade_signal_audit"],
    ),
  };
}

function buildReport() {
  const task28 = requireSource(SOURCE_TASK28, "V11.29 is running and observable");
  const task29 = requireSource(SOURCE_TASK29, "Task 30: V11.29 Read-Only Signal Telemetry Implementation");

  return {
    metadata: {
      strategy: "RegimeAwareV1129ResidualDragMicroSizer",
      generated_at: nowShanghaiIso(),
      mode: "read_only_signal_telemetry_sample",
      source: "clean_worktree_audit_evidence",
      can_place_orders: false,
      reads_live_server: false,
      reads_sqlite_snapshot: false,
      reads_secret_material: false,
      data_sources: [task28, task29],
      sample_status: "insufficient",
    },
    runtime_context: {
      api_state: field("observed", "running", "medium", "Observed in Task 28 API evidence, not refreshed by this generator.", [
        "task28_v1129_zero_trade_signal_audit",
      ]),
      runmode: field("observed", "dry_run", "medium", "Observed in Task 28 API evidence, not refreshed by this generator.", [
        "task28_v1129_zero_trade_signal_audit",
      ]),
      locks: field("observed", 0, "medium", "Task 28 observed lock_count=0; this generator does not refresh locks.", [
        "task28_v1129_zero_trade_signal_audit",
      ]),
      open_trade_slots: field("observed", { current: 0, max: 4 }, "medium", "Task 28 observed count.current=0 and max=4.", [
        "task28_v1129_zero_trade_signal_audit",
      ]),
      trades_observed: field("observed", 0, "medium", "Task 28 observed V11.29 trades=0.", [
        "task28_v1129_zero_trade_signal_audit",
      ]),
      orders_observed: field("observed", 0, "medium", "Task 28 observed V11.29 orders=0.", [
        "task28_v1129_zero_trade_signal_audit",
      ]),
    },
    data_freshness: V1129_WHITELIST.flatMap(localFallbackFreshness),
    pair_decisions: V1129_WHITELIST.map(pairDecision),
    blocking_gaps: [
      field("missing", "runtime_dataprovider_freshness_probe", "high", "Need safe read-only proof of live candle timestamps per pair/timeframe."),
      field("missing", "signal_dataframe_probe", "high", "Need final enter_long/enter_short/enter_tag evidence per pair/candle."),
      field("missing", "gate_level_reason_probe", "high", "Need evidence of which inherited V11 gate allowed, retagged, or blocked entries."),
      field("missing", "stake_decision_probe", "high", "Need safe category-only custom stake evidence without balances or secrets."),
    ],
    verdict: {
      can_explain_zero_trades: false,
      status: "insufficient",
      reason:
        "This implementation creates the telemetry sample structure from clean audit evidence. It proves local fallback data staleness, but does not prove live DataProvider freshness or the exact no-entry reason.",
      next_required_task: "Task 31: V11.29 Safe Runtime Data Freshness Probe",
    },
  };
}

function assertNoForbiddenClaims(report, markdown) {
  const serialized = `${JSON.stringify(report)}\n${markdown}`;
  const forbidden = [
    "V11.29 passed",
    "V11.29 can replace",
    "V11.29 failed",
    "V11.29 通过真实执行验证",
    "V11.29 可以替换 V10.8.2",
    "策略失败",
  ];
  for (const phrase of forbidden) {
    if (serialized.toLowerCase().includes(phrase.toLowerCase())) {
      throw new Error(`forbidden claim found: ${phrase}`);
    }
  }
}

function assertReport(report) {
  if (report.metadata.can_place_orders !== false) {
    throw new Error("metadata.can_place_orders must be false");
  }
  if (report.metadata.reads_secret_material !== false) {
    throw new Error("metadata.reads_secret_material must be false");
  }
  if (report.metadata.reads_live_server !== false) {
    throw new Error("metadata.reads_live_server must be false");
  }
  if (report.metadata.sample_status !== "insufficient") {
    throw new Error("metadata.sample_status must be insufficient");
  }
  if (report.verdict.can_explain_zero_trades !== false) {
    throw new Error("verdict.can_explain_zero_trades must be false");
  }
  const liveFreshness = report.data_freshness.filter((item) => item.source === "dataprovider_live");
  if (liveFreshness.some((item) => item.status !== "unknown")) {
    throw new Error("dataprovider_live freshness must stay unknown in this sample");
  }
}

function renderMarkdown(report) {
  const staleLocal = report.data_freshness.filter((item) => item.source === "local_fallback" && item.status === "stale").length;
  const liveUnknown = report.data_freshness.filter((item) => item.source === "dataprovider_live" && item.status === "unknown").length;
  const unknownDecisions = report.pair_decisions.filter((item) => item.not_entered_reason.value === "unknown").length;

  return `# V11.29 Signal Decision Telemetry Sample

## Summary

This is a read-only telemetry sample generated from clean-worktree audit
evidence. It does not attach to the live bot, does not read SQLite, does not read
secrets, does not place orders, and does not change strategy or bot
configuration.

- Sample status: \`${report.metadata.sample_status}\`
- Can place orders: \`${report.metadata.can_place_orders}\`
- Reads live server: \`${report.metadata.reads_live_server}\`
- Reads secret material: \`${report.metadata.reads_secret_material}\`
- Can explain zero trades: \`${report.verdict.can_explain_zero_trades}\`

## Data Freshness

Task 28 observed stale local downloaded/fallback futures data:

- Local fallback stale checks: ${staleLocal}
- Live DataProvider freshness checks: ${liveUnknown} marked \`unknown\`
- Whitelist pairs covered: ${V1129_WHITELIST.length}

This means the local downloaded/fallback data set was not real-time updated in
the Task 28 evidence. It does not prove that the running bot lacked live
exchange candles.

## Runtime Context

Runtime context is copied from Task 28 audit evidence and is not refreshed by
this generator:

- API state: \`${report.runtime_context.api_state.value}\`
- Run mode: \`${report.runtime_context.runmode.value}\`
- Observed trades: \`${report.runtime_context.trades_observed.value}\`
- Observed orders: \`${report.runtime_context.orders_observed.value}\`

## Pair Decision Coverage

Pair decision rows generated: ${report.pair_decisions.length}

All pair-level signal decisions remain \`unknown\` because no generated signal
dataframe, strategy callback telemetry, or safe runtime DataProvider probe was
read in this task.

Unknown no-entry reason rows: ${unknownDecisions}

## Blocking Gaps

${report.blocking_gaps.map((gap) => `- \`${gap.value}\`: ${gap.notes}`).join("\n")}

## What This Sample Cannot Conclude

This sample cannot conclude whether V11.29 received fresh live exchange data,
whether any pair produced entry signals, whether inherited V11 gates blocked or
retagged signals, whether stake sizing blocked orders, or whether V11.29 can be
compared with V10.8.2.

## Recommended Next Task

${report.verdict.next_required_task}
`;
}

function main() {
  const report = buildReport();
  assertReport(report);
  const markdown = renderMarkdown(report);
  assertNoForbiddenClaims(report, markdown);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown, "utf8");
  console.log(`wrote ${JSON_OUT}`);
  console.log(`wrote ${MD_OUT}`);
}

main();
