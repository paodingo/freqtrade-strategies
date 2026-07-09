#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1131_observation");
const JSON_OUT = path.join(OUT_DIR, "v1131_longer_replay_window_inventory.json");
const MD_OUT = path.join(OUT_DIR, "v1131_longer_replay_window_inventory.md");

const COVERAGE_JSON = path.join(OUT_DIR, "v1131_loose_range_replay_coverage_extension.json");
const WATCH_JSON = path.join(ROOT, "reports", "v1130_observation", "v1130_watch_only_telemetry_report.json");
const TASK124_PLAN = path.join(ROOT, "reports", "audits", "task124_v1131_longer_replay_window_acquisition_plan.md");

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function readTextIfExists(file) {
  return fs.existsSync(file) ? fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "") : "";
}

function isoDate(value) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function subtractHours(iso, hours) {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Date(parsed.getTime() - hours * 60 * 60 * 1000).toISOString();
}

function sampleStatus(count, gate) {
  if (!Number.isFinite(Number(count))) return "unknown";
  return Number(count) >= gate ? "sufficient_initial" : "thin";
}

function buildReport() {
  const coverage = readJson(COVERAGE_JSON);
  const watch = readJson(WATCH_JSON);
  const task124 = readTextIfExists(TASK124_PLAN);

  const pairs = watch.metadata?.pairs || [];
  const rows = Number(watch.summary?.rows ?? 0);
  const rowsPerPair = pairs.length ? rows / pairs.length : null;
  const candlesPerDay15m = 96;
  const committed15mDays = Number.isFinite(rowsPerPair) ? rowsPerPair / candlesPerDay15m : null;
  const latestCandle = isoDate(watch.summary?.latest_candle_time || watch.metadata?.data_sources?.[0]?.latest_window);
  const earliestApprox = latestCandle && Number.isFinite(rowsPerPair)
    ? subtractHours(latestCandle, Math.max(rowsPerPair - 1, 0) * 0.25)
    : null;

  const alphaEnabled = coverage.coverage_layers?.alpha_screened_replay?.enabled ?? null;
  const ohlcvEnabled = coverage.coverage_layers?.ohlcv_watch_only?.enabled ?? null;
  const sampleGate = coverage.thresholds?.minimum_sample_gate ?? 30;

  const task124MentionsServerAcquisition = /server|scp|snapshot|data source|download/i.test(task124);

  const inventory = {
    metadata: {
      strategy: "RegimeAwareV1131LooseRangeWatchShadow",
      report_status: "longer_replay_window_inventory_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [rel(COVERAGE_JSON), rel(WATCH_JSON), rel(TASK124_PLAN)],
      reads_secret: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      writes_sqlite: false,
    },
    committed_window_inventory: {
      "15m": {
        state: "observed",
        source: rel(WATCH_JSON),
        pairs,
        rows,
        rows_per_pair: rowsPerPair,
        latest_candle_time: latestCandle,
        earliest_candle_time_approx: earliestApprox,
        approximate_days_per_pair: committed15mDays,
        supports_1d_review: committed15mDays >= 1,
        supports_7d_review: committed15mDays >= 7,
        supports_14d_review: committed15mDays >= 14,
      },
      "4h": {
        state: "unknown",
        source: rel(COVERAGE_JSON),
        reason: "Committed V11.31 coverage evidence says 4h informative features were used, but does not include row-level 4h window inventory.",
        supports_1d_review: "unknown",
        supports_7d_review: "unknown",
        supports_14d_review: "unknown",
      },
      "1h": {
        state: "excluded",
        reason: "Earlier readiness work marked exact futures OHLCV stale; V11.31 currently excludes 1h features.",
      },
    },
    replay_sample_inventory: {
      alpha_screened_replay_enabled: {
        state: "observed",
        value: alphaEnabled,
        sample_gate: sampleGate,
        sample_status: sampleStatus(alphaEnabled, sampleGate),
      },
      ohlcv_watch_only_enabled: {
        state: "observed",
        value: ohlcvEnabled,
        sample_gate: sampleGate,
        sample_status: sampleStatus(ohlcvEnabled, sampleGate),
      },
      alpha_taker_protection_for_wider_window: {
        state: "unknown",
        reason: "Wider committed watch layer is OHLCV-only and does not prove final strategy entry after alpha/taker/protection filters.",
      },
    },
    readiness_decision: {
      can_reconsider_backtest: false,
      can_deploy_shadow: false,
      can_evaluate_replacement: false,
      conclusion: "longer_window_data_not_yet_available_in_committed_evidence",
      reason: "Committed evidence covers about 2.5 days of 15m watch data and does not expose a 7d/14d alpha-screened replay or row-level 4h inventory.",
    },
    required_before_backtest_reconsideration: [
      "authorized_longer_15m_window_inventory",
      "authorized_4h_informative_window_inventory",
      "alpha_taker_protection_reconstruction_or_explicit_unknown_marking",
      "sample_count_after_final_filters_at_or_above_gate",
      "per_pair_and_per_day_concentration_review",
    ],
    task124_alignment: {
      source_mentions_server_or_data_acquisition: task124MentionsServerAcquisition,
      action_this_task: "no_server_access_no_download_no_backtest",
    },
    explicit_non_conclusions: [
      "Does not prove V11.31 is profitable.",
      "Does not prove V11.31 is bad.",
      "Does not authorize a Freqtrade backtest.",
      "Does not authorize deployment or live shadow launch.",
      "Does not conclude V11.31 can replace V10.8.2, V11.29, or V11.30.",
    ],
    next_recommended_task: "Task 136: V11.31 Longer Replay Window Data Source Authorization",
  };

  if (inventory.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (inventory.metadata.modifies_strategy !== false) throw new Error("modifies_strategy must be false");
  if (inventory.metadata.modifies_bot_config !== false) throw new Error("modifies_bot_config must be false");
  if (inventory.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (inventory.replay_sample_inventory.alpha_screened_replay_enabled.value !== 23) {
    throw new Error("Expected alpha-screened replay enabled count to remain 23 from committed evidence.");
  }
  if (inventory.replay_sample_inventory.ohlcv_watch_only_enabled.value !== 29) {
    throw new Error("Expected OHLCV watch-only enabled count to remain 29 from committed evidence.");
  }

  return inventory;
}

function markdown(report) {
  const window15m = report.committed_window_inventory["15m"];
  const window4h = report.committed_window_inventory["4h"];
  const gaps = report.required_before_backtest_reconsideration.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# V11.31 Longer Replay Window Inventory

## Summary

This inventory uses committed read-only evidence only. It does not access the
server, refresh market data, run a backtest, or modify strategy/config files.

Decision:

\`\`\`text
${report.readiness_decision.conclusion}
\`\`\`

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Committed Window Inventory

| timeframe | state | rows | rows per pair | approximate days per pair | latest candle | 7d support | 14d support |
|---|---|---:|---:|---:|---|---|---|
| 15m | \`${window15m.state}\` | ${window15m.rows} | ${window15m.rows_per_pair} | ${window15m.approximate_days_per_pair} | \`${window15m.latest_candle_time}\` | \`${window15m.supports_7d_review}\` | \`${window15m.supports_14d_review}\` |
| 4h | \`${window4h.state}\` | unknown | unknown | unknown | unknown | \`${window4h.supports_7d_review}\` | \`${window4h.supports_14d_review}\` |
| 1h | \`excluded\` | n/a | n/a | n/a | n/a | n/a | n/a |

## Replay Sample Inventory

| layer | state | value | gate | sample status |
|---|---|---:|---:|---|
| alpha-screened replay enabled | \`${report.replay_sample_inventory.alpha_screened_replay_enabled.state}\` | ${report.replay_sample_inventory.alpha_screened_replay_enabled.value} | ${report.replay_sample_inventory.alpha_screened_replay_enabled.sample_gate} | \`${report.replay_sample_inventory.alpha_screened_replay_enabled.sample_status}\` |
| OHLCV watch-only enabled | \`${report.replay_sample_inventory.ohlcv_watch_only_enabled.state}\` | ${report.replay_sample_inventory.ohlcv_watch_only_enabled.value} | ${report.replay_sample_inventory.ohlcv_watch_only_enabled.sample_gate} | \`${report.replay_sample_inventory.ohlcv_watch_only_enabled.sample_status}\` |
| alpha/taker/protection for wider window | \`${report.replay_sample_inventory.alpha_taker_protection_for_wider_window.state}\` | unknown | ${report.replay_sample_inventory.alpha_screened_replay_enabled.sample_gate} | \`unknown\` |

## Decision

| item | value |
|---|---|
| can reconsider backtest | \`${report.readiness_decision.can_reconsider_backtest}\` |
| can deploy shadow | \`${report.readiness_decision.can_deploy_shadow}\` |
| can evaluate replacement | \`${report.readiness_decision.can_evaluate_replacement}\` |
| reason | ${report.readiness_decision.reason} |

## Required Before Backtest Reconsideration

${gaps}

## Task 124 Alignment

| item | value |
|---|---|
| source mentions server/data acquisition | \`${report.task124_alignment.source_mentions_server_or_data_acquisition}\` |
| action this task | \`${report.task124_alignment.action_this_task}\` |

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
