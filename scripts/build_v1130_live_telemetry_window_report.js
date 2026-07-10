#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1130_observation");
const JSON_OUT = path.join(OUT_DIR, "v1130_live_telemetry_window_report.json");
const MD_OUT = path.join(OUT_DIR, "v1130_live_telemetry_window_report.md");

const PERF_JSON = path.join(OUT_DIR, "v1130_runtime_performance_audit.json");
const TASK143 = path.join(ROOT, "reports", "audits", "task143_v1130_live_telemetry_window_collection_authorization.md");
const TASK150 = path.join(ROOT, "reports", "audits", "task150_v1130_live_telemetry_window_guard_exception.md");

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function buildReport() {
  const perf = readJson(PERF_JSON);

  return {
    metadata: {
      strategy: "RegimeAwareV1130CrashReboundShadow",
      report_status: "telemetry_window_report_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [rel(PERF_JSON), rel(TASK143), rel(TASK150)],
      reads_secret: false,
      reads_env_files: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      live_server_rechecked_this_task: false,
      writes_sqlite: false,
    },
    committed_runtime_evidence: {
      server_context: perf.committed_server_context,
      analysis_overrun: perf.observed_runtime_signals?.analysis_overrun || { state: "unknown" },
      exchange_timeout: perf.observed_runtime_signals?.exchange_timeout || { state: "unknown" },
      running_after_warning: perf.observed_runtime_signals?.running_after_warning || { state: "unknown" },
      point_in_time_resource_saturation:
        perf.observed_runtime_signals?.point_in_time_resource_saturation || { state: "unknown" },
    },
    telemetry_window_status: {
      fresh_log_window_collected: false,
      fresh_docker_stats_collected: false,
      fresh_sqlite_timing_join_collected: false,
      reason: "This task is a local committed-evidence report only; live collection requires a separate server-authorized task.",
    },
    bounded_future_collection_plan: {
      log_window: {
        state: "planned_not_executed",
        command_draft: "docker logs --tail <bounded-lines> freqtrade-v1130-crash-rebound-shadow",
        fields: ["analysis_duration_warnings", "exchange_timeouts", "tracebacks", "running_heartbeats"],
      },
      resource_samples: {
        state: "planned_not_executed",
        command_draft: "docker stats --no-stream <approved-container-names>",
        fields: ["cpu_percent", "memory_usage", "memory_percent"],
      },
      sqlite_timing_join: {
        state: "planned_not_executed",
        command_draft: "read-only SQLite count/timestamp queries",
        fields: ["trade_open_time", "order_time", "close_time", "overrun_near_trade_window"],
      },
    },
    risk_decision: {
      runtime_risk_state: perf.risk_decision?.runtime_risk_state || "active_risk",
      blocks_promotion: true,
      can_claim_runtime_stable: false,
      can_claim_replacement: false,
      reason: "At least one overrun and one exchange timeout are known; fresh telemetry frequency and impact remain uncollected.",
    },
    forbidden_actions: [
      "read_env_or_secret_files",
      "docker_inspect_full_output",
      "docker_restart_stop_start",
      "freqtrade_trade",
      "backtests",
      "strategy_changes",
      "bot_config_changes",
      "promotion_or_replacement_claims",
    ],
    required_next_evidence: perf.required_next_evidence || [],
    explicit_non_conclusions: [
      "Does not prove V11.30 is stable.",
      "Does not prove V11.30 is unstable.",
      "Does not authorize promotion or replacement.",
      "Does not authorize bot lifecycle operations.",
    ],
    next_recommended_task: "Task 155: V11.30 Live Telemetry Window Server Collection Authorization",
  };
}

function markdown(report) {
  const futureRows = Object.entries(report.bounded_future_collection_plan)
    .map(([name, item]) => `| \`${name}\` | \`${item.state}\` | \`${item.command_draft}\` | ${item.fields.map((field) => `\`${field}\``).join(", ")} |`)
    .join("\n");
  const forbidden = report.forbidden_actions.map((item) => `- \`${item}\``).join("\n");
  const nextEvidence = report.required_next_evidence.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# V11.30 Live Telemetry Window Report

## Summary

This report summarizes the live telemetry window still needed for V11.30 using
committed read-only evidence only. It does not reconnect to the server, inspect
fresh logs, start/stop/restart bots, modify strategy/config files, or run
backtests.

Decision:

\`\`\`text
${report.risk_decision.runtime_risk_state}
\`\`\`

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Known Committed Runtime Evidence

| item | state | value |
|---|---|---|
| analysis overrun | \`${report.committed_runtime_evidence.analysis_overrun.state}\` | ${report.committed_runtime_evidence.analysis_overrun.max_observed_seconds ?? "unknown"} |
| warning threshold seconds | \`${report.committed_runtime_evidence.analysis_overrun.state}\` | ${report.committed_runtime_evidence.analysis_overrun.warning_threshold_seconds ?? "unknown"} |
| exchange timeout | \`${report.committed_runtime_evidence.exchange_timeout.state}\` | ${report.committed_runtime_evidence.exchange_timeout.endpoint ?? "unknown"} |
| running after warning | \`${report.committed_runtime_evidence.running_after_warning.state}\` | observed from committed evidence |

## Fresh Window Collection Status

| item | value |
|---|---|
| fresh log window collected | \`${report.telemetry_window_status.fresh_log_window_collected}\` |
| fresh docker stats collected | \`${report.telemetry_window_status.fresh_docker_stats_collected}\` |
| fresh SQLite timing join collected | \`${report.telemetry_window_status.fresh_sqlite_timing_join_collected}\` |
| reason | ${report.telemetry_window_status.reason} |

## Future Collection Plan

| source | state | command draft | fields |
|---|---|---|---|
${futureRows}

## Risk Decision

| item | value |
|---|---|
| blocks promotion | \`${report.risk_decision.blocks_promotion}\` |
| can claim runtime stable | \`${report.risk_decision.can_claim_runtime_stable}\` |
| can claim replacement | \`${report.risk_decision.can_claim_replacement}\` |
| reason | ${report.risk_decision.reason} |

## Required Next Evidence

${nextEvidence}

## Forbidden Actions

${forbidden}

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
  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.starts_or_stops_bot !== false) throw new Error("bot lifecycle must be false");
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown(report), "utf8");
  console.log(`wrote ${rel(JSON_OUT)}`);
  console.log(`wrote ${rel(MD_OUT)}`);
}

main();
