#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "ranging_short_research");
const JSON_OUT = path.join(OUT_DIR, "ranging_short_alpha_taker_data_source_inventory.json");
const MD_OUT = path.join(OUT_DIR, "ranging_short_alpha_taker_data_source_inventory.md");

const RECON_JSON = path.join(OUT_DIR, "ranging_short_alpha_state_reconstruction.json");
const TASK142 = path.join(ROOT, "reports", "audits", "task142_ranging_short_alpha_taker_data_source_authorization.md");
const TASK149 = path.join(ROOT, "reports", "audits", "task149_ranging_short_alpha_taker_data_source_guard_exception.md");

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function buildReport() {
  const recon = readJson(RECON_JSON);
  const pairCount = recon.observed_ohlcv_evidence?.pair_count ?? "unknown";
  const candidateCount = recon.observed_ohlcv_evidence?.candidate_count ?? "unknown";
  const latestPairDataMax = recon.observed_ohlcv_evidence?.source_freshness?.latest_pair_data_max ?? "unknown";

  const fields = {
    alpha_risk_flags: {
      current_state: recon.reconstructed_alpha_state?.alpha_risk_flags?.state ?? "unknown",
      committed_source_status: "missing",
      future_source_need: "historical alpha-risk allowed/blocked timeline for every candidate timestamp",
      safe_next_action: "read-only source inventory only",
    },
    taker_buy_pressure: {
      current_state: recon.reconstructed_alpha_state?.taker_buy_pressure?.state ?? "unknown",
      committed_source_status: "missing",
      future_source_need: "taker-buy pressure timeline aligned to candidate timestamps",
      safe_next_action: "read-only source inventory only",
    },
    taker_sell_pressure: {
      current_state: recon.reconstructed_alpha_state?.taker_sell_pressure?.state ?? "unknown",
      committed_source_status: "missing",
      future_source_need: "taker-sell pressure timeline aligned to candidate timestamps",
      safe_next_action: "read-only source inventory only",
    },
    protection_blocked: {
      current_state: recon.reconstructed_alpha_state?.protection_blocked?.state ?? "unknown",
      committed_source_status: "unknown",
      future_source_need: "protection/pairlock timeline, if non-secret and available",
      safe_next_action: "read-only source inventory only",
    },
    pairlist_included: {
      current_state: recon.reconstructed_alpha_state?.pairlist_included?.state ?? "unknown",
      committed_source_status: "unknown",
      future_source_need: "historical pairlist membership by candidate timestamp",
      safe_next_action: "read-only source inventory only",
    },
    wallet_or_stake_blocked: {
      current_state: recon.reconstructed_alpha_state?.wallet_or_stake_blocked?.state ?? "unknown",
      committed_source_status: "unknown",
      future_source_need: "non-secret wallet/stake blocker evidence, if explicitly authorized",
      safe_next_action: "manual authorization before content reads",
    },
  };

  return {
    metadata: {
      candidate_family: "ranging_short_volatility_fade",
      report_status: "alpha_taker_data_source_inventory_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [rel(RECON_JSON), rel(TASK142), rel(TASK149)],
      reads_secret: false,
      reads_env_files: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      writes_sqlite: false,
    },
    current_research_evidence: {
      state: "observed",
      candidate_count: candidateCount,
      pair_count: pairCount,
      latest_pair_data_max: latestPairDataMax,
      source_method: recon.observed_ohlcv_evidence?.method ?? "unknown",
      can_authorize_strategy_implementation: false,
      can_authorize_backtest: false,
      can_authorize_shadow_deployment: false,
    },
    field_source_inventory: fields,
    safe_future_inventory_scope: {
      allowed_questions: [
        "Does a non-secret alpha-risk source exist?",
        "Does a non-secret taker pressure source exist?",
        "Can protection/pairlist blockers be inventoried without reading secrets?",
        "Does any source cover the recent 2026-07 runtime window?",
      ],
      forbidden_actions: [
        "strategy_changes",
        "bot_config_changes",
        "secret_reads",
        "server_writes",
        "bot_lifecycle_commands",
        "backtests",
        "profitability_claims",
      ],
    },
    decision: {
      can_reconstruct_alpha_taker_now: false,
      can_authorize_strategy_implementation: false,
      can_authorize_backtest: false,
      can_claim_profitability: false,
      conclusion: "alpha_taker_sources_not_available_in_committed_evidence",
      reason: "Committed evidence identifies required fields but does not provide alpha/taker/protection source data.",
    },
    blocking_gaps: [
      "alpha_risk_source_missing",
      "taker_buy_pressure_source_missing",
      "taker_sell_pressure_source_missing",
      "protection_pairlock_source_unknown",
      "pairlist_history_source_unknown",
      "recent_2026_07_runtime_window_not_proven",
      "no_execution_quality_evidence",
    ],
    explicit_non_conclusions: [
      "Does not prove ranging-short is profitable.",
      "Does not authorize strategy implementation.",
      "Does not authorize a Freqtrade backtest.",
      "Does not authorize deployment or live shadow launch.",
    ],
    next_recommended_task: "Task 154: Ranging Short Alpha/Taker Source Acquisition Authorization",
  };
}

function markdown(report) {
  const fieldRows = Object.entries(report.field_source_inventory)
    .map(([field, item]) => `| \`${field}\` | \`${item.current_state}\` | \`${item.committed_source_status}\` | ${item.future_source_need} | ${item.safe_next_action} |`)
    .join("\n");
  const forbidden = report.safe_future_inventory_scope.forbidden_actions.map((item) => `- \`${item}\``).join("\n");
  const gaps = report.blocking_gaps.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# Ranging Short Alpha/Taker Data Source Inventory

## Summary

This report inventories alpha/taker/protection source readiness from committed
read-only evidence only. It does not access the server, read secrets, modify
strategy/config files, or run backtests.

Decision:

\`\`\`text
${report.decision.conclusion}
\`\`\`

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Current Research Evidence

| item | value |
|---|---|
| candidate count | ${report.current_research_evidence.candidate_count} |
| pair count | ${report.current_research_evidence.pair_count} |
| latest pair data max | \`${report.current_research_evidence.latest_pair_data_max}\` |
| source method | \`${report.current_research_evidence.source_method}\` |
| can authorize strategy implementation | \`${report.current_research_evidence.can_authorize_strategy_implementation}\` |
| can authorize backtest | \`${report.current_research_evidence.can_authorize_backtest}\` |

## Field Source Inventory

| field | current state | committed source | future source need | safe next action |
|---|---|---|---|---|
${fieldRows}

## Forbidden Actions

${forbidden}

## Decision

| item | value |
|---|---|
| can reconstruct alpha/taker now | \`${report.decision.can_reconstruct_alpha_taker_now}\` |
| can authorize strategy implementation | \`${report.decision.can_authorize_strategy_implementation}\` |
| can authorize backtest | \`${report.decision.can_authorize_backtest}\` |
| can claim profitability | \`${report.decision.can_claim_profitability}\` |
| reason | ${report.decision.reason} |

## Blocking Gaps

${gaps}

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
  if (report.decision.can_authorize_backtest !== false) throw new Error("backtest must remain unauthorized");
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown(report), "utf8");
  console.log(`wrote ${rel(JSON_OUT)}`);
  console.log(`wrote ${rel(MD_OUT)}`);
}

main();
