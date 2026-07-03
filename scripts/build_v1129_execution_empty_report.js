#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join("reports", "v1129_execution_validation");
const JSON_OUT = path.join(OUT_DIR, "sample_empty_report.json");
const MD_OUT = path.join(OUT_DIR, "sample_empty_report.md");

function field(state, value = null, unit = null, confidence = "unknown", notes = "", sourceRefs = []) {
  return {
    state,
    value,
    unit,
    source_refs: sourceRefs,
    confidence,
    notes,
  };
}

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

function buildReport() {
  const dataSources = [
    {
      id: "schema_doc",
      kind: "other",
      path_or_endpoint: "docs/harness/v1129_execution_report_schema.md",
      read_status: "read",
      trust_level: "high",
      contains_secret_material: false,
      notes: "Schema contract only; not a real execution source.",
    },
    {
      id: "task12_inventory",
      kind: "other",
      path_or_endpoint: "reports/audits/task12_v1129_execution_data_inventory.md",
      read_status: "read",
      trust_level: "medium",
      contains_secret_material: false,
      notes: "Path-level inventory said real V11.29 trade samples were not verified.",
    },
    {
      id: "task13_schema_audit",
      kind: "other",
      path_or_endpoint: "reports/audits/task13_v1129_execution_report_schema.md",
      read_status: "read",
      trust_level: "medium",
      contains_secret_material: false,
      notes: "Task 13 required insufficient/missing/unknown wording for sample-limited reports.",
    },
  ];

  const unknownTradeCountNote = "No verified DB/API/monitor export was read. Do not infer a numeric count.";
  const collectionTask = "Task 15: V11.29 Execution Data Locator and Collection Plan";

  return {
    metadata: {
      strategy: field(
        "unknown",
        "RegimeAwareV1129ResidualDragMicroSizer",
        null,
        "low",
        "Name is path-derived from prior inventory; runtime use was not verified.",
      ),
      version: field("unknown", "V11.29", null, "low", "Version label is not verified against a running bot."),
      report_time: nowShanghaiIso(),
      observation_window: {
        start: null,
        end: null,
        timezone: "Asia/Shanghai",
        state: "unknown",
        notes: "No verified execution window is available in this empty sample.",
      },
      data_sources: dataSources,
      sample_status: "insufficient",
    },
    bot_runtime: {
      running_state: field("unknown", null, null, "unknown", "No bot runtime API or monitor export was read."),
      uptime: field("unknown", null, "seconds", "unknown", "No uptime source was read."),
      stopped_alerts: field("unknown", null, "alerts", "unknown", "No alert history source was read."),
      api_errors: field("unknown", null, "events", "unknown", "No API health history source was read."),
      jq_parse_errors: field("unknown", null, "events", "unknown", "No trade-monitor alert history source was read."),
      data_quality: field("derived", "insufficient", null, "medium", "Derived from missing verified execution samples.", [
        "task12_inventory",
      ]),
    },
    execution_samples: {
      total_trades: field("unknown", null, "trades", "unknown", unknownTradeCountNote),
      open_trades: field("unknown", null, "trades", "unknown", unknownTradeCountNote),
      closed_trades: field("unknown", null, "trades", "unknown", unknownTradeCountNote),
      sample_1d: field("unknown", null, "trades", "unknown", "No verified 1d execution window was read."),
      sample_7d: field("unknown", null, "trades", "unknown", "No verified 7d execution window was read."),
      sample_14d: field("unknown", null, "trades", "unknown", "No verified 14d execution window was read."),
      sample_sufficiency: field("derived", "insufficient", null, "medium", "No verified trade sample source is available.", [
        "task12_inventory",
        "task13_schema_audit",
      ]),
    },
    trade_execution_quality: {
      order_price: field("missing", null, null, "medium", "Requires verified order source."),
      expected_price: field("missing", null, null, "medium", "Requires verified signal snapshot source."),
      filled_price: field("missing", null, null, "medium", "Requires verified fill source."),
      slippage_bps: field("unknown", null, "bps", "unknown", "Requires observed expected and filled prices."),
      fee: field("missing", null, null, "medium", "Requires verified trade/order fee source."),
      funding_fee: field("unknown", null, null, "unknown", "Requires verified per-trade futures funding source."),
      latency: field("unknown", null, "seconds", "unknown", "Requires signal/order/fill timestamps."),
      unfilled_signals: field("unknown", null, "signals", "unknown", "Requires verified signal and order status sources."),
      blocked_signals: field("unknown", null, "signals", "unknown", "Requires verified supervisor or opportunity audit source."),
    },
    strategy_behavior: {
      pair: field("missing", null, null, "medium", "Requires verified trade samples."),
      side: field("missing", null, null, "medium", "Requires verified trade samples."),
      entry_tag: field("missing", null, null, "medium", "Requires verified trade samples."),
      exit_reason: field("missing", null, null, "medium", "Requires verified closed trade samples."),
      open_time: field("missing", null, null, "medium", "Requires verified trade samples."),
      close_time: field("missing", null, null, "medium", "Requires verified closed trade samples."),
      pnl: field("unknown", null, null, "unknown", "Requires verified closed trade samples."),
      pnl_ratio: field("unknown", null, "ratio", "unknown", "Requires verified closed trade samples."),
    },
    benchmark_comparison: {
      v1082_data_availability: field("unknown", null, null, "unknown", "No same-window V10.8.2 execution source was read."),
      same_window_comparison_availability: field(
        "missing",
        null,
        null,
        "medium",
        "No verified same-window V11.29 and V10.8.2 execution samples are available.",
      ),
      comparison_1d_status: field("unknown", null, null, "unknown", "No verified 1d comparison window."),
      comparison_7d_status: field("unknown", null, null, "unknown", "No verified 7d comparison window."),
      comparison_14d_status: field("unknown", null, null, "unknown", "No verified 14d comparison window."),
      cannot_compare_reason: field(
        "derived",
        "Missing verified same-window execution samples for both versions.",
        null,
        "medium",
        "Replacement evaluation is disabled in this empty sample.",
        ["task12_inventory", "task13_schema_audit"],
      ),
    },
    data_gaps: {
      missing_fields: [
        field("missing", "order_price", null, "medium", "No verified order source."),
        field("missing", "fee", null, "medium", "No verified fee source."),
        field("missing", "pair/side/open_time/close_time", null, "medium", "No verified trade source."),
      ],
      unverified_fields: [
        field("unknown", "bot_runtime", null, "unknown", "No runtime monitor/API export was read."),
        field("unknown", "sample_1d/sample_7d/sample_14d", null, "unknown", "No verified execution windows."),
        field("unknown", "funding_fee/slippage_bps/latency", null, "unknown", "No source chain for these calculations."),
      ],
      required_new_collection: [
        field("missing", "freqtrade_trade_order_export", null, "medium", "Locate and export read-only DB/API trade and order fields."),
        field("missing", "monitor_history_schema", null, "medium", "Inspect monitor history structure in a separate task."),
        field("missing", "same_window_v1082_v1129_samples", null, "medium", "Define and locate comparable execution windows."),
      ],
      blocking_gaps: [
        field("missing", "verified_v1129_trade_samples", null, "medium", "Required before generating a real execution report."),
        field("missing", "verified_v1082_same_window_samples", null, "medium", "Required before replacement evaluation."),
      ],
    },
    verdict: {
      report_status: "blocked_by_missing_data",
      can_generate_execution_report: field(
        "derived",
        false,
        null,
        "medium",
        "Only an empty insufficient sample can be generated until verified execution data is located.",
        ["schema_doc", "task12_inventory"],
      ),
      can_evaluate_replacement: field(
        "derived",
        false,
        null,
        "medium",
        "Same-window V11.29 and V10.8.2 execution evidence is not verified.",
        ["task12_inventory", "task13_schema_audit"],
      ),
      reason: field(
        "derived",
        "Insufficient verified execution samples. This file is an empty report sample, not a real execution verdict.",
        null,
        "medium",
        "Do not use this sample for replacement decisions.",
        ["task12_inventory", "task13_schema_audit"],
      ),
      next_required_task: field(
        "derived",
        collectionTask,
        null,
        "medium",
        "Locate read-only execution data sources before generating a real report.",
        ["task12_inventory"],
      ),
    },
  };
}

