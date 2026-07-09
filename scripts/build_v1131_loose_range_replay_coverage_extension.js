#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1131_observation");
const JSON_OUT = path.join(OUT_DIR, "v1131_loose_range_replay_coverage_extension.json");
const MD_OUT = path.join(OUT_DIR, "v1131_loose_range_replay_coverage_extension.md");

const SOURCE_REPLAY = path.join(ROOT, "reports", "v1131_observation", "v1131_loose_range_replay_report.json");
const SOURCE_WATCH = path.join(ROOT, "reports", "v1130_observation", "v1130_watch_only_telemetry_report.json");
const SOURCE_GATE = path.join(ROOT, "reports", "v1130_observation", "v1130_gate_telemetry_report.json");
const SOURCE_CANDIDATE = path.join(
  ROOT,
  "reports",
  "candidate_search",
  "2026-07-09-v1130-15m-4h-first-pass",
  "candidate_search_summary.json",
);

const MIN_SAMPLE_GATE = 30;
const FEE_BPS = 10;

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function round(value, places = 4) {
  if (!Number.isFinite(Number(value))) return null;
  const factor = 10 ** places;
  return Math.round(Number(value) * factor) / factor;
}

function maxShare(map) {
  const values = Object.values(map || {}).map(Number).filter(Number.isFinite);
  const total = values.reduce((sum, value) => sum + value, 0);
  if (!total) return null;
  return round(Math.max(...values) / total, 4);
}

function sampleStatus(count, gate = MIN_SAMPLE_GATE) {
  if (!Number.isFinite(Number(count))) return "unknown";
  return Number(count) >= gate ? "sufficient_initial" : "thin";
}

function withFee(summary) {
  if (!summary || !Number.isFinite(Number(summary.mean_bps))) return "unknown";
  return round(Number(summary.mean_bps) - FEE_BPS, 2);
}

function rowsFromMap(map) {
  const entries = Object.entries(map || {});
  if (entries.length === 0) return "| none | 0 |";
  return entries.map(([key, value]) => `| \`${key}\` | ${value} |`).join("\n");
}

