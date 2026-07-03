#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { DatabaseSync } = require("node:sqlite");

const SNAPSHOT_DIR = path.join("reports", "v1129_execution_validation", "snapshots");
const OUT_DIR = path.join("reports", "v1129_execution_validation");
const V1129_DB = path.join(SNAPSHOT_DIR, "tradesv3_v1129.snapshot.sqlite");
const V1082_DB = path.join(SNAPSHOT_DIR, "tradesv3_v1082.snapshot.sqlite");
const JSON_OUT = path.join(OUT_DIR, "v1129_snapshot_insufficient_report.json");
const MD_OUT = path.join(OUT_DIR, "v1129_snapshot_insufficient_report.md");

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

function fileInfo(filePath) {
  const buffer = fs.readFileSync(filePath);
  return {
    path: filePath.replace(/\\/g, "/"),
    size_bytes: buffer.length,
    sha256: crypto.createHash("sha256").update(buffer).digest("hex").toUpperCase(),
  };
}

function openReadOnlySqlite(filePath) {
  const db = new DatabaseSync(filePath, { readOnly: true });
  db.exec("PRAGMA query_only = ON");
  return db;
}

function getScalar(db, sql) {
  const row = db.prepare(sql).get();
  return row ? Object.values(row)[0] : null;
}

function getTables(db) {
  return db
    .prepare("select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name")
    .all()
    .map((row) => row.name);
}

function getColumns(db, table) {
  return db.prepare(`PRAGMA table_info("${table.replaceAll('"', '""')}")`).all().map((row) => row.name);
}

function tableExists(tables, table) {
  return tables.includes(table);
}

function inspectSnapshot(label, filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`missing snapshot: ${filePath}`);
  }

  const info = fileInfo(filePath);
  const db = openReadOnlySqlite(filePath);
  try {
    const tables = getTables(db);
    const tradesExists = tableExists(tables, "trades");
    const ordersExists = tableExists(tables, "orders");
    const tradesColumns = tradesExists ? getColumns(db, "trades") : [];
    const ordersColumns = ordersExists ? getColumns(db, "orders") : [];

    return {
      label,
      file: info,
      tables,
      trades: {
        table_exists: tradesExists,
        columns: tradesColumns,
        total: tradesExists ? getScalar(db, "select count(*) from trades") : null,
        open: tradesExists && tradesColumns.includes("is_open") ? getScalar(db, "select count(*) from trades where is_open = 1") : null,
        closed:
          tradesExists && tradesColumns.includes("is_open")
            ? getScalar(db, "select count(*) from trades where is_open = 0")
            : null,
        earliest_open_date:
          tradesExists && tradesColumns.includes("open_date") ? getScalar(db, "select min(open_date) from trades") : null,
        latest_open_date:
          tradesExists && tradesColumns.includes("open_date") ? getScalar(db, "select max(open_date) from trades") : null,
        latest_close_date:
          tradesExists && tradesColumns.includes("close_date")
            ? getScalar(db, "select max(close_date) from trades where close_date is not null")
            : null,
      },
      orders: {
        table_exists: ordersExists,
        columns: ordersColumns,
        total: ordersExists ? getScalar(db, "select count(*) from orders") : null,
        open: ordersExists && ordersColumns.includes("ft_is_open") ? getScalar(db, "select count(*) from orders where ft_is_open = 1") : null,
        closed:
          ordersExists && ordersColumns.includes("ft_is_open")
            ? getScalar(db, "select count(*) from orders where ft_is_open = 0")
            : null,
      },
    };
  } finally {
    db.close();
  }
}

function observedCount(value, unit, sourceRefs, notes) {
  return field("observed", value, unit, "high", notes, sourceRefs);
}