function assertNoZeroValues(value, pathParts = []) {
  if (value === 0) {
    throw new Error(`unexpected numeric zero at ${pathParts.join(".")}`);
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoZeroValues(item, [...pathParts, String(index)]));
    return;
  }
  if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      assertNoZeroValues(child, [...pathParts, key]);
    }
  }
}

function validateReport(report, markdown) {
  if (report.metadata.sample_status !== "insufficient") {
    throw new Error("sample_status must be insufficient");
  }
  if (report.verdict.can_generate_execution_report.value !== false) {
    throw new Error("can_generate_execution_report must be false");
  }
  if (report.verdict.can_evaluate_replacement.value !== false) {
    throw new Error("can_evaluate_replacement must be false");
  }
  assertNoZeroValues(report);

  const forbidden = [["V11.29", "通过真实执行验证"].join(" "), ["没有", "交易"].join("")];
  const serialized = `${JSON.stringify(report)}\n${markdown}`;
  for (const phrase of forbidden) {
    if (serialized.includes(phrase)) {
      throw new Error(`forbidden phrase found: ${phrase}`);
    }
  }
}

function renderMarkdown(report) {
  return `# V11.29 Execution Validation: Empty Sample Report

## Summary

This is an empty/insufficient sample generated from the harness schema. It is not
a real execution report and does not evaluate whether V11.29 can replace
V10.8.2.

- Report status: \`${report.verdict.report_status}\`
- Sample status: \`${report.metadata.sample_status}\`
- Can generate real execution report: \`${report.verdict.can_generate_execution_report.value}\`
- Can evaluate replacement: \`${report.verdict.can_evaluate_replacement.value}\`

## Data availability

The generator did not read a trade DB, exchange API, dashboard API, monitor DB,
secret file, server, or bot runtime. The only inputs are documentation and audit
contracts already in the clean harness worktree.

## Execution sample status

- Total trades: \`${report.execution_samples.total_trades.state}\`
- Open trades: \`${report.execution_samples.open_trades.state}\`
- Closed trades: \`${report.execution_samples.closed_trades.state}\`
- 1d sample: \`${report.execution_samples.sample_1d.state}\`
- 7d sample: \`${report.execution_samples.sample_7d.state}\`
- 14d sample: \`${report.execution_samples.sample_14d.state}\`

## Runtime health

Runtime health is \`${report.bot_runtime.running_state.state}\` because no
verified runtime monitor/API export was read. This sample must not be used as a
runtime health claim.

## Execution quality

Order price, expected price, filled price, fee, funding fee, slippage, latency,
unfilled signals, and blocked signals are marked as \`missing\` or \`unknown\`
until verified execution data is located.

## V10.8.2 comparison readiness

Same-window comparison availability is
\`${report.benchmark_comparison.same_window_comparison_availability.state}\`.
Replacement evaluation remains disabled.

## Missing data

Required missing or unverified sources include:

- verified V11.29 trade/order export
- verified fee and funding source
- verified runtime/API health history
- verified signal/order/fill timing chain
- verified same-window V10.8.2 execution samples

## Blocking gaps

Blocking gaps are:

- ${report.data_gaps.blocking_gaps.map((item) => item.value).join("\n- ")}

## What this report cannot conclude

This sample cannot conclude that V11.29 has run, produced open or closed
execution samples, has acceptable execution quality, has healthy runtime state,
or can replace V10.8.2.

## Recommended next task

${report.verdict.next_required_task.value}
`;
}

function main() {
  const report = buildReport();
  const markdown = renderMarkdown(report);
  validateReport(report, markdown);

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown, "utf8");
  console.log(`wrote ${JSON_OUT}`);
  console.log(`wrote ${MD_OUT}`);
}

main();
