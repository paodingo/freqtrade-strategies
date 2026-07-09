#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1130_observation");
const JSON_OUT = path.join(OUT_DIR, "v1130_runtime_performance_audit.json");
const MD_OUT = path.join(OUT_DIR, "v1130_runtime_performance_audit.md");

const TASK126 = path.join(ROOT, "reports", "audits", "task126_v1130_live_evidence_refresh_candidate_priority_rebalance.md");
const TASK129 = path.join(ROOT, "reports", "audits", "task129_v1130_runtime_performance_warning_investigation.md");
const TASK132 = path.join(ROOT, "reports", "audits", "task132_v1130_instrumented_runtime_performance_audit_plan.md");

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readText(file) {
  return fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "");
}

function firstMatch(text, regex) {
  const match = text.match(regex);
  return match ? match[1] : null;
}

function has(text, pattern) {
  return pattern.test(text);
}

function buildReport() {
  const task126 = readText(TASK126);
  const task129 = readText(TASK129);
  const task132 = readText(TASK132);

  const analysisDuration = Number(firstMatch(task129, /Strategy analysis took ([0-9.]+)s/i));
  const analysisThreshold = Number(firstMatch(task129, /timeframe \(([0-9.]+)s\)/i));

  const report = {
    metadata: {
      strategy: "RegimeAwareV1130CrashReboundShadow",
      report_status: "runtime_performance_audit_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [rel(TASK126), rel(TASK129), rel(TASK132)],
      reads_secret: false,
      reads_env_files: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      writes_sqlite: false,
      live_server_rechecked_this_task: false,
    },
    committed_server_context: {
      host: firstMatch(task129, /\| host \| `([^`]+)` \|/i) || "unknown",
      hostname: firstMatch(task129, /\| hostname \| `([^`]+)` \|/i) || "unknown",
      server_time_checked: firstMatch(task129, /\| server time checked \| `([^`]+)` \|/i) || "unknown",
      v1130_container: firstMatch(task129, /\| V11\.30 container \| `([^`]+)` \|/i) || "unknown",
      v1130_state: firstMatch(task129, /\| V11\.30 state \| `([^`]+)` \|/i) || "unknown",
      v1129_container: firstMatch(task129, /\| V11\.29 container \| `([^`]+)` \|/i) || "unknown",
      v1129_state: firstMatch(task129, /\| V11\.29 state \| `([^`]+)` \|/i) || "unknown",
    },
    observed_runtime_signals: {
      analysis_overrun: {
        state: Number.isFinite(analysisDuration) ? "observed" : "unknown",
        max_observed_seconds: Number.isFinite(analysisDuration) ? analysisDuration : "unknown",
        warning_threshold_seconds: Number.isFinite(analysisThreshold) ? analysisThreshold : "unknown",
        source: rel(TASK129),
      },
      exchange_timeout: {
        state: has(task129, /RequestTimeout|Could not load markets/i) ? "observed" : "unknown",
        endpoint: has(task129, /exchangeInfo/i) ? "binance dapi exchangeInfo" : "unknown",
        source: rel(TASK129),
      },
      running_after_warning: {
        state: has(task129, /state='RUNNING'|still running|V11\.30 is still running/i) ? "observed" : "unknown",
        source: rel(TASK129),
      },
      point_in_time_resource_saturation: {
        state: "not_observed_in_snapshot",
        caveat: "Point-in-time docker stats do not rule out intermittent spikes during analysis cycles.",
        source: rel(TASK129),
      },
    },
    trade_context: {
      source: rel(TASK126),
      trades: 2,
      orders: 4,
      open_trades: 0,
      closed_trades: 2,
      realized_pnl_usdt: -4.66341765,
      performance_interpretation_allowed: false,
      reason: "Small negative trade sample is runtime context only; this report does not evaluate strategy quality.",
    },
    audit_questions: {
      overrun_frequency: {
        state: "unknown",
        reason: "Committed evidence confirms at least one overrun but does not include full log-window counts.",
      },
      overrun_trade_correlation: {
        state: "unknown",
        reason: "Committed evidence does not join analysis warnings to exact trade/order timing.",
      },
      api_timeout_correlation: {
        state: "unknown",
        reason: "One exchangeInfo timeout is observed, but frequency and correlation remain unknown.",
      },
      v1129_resource_contention: {
        state: "unknown",
        reason: "V11.29 is co-running, but point-in-time CPU/memory is not enough to prove contention.",
      },
      bottleneck_source: {
        state: "unknown",
        reason: "No per-indicator, data-loading, or exchange-I/O timing breakdown is available.",
      },
    },
    risk_decision: {
      runtime_risk_state: "active_risk",
      blocks_promotion: true,
      can_claim_runtime_stable: false,
      can_claim_replacement: false,
      reason: "At least one analysis overrun and one exchange timeout are observed; frequency and impact remain unknown.",
    },
    required_next_evidence: [
      "full_log_window_analysis_duration_count",
      "exchange_timeout_count_by_window",
      "docker_stats_repeated_samples",
      "trade_order_timing_join_around_warning_windows",
      "v1129_correlation_or_resource_isolation_check",
      "per_cycle_or_per_pair_bottleneck_measurement",
    ],
    explicit_non_conclusions: [
      "Does not prove V11.30 is bad.",
      "Does not prove V11.30 is good.",
      "Does not prove runtime is stable.",
      "Does not authorize promotion or replacement.",
      "Does not authorize bot restart or configuration changes.",
    ],
    next_recommended_task: "Task 143: V11.30 Live Telemetry Window Collection Authorization",
  };

  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.starts_or_stops_bot !== false) throw new Error("starts_or_stops_bot must be false");
  if (report.risk_decision.blocks_promotion !== true) throw new Error("runtime risk should block promotion");
  return report;
}

function markdown(report) {
  const signalRows = Object.entries(report.observed_runtime_signals)
    .map(([name, item]) => `| \`${name}\` | \`${item.state}\` | ${item.max_observed_seconds ?? item.endpoint ?? item.caveat ?? ""} | \`${item.source}\` |`)
    .join("\n");
  const questionRows = Object.entries(report.audit_questions)
    .map(([name, item]) => `| \`${name}\` | \`${item.state}\` | ${item.reason} |`)
    .join("\n");
  const needed = report.required_next_evidence.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# V11.30 Runtime Performance Audit

## Summary

This report audits V11.30 runtime performance using committed read-only evidence
only. It does not reconnect to the server and does not start, stop, restart, or
modify any bot.

Decision:

\`\`\`text
${report.risk_decision.runtime_risk_state}
\`\`\`

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Server Context From Committed Evidence

| item | value |
|---|---|
| host | \`${report.committed_server_context.host}\` |
| hostname | \`${report.committed_server_context.hostname}\` |
| server time checked | \`${report.committed_server_context.server_time_checked}\` |
| V11.30 container | \`${report.committed_server_context.v1130_container}\` |
| V11.30 state | \`${report.committed_server_context.v1130_state}\` |
| V11.29 container | \`${report.committed_server_context.v1129_container}\` |
| V11.29 state | \`${report.committed_server_context.v1129_state}\` |

## Observed Runtime Signals

| signal | state | value | source |
|---|---|---|---|
${signalRows}

## Trade Context

| item | value |
|---|---:|
| trades | ${report.trade_context.trades} |
| orders | ${report.trade_context.orders} |
| open trades | ${report.trade_context.open_trades} |
| closed trades | ${report.trade_context.closed_trades} |
| realized PnL USDT | ${report.trade_context.realized_pnl_usdt} |

This trade context does not authorize a strategy quality conclusion.

## Audit Questions

| question | state | reason |
|---|---|---|
${questionRows}

## Risk Decision

| item | value |
|---|---|
| blocks promotion | \`${report.risk_decision.blocks_promotion}\` |
| can claim runtime stable | \`${report.risk_decision.can_claim_runtime_stable}\` |
| can claim replacement | \`${report.risk_decision.can_claim_replacement}\` |
| reason | ${report.risk_decision.reason} |

## Required Next Evidence

${needed}

## What This Cannot Conclude

${nonConclusions}

## Recommended Next Task

\`\`\`text
${report.next_recommended_task}
\`\`\`
`;
}

function main() {
  const report = buildReport();
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown(report), "utf8");
  console.log(`wrote ${rel(JSON_OUT)}`);
  console.log(`wrote ${rel(MD_OUT)}`);
}

main();