function buildReport() {
  const v1129 = inspectSnapshot("V11.29", V1129_DB);
  const v1082 = inspectSnapshot("V10.8.2", V1082_DB);
  const sampleStatus = v1129.trades.total === 0 || v1129.orders.total === 0 ? "insufficient" : "unknown";

  const dataSources = [
    {
      id: "schema_doc",
      kind: "other",
      path_or_endpoint: "docs/harness/v1129_execution_report_schema.md",
      read_status: "read",
      trust_level: "high",
      contains_secret_material: false,
      notes: "Schema contract read before generating this report.",
    },
    {
      id: "task17_sqlite_inspection",
      kind: "other",
      path_or_endpoint: "reports/audits/task17_v1129_sqlite_snapshot_schema_inspection.md",
      read_status: "read",
      trust_level: "high",
      contains_secret_material: false,
      notes: "Task 17 established that V11.29 trades/orders row counts are insufficient.",
    },
    {
      id: "v1129_snapshot_sqlite",
      kind: "sqlite",
      path_or_endpoint: v1129.file.path,
      read_status: "read",
      trust_level: "high",
      contains_secret_material: false,
      notes: `Read-only SQLite snapshot. SHA256 ${v1129.file.sha256}.`,
    },
    {
      id: "v1082_snapshot_sqlite",
      kind: "sqlite",
      path_or_endpoint: v1082.file.path,
      read_status: "read",
      trust_level: "high",
      contains_secret_material: false,
      notes: `Read-only SQLite snapshot. SHA256 ${v1082.file.sha256}.`,
    },
  ];

  return {
    metadata: {
      strategy: field(
        "unknown",
        "RegimeAwareV1129ResidualDragMicroSizer",
        null,
        "low",
        "Version and strategy label are inventory-derived; this report did not verify the running bot config.",
      ),
      version: field("observed", "V11.29", null, "medium", "Version label comes from the snapshot/report scope.", [
        "v1129_snapshot_sqlite",
      ]),
      report_time: nowShanghaiIso(),
      observation_window: {
        start: null,
        end: null,
        timezone: "Asia/Shanghai",
        state: "missing",
        notes: "V11.29 snapshot has no trade rows, so no V11.29 execution window can be derived.",
      },
      data_sources: dataSources,
      sample_status: sampleStatus,
    },
    snapshot_summary: {
      v1129: v1129,
      v1082: v1082,
    },
    bot_runtime: {
      running_state: field("unknown", null, null, "unknown", "SQLite snapshots do not prove current bot runtime state."),
      uptime: field("unknown", null, "seconds", "unknown", "SQLite snapshots do not provide bot uptime."),
      stopped_alerts: field("unknown", null, "alerts", "unknown", "Alert history was not read in this task."),
      api_errors: field("unknown", null, "events", "unknown", "API health history was not read in this task."),
      jq_parse_errors: field("unknown", null, "events", "unknown", "Trade monitor alert history was not read in this task."),
      data_quality: field("derived", "insufficient", null, "high", "Derived from observed V11.29 trades/orders counts.", [
        "v1129_snapshot_sqlite",
      ]),
    },
    execution_samples: {
      total_trades: observedCount(
        v1129.trades.total,
        "trades",
        ["v1129_snapshot_sqlite"],
        "Observed from read-only SQLite query: select count(*) from trades.",
      ),
      open_trades: observedCount(
        v1129.trades.open,
        "trades",
        ["v1129_snapshot_sqlite"],
        "Observed from read-only SQLite query filtering is_open = 1.",
      ),
      closed_trades: observedCount(
        v1129.trades.closed,
        "trades",
        ["v1129_snapshot_sqlite"],
        "Observed from read-only SQLite query filtering is_open = 0.",
      ),
      total_orders: observedCount(
        v1129.orders.total,
        "orders",
        ["v1129_snapshot_sqlite"],
        "Observed from read-only SQLite query: select count(*) from orders.",
      ),
      sample_1d: field("derived", "insufficient", "trades", "high", "No V11.29 trade rows exist in the snapshot.", [
        "v1129_snapshot_sqlite",
      ]),
      sample_7d: field("derived", "insufficient", "trades", "high", "No V11.29 trade rows exist in the snapshot.", [
        "v1129_snapshot_sqlite",
      ]),
      sample_14d: field("derived", "insufficient", "trades", "high", "No V11.29 trade rows exist in the snapshot.", [
        "v1129_snapshot_sqlite",
      ]),
      sample_sufficiency: field("derived", "insufficient", null, "high", "V11.29 trades/orders observed row counts are both zero.", [
        "v1129_snapshot_sqlite",
      ]),
    },
    trade_execution_quality: {
      order_price: field("missing", null, null, "high", "V11.29 orders table exists but has no rows; value-level order price cannot be verified.", [
        "v1129_snapshot_sqlite",
      ]),
      expected_price: field("unknown", null, null, "unknown", "No signal expected-price source was read."),
      filled_price: field("missing", null, null, "high", "V11.29 orders table exists but has no rows; filled price cannot be verified.", [
        "v1129_snapshot_sqlite",
      ]),
      slippage_bps: field("missing", null, "bps", "high", "No V11.29 order/fill rows; slippage must not be calculated."),
      fee: field("missing", null, null, "high", "V11.29 trades/orders have no rows; fee quality must not be calculated."),
      funding_fee: field("missing", null, null, "high", "V11.29 trades/orders have no rows; funding fee cannot be verified."),
      latency: field("missing", null, "seconds", "high", "V11.29 orders table has no rows; latency quality must not be calculated."),
      unfilled_signals: field("unknown", null, "signals", "unknown", "No signal/order rejection source was read."),
      blocked_signals: field("unknown", null, "signals", "unknown", "No supervisor/opportunity-audit source was read."),
    },
    strategy_behavior: {
      pair: field("missing", null, null, "high", "V11.29 trade table has no rows to inspect."),
      side: field("missing", null, null, "high", "V11.29 trade table has no rows to inspect."),
      entry_tag: field("missing", null, null, "high", "V11.29 trade table has no rows to inspect."),
      exit_reason: field("missing", null, null, "high", "V11.29 closed-trade rows are absent."),
      open_time: field("missing", null, null, "high", "V11.29 trade table has no rows to inspect."),
      close_time: field("missing", null, null, "high", "V11.29 closed-trade rows are absent."),
      pnl: field("missing", null, null, "high", "No V11.29 closed-trade rows; PnL must not be calculated."),
      pnl_ratio: field("missing", null, "ratio", "high", "No V11.29 closed-trade rows; PnL ratio must not be calculated."),
    },
    benchmark_comparison: {
      v1082_data_availability: field(
        "observed",
        {
          closed_trades: v1082.trades.closed,
          orders: v1082.orders.total,
          earliest_open_date: v1082.trades.earliest_open_date,
          latest_close_date: v1082.trades.latest_close_date,
        },
        null,
        "high",
        "V10.8.2 benchmark data availability only; no performance comparison is computed.",
        ["v1082_snapshot_sqlite"],
      ),
      same_window_comparison_availability: field(
        "derived",
        false,
        null,
        "high",
        "V11.29 has no observed trade/order rows in the snapshot, so same-window execution quality comparison is unavailable.",
        ["v1129_snapshot_sqlite", "v1082_snapshot_sqlite"],
      ),
      comparison_1d_status: field("derived", "insufficient", null, "high", "No V11.29 1d execution sample."),
      comparison_7d_status: field("derived", "insufficient", null, "high", "No V11.29 7d execution sample."),
      comparison_14d_status: field("derived", "insufficient", null, "high", "No V11.29 14d execution sample."),
      cannot_compare_reason: field(
        "derived",
        "V11.29 snapshot trades/orders row counts are zero; V10.8.2 has benchmark rows but lacks a comparable V11.29 window.",
        null,
        "high",
        "This report records benchmark availability only and does not compare performance.",
        ["v1129_snapshot_sqlite", "v1082_snapshot_sqlite"],
      ),
    },
    data_gaps: {
      missing_fields: [],
      unverified_fields: [
        field("unknown", "bot_runtime_state", null, "unknown", "Not provable from SQLite snapshots alone."),
        field("unknown", "api_errors/jq_parse_errors/stopped_alerts", null, "unknown", "Monitor/API/log sources were not read."),
        field("unknown", "unfilled_signals/blocked_signals", null, "unknown", "Signal/supervisor sources were not read."),
      ],
      required_new_collection: [
        field("missing", "v1129_zero_trade_cause_evidence", null, "medium", "Need to explain why V11.29 produced no trades/orders in the snapshot."),
        field("missing", "v1129_trade_order_samples", null, "medium", "Need future non-empty V11.29 trade/order rows before execution quality can be verified."),
        field("missing", "same_window_v1082_v1129_execution_samples", null, "medium", "Need matching observation windows before comparison."),
      ],
      blocking_gaps: [
        field("derived", "v1129_trades_total_observed_zero", "trades", "high", "Observed count(*) result is zero; this blocks execution quality metrics.", [
          "v1129_snapshot_sqlite",
        ]),
        field("derived", "v1129_orders_total_observed_zero", "orders", "high", "Observed count(*) result is zero; this blocks order/fill/latency metrics.", [
          "v1129_snapshot_sqlite",
        ]),
        field("derived", "same_window_execution_quality_comparison_insufficient", null, "high", "V10.8.2 rows exist, but V11.29 rows do not."),
      ],
    },
    verdict: {
      report_status: "blocked_by_missing_data",
      can_generate_execution_report: field(
        "derived",
        false,
        null,
        "high",
        "This is an insufficient evidence report, not a full real execution validation report.",
        ["v1129_snapshot_sqlite"],
      ),
      can_evaluate_replacement: field(
        "derived",
        false,
        null,
        "high",
        "Replacement evaluation requires non-empty V11.29 samples and same-window V10.8.2 comparison evidence.",
        ["v1129_snapshot_sqlite", "v1082_snapshot_sqlite"],
      ),
      reason: field(
        "derived",
        "V11.29 snapshot has observed trades.total = 0 and orders.total = 0, so execution quality and same-window comparison are blocked.",
        null,
        "high",
        "Zero rows are an observed database count, not a strategy failure conclusion.",
        ["v1129_snapshot_sqlite"],
      ),
      next_required_task: field(
        "derived",
        "Task 19: V11.29 Zero-Trade Cause Investigation",
        null,
        "high",
        "Investigate why the V11.29 snapshot contains no trades/orders before attempting execution-quality reporting.",
        ["task17_sqlite_inspection"],
      ),
    },
  };
}

