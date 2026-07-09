#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "ranging_short_research");
const JSON_OUT = path.join(OUT_DIR, "ranging_short_alpha_state_reconstruction.json");
const MD_OUT = path.join(OUT_DIR, "ranging_short_alpha_state_reconstruction.md");

const STUDY_JSON = path.join(
  ROOT,
  "reports",
  "v1129_execution_validation",
  "v1129_feather_ranging_short_historical_return_study.json",
);
const TASK128 = path.join(ROOT, "reports", "audits", "task128_ranging_short_candidate_evidence_deep_review.md");
const TASK131 = path.join(ROOT, "reports", "audits", "task131_ranging_short_alpha_state_reconstruction_plan.md");

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function summarizeHorizon(study, horizon) {
  const summary = study.aggregate?.summaries?.[String(horizon)] || {};
  return {
    count: summary.fee_adjusted_return?.count ?? null,
    fee_adjusted_mean_bps: summary.fee_adjusted_return?.mean_bps ?? null,
    fee_adjusted_positive_rate: summary.fee_adjusted_return?.positive_rate ?? null,
    mfe_mean_bps: summary.mfe?.mean_bps ?? null,
    mae_mean_bps: summary.mae?.mean_bps ?? null,
  };
}

function pairRows(study) {
  return (study.pairs || []).map((pair) => ({
    pair: pair.pair,
    candidate_count: pair.candidate_count ?? null,
    data_min: pair.data_min ?? null,
    data_max: pair.data_max ?? null,
    alpha_state: "missing",
    taker_buy_pressure: "missing",
    taker_sell_pressure: "missing",
    protection_blocked: "unknown",
    pairlist_included: "unknown",
    fee_adjusted_8_candle_mean_bps: pair.summaries?.["8"]?.fee_adjusted_return?.mean_bps ?? null,
    fee_adjusted_8_candle_positive_rate: pair.summaries?.["8"]?.fee_adjusted_return?.positive_rate ?? null,
  }));
}

function buildReport() {
  const study = readJson(STUDY_JSON);
  const pairs = pairRows(study);
  const candidateCount = study.aggregate?.candidate_count ?? null;

  const report = {
    metadata: {
      candidate_family: "ranging_short_volatility_fade",
      report_status: "alpha_state_reconstruction_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [rel(STUDY_JSON), rel(TASK128), rel(TASK131)],
      reads_secret: false,
      reads_env_files: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      writes_sqlite: false,
    },
    observed_ohlcv_evidence: {
      state: "observed",
      source: rel(STUDY_JSON),
      method: study.metadata?.method ?? "unknown",
      source_freshness: {
        latest_pair_data_max: pairs
          .map((item) => item.data_max)
          .filter(Boolean)
          .sort()
          .at(-1) ?? "unknown",
        known_limitation: "Feather data in the source study ends before the latest 2026-07 runtime window.",
      },
      candidate_count: candidateCount,
      horizons: {
        "1": summarizeHorizon(study, 1),
        "2": summarizeHorizon(study, 2),
        "4": summarizeHorizon(study, 4),
        "8": summarizeHorizon(study, 8),
      },
      pair_count: pairs.length,
      pairs,
    },
    reconstructed_alpha_state: {
      alpha_risk_flags: {
        state: "missing",
        reason: "Committed evidence contains OHLCV-derived candidates but no historical alpha-risk allowed/blocked state.",
      },
      taker_buy_pressure: {
        state: "missing",
        reason: "No committed taker-buy pressure series is available for the candidate timestamps.",
      },
      taker_sell_pressure: {
        state: "missing",
        reason: "No committed taker-sell pressure series is available for the candidate timestamps.",
      },
      protection_blocked: {
        state: "unknown",
        reason: "No live protection or pairlock state was joined to the historical candidates.",
      },
      pairlist_included: {
        state: "unknown",
        reason: "Historical runtime pairlist inclusion is not proven for every candidate timestamp.",
      },
      max_open_trades_blocked: {
        state: "unknown",
        reason: "Historical wallet/open-trade state is not present in the committed OHLCV study.",
      },
      wallet_or_stake_blocked: {
        state: "unknown",
        reason: "Historical wallet and stake availability are not present in the committed OHLCV study.",
      },
    },
    decision: {
      can_authorize_strategy_implementation: false,
      can_authorize_backtest: false,
      can_authorize_shadow_deployment: false,
      can_claim_profitability: false,
      conclusion: "alpha_state_not_reconstructable_from_committed_evidence",
      reason: "The candidate remains research-only because alpha/taker/protection state is missing or unknown.",
    },
    blocking_gaps: [
      "alpha_risk_flags_missing",
      "taker_buy_pressure_missing",
      "taker_sell_pressure_missing",
      "protection_blocked_unknown",
      "pairlist_included_unknown",
      "max_open_trades_blocked_unknown",
      "wallet_or_stake_blocked_unknown",
      "recent_runtime_window_missing",
      "no_freqtrade_backtest",
      "no_live_dry_run_execution_evidence",
    ],
    explicit_non_conclusions: [
      "Does not prove ranging-short is profitable.",
      "Does not authorize strategy implementation.",
      "Does not authorize a Freqtrade backtest.",
      "Does not authorize deployment or live shadow launch.",
      "Does not conclude V11.30 or V11.31 should be abandoned.",
    ],
    next_recommended_task: "Task 142: Ranging Short Alpha/Taker Data Source Authorization",
  };

  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.modifies_strategy !== false) throw new Error("modifies_strategy must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.decision.can_authorize_strategy_implementation !== false) {
    throw new Error("strategy implementation must remain unauthorized");
  }
  return report;
}