function buildReport() {
  const replay = readJson(SOURCE_REPLAY);
  const watch = readJson(SOURCE_WATCH);
  const gate = readJson(SOURCE_GATE);
  const candidate = readJson(SOURCE_CANDIDATE);

  const replayEnabled = replay.counts?.enabled ?? replay.enabled_examples?.length ?? null;
  const replayCandidates = replay.counts?.candidates ?? null;
  const watchSummary = watch.summary || {};
  const gateSensitivity = gate.sensitivity || {};
  const candidateTop = (candidate.candidates || []).find((item) => item.candidate_id === "v1130_loose_range_watch");

  const coverageLayers = {
    alpha_screened_replay: {
      state: "observed",
      source: rel(SOURCE_REPLAY),
      candidates: replayCandidates,
      enabled: replayEnabled,
      blocked: replay.counts?.blocked ?? null,
      sample_status: sampleStatus(replayEnabled),
      interpretation: "Closest existing proxy for V11.31 because it includes observed taker-sell blocker evidence.",
    },
    ohlcv_watch_only: {
      state: "observed",
      source: rel(SOURCE_WATCH),
      rows: watchSummary.rows ?? null,
      candidates: watchSummary.watch_candidates ?? null,
      enabled: watchSummary.watch_enabled ?? null,
      watch_only_enabled: watchSummary.watch_only_enabled ?? null,
      sample_status: sampleStatus(watchSummary.watch_enabled),
      interpretation: "Wider OHLCV-only coverage; alpha/taker/protection filters remain unknown.",
    },
    strict_crash_rebound_gate: {
      state: "observed",
      source: rel(SOURCE_GATE),
      candidates: gate.window_summary?.gate_counts?.enabled_crash_rebound_long ?? gateSensitivity.baseline?.enabled ?? null,
      enabled: gateSensitivity.baseline?.enabled ?? null,
      sample_status: sampleStatus(gateSensitivity.baseline?.enabled),
      interpretation: "Stricter V11.30 crash-rebound reference, not the V11.31 loose-range implementation target.",
    },
    sensitivity_combined_looser: {
      state: "derived",
      source: rel(SOURCE_GATE),
      candidates: gateSensitivity.combined_looser?.candidates ?? null,
      enabled: gateSensitivity.combined_looser?.enabled ?? null,
      sample_status: sampleStatus(gateSensitivity.combined_looser?.enabled),
      interpretation: "Sensitivity-only evidence; not V11.31 exact thresholds and not authorized for strategy change.",
    },
  };

  const alphaScreenedGatePass = replayEnabled >= MIN_SAMPLE_GATE;
  const ohlcvGatePass = Number(watchSummary.watch_enabled) >= MIN_SAMPLE_GATE;
  const canReconsiderBacktest = alphaScreenedGatePass;

  return {
    metadata: {
      strategy: "RegimeAwareV1131LooseRangeWatchShadow",
      report_status: "coverage_extension_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [
        rel(SOURCE_REPLAY),
        rel(SOURCE_WATCH),
        rel(SOURCE_GATE),
        rel(SOURCE_CANDIDATE),
      ],
      timeframe: "15m",
      informative_timeframes_used: ["4h"],
      excluded_timeframes: [
        {
          timeframe: "1h",
          reason: "Task 103 found exact futures OHLCV stale; V11.31 currently excludes 1h features.",
        },
      ],
      reads_secret: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      writes_sqlite: false,
    },
    thresholds: {
      entry_tag: "v1131_loose_range_watch_long",
      min_return: 0.004,
      min_range: 0.008,
      min_rsi: 35,
      max_rsi: 62,
      min_volume_ratio: 0.8,
      fee_bps: FEE_BPS,
      minimum_sample_gate: MIN_SAMPLE_GATE,
    },
    coverage_layers: coverageLayers,
    source_quality: {
      alpha_screened_replay: "best_available_proxy",
      ohlcv_watch_only: "wider_but_alpha_taker_unknown",
      strict_gate: "reference_only",
      sensitivity_combined_looser: "not_exact_v1131_thresholds",
    },
    concentration: {
      alpha_screened_enabled_by_pair: replay.concentration?.enabled_by_pair || {},
      alpha_screened_max_pair_share: replay.concentration?.max_pair_share ?? null,
      ohlcv_watch_enabled_by_pair: watchSummary.watch_enabled_by_pair || {},
      ohlcv_watch_max_pair_share: maxShare(watchSummary.watch_enabled_by_pair || {}),
      ohlcv_watch_enabled_by_day: watchSummary.watch_enabled_by_day || {},
    },
    returns: {
      alpha_screened_forward_return_summary: replay.forward_return_summary || {},
      alpha_screened_fee_adjusted_forward_return_summary: replay.fee_adjusted_forward_return_summary || {},
      candidate_search_top_net_return_bps: candidateTop?.net_return_bps ?? "unknown",
      candidate_search_top_fee_adjusted_4_candle_mean_bps: withFee(replay.forward_return_summary?.["4_candle"]),
      candidate_search_top_fee_adjusted_8_candle_mean_bps: withFee(replay.forward_return_summary?.["8_candle"]),
    },
    gate_decision: {
      alpha_screened_replay_gate_pass: alphaScreenedGatePass,
      ohlcv_watch_only_gate_pass: ohlcvGatePass,
      can_reconsider_backtest: canReconsiderBacktest,
      can_deploy_shadow: false,
      can_evaluate_replacement: false,
      conclusion: canReconsiderBacktest
        ? "coverage_reaches_initial_gate_but_still_requires_lifecycle_review"
        : "coverage_extension_does_not_clear_backtest_gate",
      reason: canReconsiderBacktest
        ? "Alpha-screened replay reaches the initial sample gate, but still lacks lifecycle execution evidence."
        : "Alpha-screened replay remains at 23 enabled samples and OHLCV-only watch coverage reaches only 29 with alpha/taker/protection unknown.",
    },
    blocking_gaps: [
      "alpha_screened_enabled_samples_below_30",
      "ohlcv_watch_only_samples_do_not_prove_final_strategy_entry",
      "alpha_taker_protection_unknown_for_wider_watch_layer",
      "no_lifecycle_exit_distribution",
      "no_fill_slippage_funding_latency_model",
      "no_drawdown_path",
      "no_same_window_live_trade_quality_comparison",
    ],
    explicit_non_conclusions: [
      "Does not prove V11.31 is profitable.",
      "Does not prove V11.31 is bad.",
      "Does not authorize a Freqtrade backtest.",
      "Does not authorize deployment or live shadow launch.",
      "Does not conclude V11.31 can replace V10.8.2 or V11.30.",
    ],
    next_required_task: "Task 123: V11.31 Expanded Replay Result Review / Backtest Reconsideration",
  };
}