function assertReport(report, markdown) {
  const allowedStates = new Set(["observed", "derived", "missing", "unknown", "not_applicable"]);
  function assertEvidenceStates(value, breadcrumbs = []) {
    if (Array.isArray(value)) {
      value.forEach((item, index) => assertEvidenceStates(item, [...breadcrumbs, String(index)]));
      return;
    }
    if (!value || typeof value !== "object") {
      return;
    }
    if (Object.hasOwn(value, "state") && !allowedStates.has(value.state)) {
      throw new Error(`invalid evidence state at ${breadcrumbs.join(".")}: ${value.state}`);
    }
    for (const [key, child] of Object.entries(value)) {
      assertEvidenceStates(child, [...breadcrumbs, key]);
    }
  }

  assertEvidenceStates(report);

  if (report.metadata.sample_status !== "insufficient") {
    throw new Error("metadata.sample_status must be insufficient");
  }
  if (report.snapshot_summary.v1129.trades.total !== 0) {
    throw new Error("expected observed v1129.trades.total to be 0");
  }
  if (report.snapshot_summary.v1129.orders.total !== 0) {
    throw new Error("expected observed v1129.orders.total to be 0");
  }
  if (report.snapshot_summary.v1082.trades.closed !== 6) {
    throw new Error("expected observed v1082.closed_trades to be 6");
  }
  if (report.snapshot_summary.v1082.orders.total !== 12) {
    throw new Error("expected observed v1082.orders to be 12");
  }
  if (report.verdict.can_generate_execution_report.value !== false) {
    throw new Error("can_generate_execution_report must be false");
  }
  if (report.verdict.can_evaluate_replacement.value !== false) {
    throw new Error("can_evaluate_replacement must be false");
  }

  const serialized = `${JSON.stringify(report)}\n${markdown}`;
  const forbiddenPhrases = [
    "V11.29 passed",
    "V11.29 can replace",
    "V11.29 通过真实执行验证",
    "V11.29 可以替换 V10.8.2",
    "winrate",
    "profit factor",
  ];
  for (const phrase of forbiddenPhrases) {
    if (serialized.toLowerCase().includes(phrase.toLowerCase())) {
      throw new Error(`forbidden phrase found: ${phrase}`);
    }
  }
}