function tableRows(rows) {
  return rows
    .map((item) => `| \`${item.pair}\` | ${item.candidate_count ?? "unknown"} | ${item.fee_adjusted_8_candle_mean_bps ?? "unknown"} | ${item.fee_adjusted_8_candle_positive_rate ?? "unknown"} | \`${item.alpha_state}\` | \`${item.protection_blocked}\` |`)
    .join("\n");
}

function markdown(report) {
  const horizonRows = Object.entries(report.observed_ohlcv_evidence.horizons)
    .map(([horizon, item]) => `| ${horizon} | ${item.count ?? "unknown"} | ${item.fee_adjusted_mean_bps ?? "unknown"} | ${item.fee_adjusted_positive_rate ?? "unknown"} | ${item.mfe_mean_bps ?? "unknown"} | ${item.mae_mean_bps ?? "unknown"} |`)
    .join("\n");
  const alphaRows = Object.entries(report.reconstructed_alpha_state)
    .map(([field, item]) => `| \`${field}\` | \`${item.state}\` | ${item.reason} |`)
    .join("\n");
  const gaps = report.blocking_gaps.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# Ranging Short Alpha-State Reconstruction

## Summary

This report reconstructs only what can be proven from committed read-only
evidence. The available ranging-short study remains OHLCV-derived and does not
contain historical alpha/taker/protection state.

Decision:

\`\`\`text
${report.decision.conclusion}
\`\`\`

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Observed OHLCV Evidence

| item | value |
|---|---|
| candidate count | ${report.observed_ohlcv_evidence.candidate_count} |
| pair count | ${report.observed_ohlcv_evidence.pair_count} |
| method | \`${report.observed_ohlcv_evidence.method}\` |
| latest pair data max | \`${report.observed_ohlcv_evidence.source_freshness.latest_pair_data_max}\` |

| horizon candles | count | fee-adjusted mean bps | fee-adjusted positive rate | MFE mean bps | MAE mean bps |
|---:|---:|---:|---:|---:|---:|
${horizonRows}

## Pair Matrix

| pair | candidates | 8-candle fee-adjusted mean bps | 8-candle positive rate | alpha state | protection blocked |
|---|---:|---:|---:|---|---|
${tableRows(report.observed_ohlcv_evidence.pairs)}

## Alpha-State Availability

| field | state | reason |
|---|---|---|
${alphaRows}

## Decision

| item | value |
|---|---|
| can authorize strategy implementation | \`${report.decision.can_authorize_strategy_implementation}\` |
| can authorize backtest | \`${report.decision.can_authorize_backtest}\` |
| can authorize shadow deployment | \`${report.decision.can_authorize_shadow_deployment}\` |
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
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown(report), "utf8");
  console.log(`wrote ${rel(JSON_OUT)}`);
  console.log(`wrote ${rel(MD_OUT)}`);
}

main();
