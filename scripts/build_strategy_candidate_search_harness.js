#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const RUN_ID = "2026-07-09-v1130-15m-4h-first-pass";
const OUT_DIR = path.join(ROOT, "reports", "candidate_search", RUN_ID);
const JSON_OUT = path.join(OUT_DIR, "candidate_search_summary.json");
const MD_OUT = path.join(OUT_DIR, "candidate_search_summary.md");
const CSV_OUT = path.join(OUT_DIR, "candidate_matrix.csv");

const SOURCES = {
  highVol: "reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json",
  rangingShort: "reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json",
  looseRange: "reports/v1130_observation/v1130_loose_range_replay_report.json",
  watchOnly: "reports/v1130_observation/v1130_watch_only_telemetry_report.json",
  finalTelemetry: "reports/v1130_observation/v1130_final_decision_telemetry.json",
};

function readJson(repoPath) {
  const fullPath = path.join(ROOT, repoPath);
  return JSON.parse(fs.readFileSync(fullPath, "utf8"));
}

function round(value, places = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return null;
  }
  const factor = 10 ** places;
  return Math.round(Number(value) * factor) / factor;
}

function getHorizon(candidate, horizon, field) {
  return candidate?.horizons?.[String(horizon)]?.[field] || {};
}

function positiveRate(candidate, horizon) {
  return getHorizon(candidate, horizon, "fee_adjusted_return").positive_rate ?? null;
}

function meanBps(candidate, horizon) {
  return getHorizon(candidate, horizon, "fee_adjusted_return").mean_bps ?? null;
}

function countBps(candidate, horizon) {
  return getHorizon(candidate, horizon, "fee_adjusted_return").count ?? candidate?.count ?? null;
}

function maxShare(map) {
  const values = Object.values(map || {}).map(Number).filter((value) => Number.isFinite(value));
  const total = values.reduce((sum, value) => sum + value, 0);
  if (!total) {
    return null;
  }
  return round(Math.max(...values) / total, 4);
}

function scoreCandidate(row) {
  let score = 50;
  if (row.sample_status === "insufficient") score -= 18;
  if (row.data_gap_status !== "ready") score -= 12;
  if (row.net_return_bps !== null) score += Math.max(-25, Math.min(25, row.net_return_bps / 2));
  if (row.positive_rate !== null) score += (row.positive_rate - 0.5) * 40;
  if (row.trade_count !== null && row.trade_count >= 100) score += 8;
  if (row.trade_count !== null && row.trade_count < 30) score -= 6;
  if (row.pair_concentration !== null && row.pair_concentration > 0.5) score -= 10;
  if (row.alpha_state === "missing" || row.alpha_state === "unknown") score -= 5;
  return round(Math.max(0, Math.min(100, score)), 2);
}