function renderMarkdown(report) {
  const v1129 = report.snapshot_summary.v1129;
  const v1082 = report.snapshot_summary.v1082;
  return `# V11.29 Snapshot-Based Insufficient Execution Report

## Summary

This report was generated from local read-only SQLite snapshots. It records an
insufficient V11.29 execution sample: the V11.29 snapshot contains observed
\`trades.total = ${v1129.trades.total}\` and observed \`orders.total = ${v1129.orders.total}\`.

This is not a positive execution validation report, and it does not evaluate
replacement readiness.

## Data availability

| Source | Status | Details |
|---|---|---|
| V11.29 SQLite snapshot | observed | \`${v1129.file.path}\`, ${v1129.file.size_bytes} bytes, SHA256 \`${v1129.file.sha256}\` |
| V10.8.2 SQLite snapshot | observed | \`${v1082.file.path}\`, ${v1082.file.size_bytes} bytes, SHA256 \`${v1082.file.sha256}\` |
| Runtime/API/monitor logs | unknown | Not read in this task |
| Secrets/server/bot state | not_applicable | Not accessed in this task |

## Execution sample status

| Metric | V11.29 | Evidence state |
|---|---:|---|
| trades total | ${v1129.trades.total} | observed SQLite \`count(*)\` |
| open trades | ${v1129.trades.open} | observed SQLite query |
| closed trades | ${v1129.trades.closed} | observed SQLite query |
| orders total | ${v1129.orders.total} | observed SQLite \`count(*)\` |
| sample status | \`${report.metadata.sample_status}\` | derived from observed counts |

The observed zero trade/order counts must not be interpreted as a strategy
failure conclusion. They only prove that this acquired SQLite snapshot does not
contain V11.29 trade/order rows.

## Runtime health

Runtime health is \`${report.bot_runtime.running_state.state}\` because this
task did not read dashboard API, monitor history, server state, bot logs, or
secret-backed runtime sources.

## Execution quality

Execution quality is \`insufficient\`. The report intentionally does not compute
V11.29 performance metrics, order quality, fee quality, funding quality,
slippage, or latency because V11.29 has no observed trade/order rows in this
snapshot.

## V10.8.2 comparison readiness

Benchmark data availability:

- V10.8.2 closed trades: ${v1082.trades.closed}
- V10.8.2 orders: ${v1082.orders.total}
- V10.8.2 earliest open: ${v1082.trades.earliest_open_date}
- V10.8.2 latest close: ${v1082.trades.latest_close_date}

These values are benchmark availability only. Same-window execution quality
comparison is \`insufficient\` because the V11.29 snapshot has no trade/order
rows.

## Missing data

- Non-empty V11.29 trade/order rows
- V11.29 order/fill rows for order price, filled price, fee, funding, and latency
- Signal/supervisor data for unfilled or blocked signals
- Runtime/API/monitor data for uptime, stopped alerts, API errors, and jq parse errors
- Same-window V11.29 and V10.8.2 execution samples

## Blocking gaps

- \`v1129.trades.total = ${v1129.trades.total}\` from observed SQLite query
- \`v1129.orders.total = ${v1129.orders.total}\` from observed SQLite query
- no V11.29 1d / 7d / 14d execution sample window
- no same-window execution quality comparison

## What this report cannot conclude

This report cannot conclude that V11.29 has acceptable execution quality, cannot
compare V11.29 with V10.8.2, cannot calculate replacement readiness, and cannot
explain why the V11.29 snapshot has no trade/order rows.

## Recommended next task

Task 19: V11.29 Zero-Trade Cause Investigation
`;
}

function main() {
  const report = buildReport();
  const markdown = renderMarkdown(report);
  assertReport(report, markdown);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown, "utf8");
  console.log(`wrote ${JSON_OUT}`);
  console.log(`wrote ${MD_OUT}`);
}

main();