function assertReport(report) {
  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.modifies_strategy !== false) throw new Error("modifies_strategy must be false");
  if (report.metadata.modifies_bot_config !== false) throw new Error("modifies_bot_config must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.metadata.starts_or_stops_bot !== false) throw new Error("starts_or_stops_bot must be false");
  if (report.metadata.deploys_to_server !== false) throw new Error("deploys_to_server must be false");
  if (report.coverage_layers.alpha_screened_replay.enabled !== 23) {
    throw new Error("Expected alpha-screened replay enabled count to remain 23 from committed evidence.");
  }
  if (report.coverage_layers.ohlcv_watch_only.enabled !== 29) {
    throw new Error("Expected OHLCV watch-only enabled count to remain 29 from committed evidence.");
  }
}

function markdown(report) {
  const layers = Object.entries(report.coverage_layers)
    .map(([name, layer]) => `| \`${name}\` | \`${layer.state}\` | ${layer.candidates ?? "-"} | ${layer.enabled ?? "-"} | \`${layer.sample_status}\` | ${layer.interpretation} |`)
    .join("\n");
  const gaps = report.blocking_gaps.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# V11.31 Loose-Range Replay Coverage Extension

## Summary

This report extends the V11.31 loose-range replay review using committed,
read-only evidence only.

Decision:

\`\`\`text
${report.gate_decision.conclusion}
\`\`\`

The expanded evidence does not authorize immediate backtest or deployment.

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Coverage Layers

| layer | state | candidates | enabled | sample status | interpretation |
|---|---|---:|---:|---|---|
${layers}

## Concentration

Alpha-screened enabled by pair:

| pair | enabled |
|---|---:|
${rowsFromMap(report.concentration.alpha_screened_enabled_by_pair)}

OHLCV watch enabled by pair:

| pair | enabled |
|---|---:|
${rowsFromMap(report.concentration.ohlcv_watch_enabled_by_pair)}

OHLCV watch enabled by day:

| day | enabled |
|---|---:|
${rowsFromMap(report.concentration.ohlcv_watch_enabled_by_day)}

## Return Evidence

| metric | value |
|---|---:|
| alpha-screened fee-adjusted 4-candle mean bps | ${report.returns.candidate_search_top_fee_adjusted_4_candle_mean_bps} |
| alpha-screened fee-adjusted 8-candle mean bps | ${report.returns.candidate_search_top_fee_adjusted_8_candle_mean_bps} |
| candidate-search top net return bps | ${report.returns.candidate_search_top_net_return_bps} |

## Gate Decision

| item | value |
|---|---|
| alpha-screened replay gate pass | \`${report.gate_decision.alpha_screened_replay_gate_pass}\` |
| OHLCV watch-only gate pass | \`${report.gate_decision.ohlcv_watch_only_gate_pass}\` |
| can reconsider backtest | \`${report.gate_decision.can_reconsider_backtest}\` |
| can deploy shadow | \`${report.gate_decision.can_deploy_shadow}\` |
| can evaluate replacement | \`${report.gate_decision.can_evaluate_replacement}\` |
| reason | ${report.gate_decision.reason} |

## Blocking Gaps

${gaps}

## What This Cannot Conclude

${nonConclusions}

## Recommended Next Task

\`\`\`text
${report.next_required_task}
\`\`\`
`;
}

function main() {
  const report = buildReport();
  assertReport(report);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown(report), "utf8");
  console.log(`wrote ${rel(JSON_OUT)}`);
  console.log(`wrote ${rel(MD_OUT)}`);
}

main();