function buildRows() {
  const highVol = readJson(SOURCES.highVol);
  const rangingShort = readJson(SOURCES.rangingShort);
  const looseRange = readJson(SOURCES.looseRange);
  const watchOnly = readJson(SOURCES.watchOnly);
  const finalTelemetry = readJson(SOURCES.finalTelemetry);

  const byCandidate = highVol.aggregate?.by_candidate || {};
  const crash = byCandidate.crash_rebound;
  const blowoff = byCandidate.blowoff_short;
  const selloff = byCandidate.selloff_continuation;
  const rangingSummary8 = rangingShort.aggregate?.summaries?.["8"]?.fee_adjusted_return || {};
  const rangingSummary4 = rangingShort.aggregate?.summaries?.["4"]?.fee_adjusted_return || {};
  const loose4 = looseRange.forward_return_summary?.["4_candle"] || {};
  const loose8 = looseRange.forward_return_summary?.["8_candle"] || {};

  const rows = [
    {
      candidate_id: "crash_rebound_continuation",
      family: "crash_rebound",
      source: SOURCES.highVol,
      data_mode: "15m_with_4h_context",
      trade_count: countBps(crash, 4),
      closed_trade_count: countBps(crash, 4),
      net_return_bps: round(meanBps(crash, 4)),
      positive_rate: round(positiveRate(crash, 4)),
      profit_factor: "unknown",
      max_drawdown: "unknown",
      mfe_bps: round(getHorizon(crash, 4, "mfe").mean_bps),
      mae_bps: round(getHorizon(crash, 4, "mae").mean_bps),
      pair_count: "unknown",
      pair_concentration: "unknown",
      exit_reason_distribution: "missing",
      alpha_state: "observed_filter_blocks_only",
      data_gap_status: "ready_15m_4h_1h_excluded_stale",
      sample_status: "thin",
      notes: "Best high-volatility replay ranking; V11.30 live path confirms order-capable behavior but early live quality is insufficient.",
    },
    {
      candidate_id: "v1130_loose_range_watch",
      family: "crash_rebound_loose_range",
      source: SOURCES.looseRange,
      data_mode: "15m_ohlcv_watch_replay",
      trade_count: looseRange.counts?.enabled ?? null,
      closed_trade_count: looseRange.counts?.enabled ?? null,
      net_return_bps: round(loose4.mean_bps),
      positive_rate: round(loose4.win_rate),
      profit_factor: "unknown",
      max_drawdown: "unknown",
      mfe_bps: "unknown",
      mae_bps: "unknown",
      pair_count: Object.keys(looseRange.concentration?.enabled_by_pair || {}).length || null,
      pair_concentration: maxShare(looseRange.concentration?.enabled_by_pair),
      exit_reason_distribution: "missing",
      alpha_state: "partial_blockers_observed",
      data_gap_status: "ready_15m_4h_1h_excluded_stale",
      sample_status: looseRange.counts?.enabled >= 30 ? "adequate" : "thin",
      notes: `Loose-range watch replay: 4-candle mean ${loose4.mean_bps} bps, 8-candle mean ${loose8.mean_bps} bps; not an order-capable proof.`,
    },
    {
      candidate_id: "ranging_short_volatility_fade",
      family: "ranging_short",
      source: SOURCES.rangingShort,
      data_mode: "30d_ohlcv_derived_15m_4h",
      trade_count: rangingShort.aggregate?.candidate_count ?? null,
      closed_trade_count: rangingShort.aggregate?.candidate_count ?? null,
      net_return_bps: round(rangingSummary8.mean_bps),
      positive_rate: round(rangingSummary8.positive_rate),
      profit_factor: "unknown",
      max_drawdown: "unknown",
      mfe_bps: round(rangingShort.aggregate?.summaries?.["8"]?.mfe?.mean_bps),
      mae_bps: round(rangingShort.aggregate?.summaries?.["8"]?.mae?.mean_bps),
      pair_count: Array.isArray(rangingShort.pairs) ? rangingShort.pairs.length : null,
      pair_concentration: "unknown",
      exit_reason_distribution: "missing",
      alpha_state: rangingShort.metadata?.alpha_state || "unknown",
      data_gap_status: "historical_only_latest_window_not_included",
      sample_status: "research_candidate",
      notes: "Large 30d OHLCV-derived sample, but alpha state is missing and this is not a Freqtrade backtest or execution report.",
    },
    {
      candidate_id: "selloff_continuation_short",
      family: "selloff_continuation",
      source: SOURCES.highVol,
      data_mode: "15m_with_4h_context",
      trade_count: countBps(selloff, 4),
      closed_trade_count: countBps(selloff, 4),
      net_return_bps: round(meanBps(selloff, 4)),
      positive_rate: round(positiveRate(selloff, 4)),
      profit_factor: "unknown",
      max_drawdown: "unknown",
      mfe_bps: round(getHorizon(selloff, 4, "mfe").mean_bps),
      mae_bps: round(getHorizon(selloff, 4, "mae").mean_bps),
      pair_count: "unknown",
      pair_concentration: "unknown",
      exit_reason_distribution: "missing",
      alpha_state: "observed_filter_blocks_only",
      data_gap_status: "ready_15m_4h_1h_excluded_stale",
      sample_status: "adequate_count_negative_edge",
      notes: "Enough replay samples, but 4-candle fee-adjusted mean is negative in existing evidence.",
    },
    {
      candidate_id: "blowoff_short_fade",
      family: "blowoff_short",
      source: SOURCES.highVol,
      data_mode: "15m_with_4h_context",
      trade_count: countBps(blowoff, 4),
      closed_trade_count: countBps(blowoff, 4),
      net_return_bps: round(meanBps(blowoff, 4)),
      positive_rate: round(positiveRate(blowoff, 4)),
      profit_factor: "unknown",
      max_drawdown: "unknown",
      mfe_bps: round(getHorizon(blowoff, 4, "mfe").mean_bps),
      mae_bps: round(getHorizon(blowoff, 4, "mae").mean_bps),
      pair_count: "unknown",
      pair_concentration: "unknown",
      exit_reason_distribution: "missing",
      alpha_state: "observed_filter_blocks_only",
      data_gap_status: "ready_15m_4h_1h_excluded_stale",
      sample_status: "large_count_negative_edge",
      notes: "Large replay sample but negative fee-adjusted mean; keep as risk/control family, not first implementation target.",
    },
  ];

  for (const row of rows) {
    row.priority_score = scoreCandidate(row);
  }

  rows.sort((a, b) => b.priority_score - a.priority_score);

  return {
    rows,
    source_summaries: {
      finalTelemetry: finalTelemetry.summary || {},
      watchOnly: watchOnly.summary || {},
      highVolRanking: highVol.aggregate?.ranking || [],
      rangingShortClassification: rangingShort.classification || {},
    },
  };
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function writeCsv(rows) {
  const columns = [
    "rank",
    "candidate_id",
    "family",
    "priority_score",
    "data_mode",
    "trade_count",
    "closed_trade_count",
    "net_return_bps",
    "positive_rate",
    "profit_factor",
    "max_drawdown",
    "mfe_bps",
    "mae_bps",
    "pair_count",
    "pair_concentration",
    "exit_reason_distribution",
    "alpha_state",
    "data_gap_status",
    "sample_status",
    "source",
    "notes",
  ];
  const lines = [columns.join(",")];
  rows.forEach((row, index) => {
    lines.push(columns.map((column) => csvEscape(column === "rank" ? index + 1 : row[column])).join(","));
  });
  fs.writeFileSync(CSV_OUT, `${lines.join("\n")}\n`, "utf8");
}

function writeMarkdown(summary) {
  const rows = summary.candidates;
  const lines = [
    "# Candidate Search Summary: 2026-07-09 V11.30 15m+4h First Pass",
    "",
    "## Summary",
    "",
    "This is an offline, read-only candidate-search harness output. It aggregates existing reports only.",
    "",
    "Conclusion:",
    "",
    "```text",
    summary.verdict.conclusion,
    "```",
    "",
    "This report does not run a backtest, does not modify strategy/config files, and does not claim V11.30 can replace V10.8.2.",
    "",
    "## Data Gate",
    "",
    "| item | status |",
    "|---|---|",
    `| run id | \`${summary.metadata.run_id}\` |`,
    `| generated at | \`${summary.metadata.generated_at}\` |`,
    "| 15m OHLCV | `ready` |",
    "| 4h OHLCV | `ready` |",
    "| 1h OHLCV | `excluded_stale` |",
    "| backtest run | `false` |",
    "| strategy modified | `false` |",
    "| bot config modified | `false` |",
    "| server operation | `false` |",
    "",
    "## Candidate Matrix",
    "",
    "| rank | candidate | score | samples | net bps | positive rate | data status | note |",
    "|---:|---|---:|---:|---:|---:|---|---|",
  ];

  rows.forEach((row, index) => {
    lines.push(
      `| ${index + 1} | \`${row.candidate_id}\` | ${row.priority_score} | ${row.trade_count} | ${row.net_return_bps} | ${row.positive_rate} | \`${row.data_gap_status}\` | ${row.notes.replace(/\|/g, "/")} |`,
    );
  });

  lines.push(
    "",
    "## Blocking Gaps",
    "",
    "- Recent `1h` futures OHLCV remains stale and is excluded from this pass.",
    "- Profit factor, max drawdown, exit reason distribution, and live execution quality are unavailable for most offline candidates.",
    "- V11.30 live sample remains insufficient and must not be used for replacement conclusions.",
    "- Ranging-short alpha state is missing in historical OHLCV-derived evidence.",
    "",
    "## Recommended Next Task",
    "",
    "```text",
    summary.verdict.next_required_task,
    "```",
    "",
  );

  fs.writeFileSync(MD_OUT, lines.join("\n"), "utf8");
}

function main() {
  const { rows, source_summaries } = buildRows();
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const summary = {
    metadata: {
      run_id: RUN_ID,
      generated_at: new Date().toISOString(),
      mode: "read_only_existing_report_aggregation",
      uses_timeframes: ["15m", "4h"],
      excluded_timeframes: [{ timeframe: "1h", reason: "Task 103 found exact futures OHLCV stale at 2026-07-03T08:00:00Z" }],
      reads_secret_material: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      modifies_dashboard: false,
      modifies_deploy: false,
      starts_or_stops_bot: false,
      runs_backtest: false,
      writes_sqlite: false,
    },
    data_sources: Object.values(SOURCES).map((repoPath) => ({ path: repoPath, status: "read" })),
    source_summaries,
    candidates: rows,
    verdict: {
      report_status: "first_pass_candidate_ranking",
      can_select_implementation_target: true,
      can_modify_strategy_from_this_report_alone: false,
      can_evaluate_v1130_replacement: false,
      conclusion: `first_pass_top_candidate_${rows[0]?.candidate_id || "unknown"}`,
      recommended_candidate: rows[0]?.candidate_id || "unknown",
      next_required_task: "Task 108: Candidate Search First-Pass Review And Implementation Target Decision",
      reason: "The first pass ranks existing evidence for planning only; strategy implementation requires a separate exact-scope task.",
    },
  };

  fs.writeFileSync(JSON_OUT, `${JSON.stringify(summary, null, 2)}\n`, "utf8");
  writeCsv(rows);
  writeMarkdown(summary);
  console.log(`wrote ${path.relative(ROOT, JSON_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, MD_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, CSV_OUT)}`);
}

main();
