#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1131_observation");
const JSON_OUT = path.join(OUT_DIR, "v1131_longer_replay_data_source_inventory.json");
const MD_OUT = path.join(OUT_DIR, "v1131_longer_replay_data_source_inventory.md");

const WINDOW_JSON = path.join(OUT_DIR, "v1131_longer_replay_window_inventory.json");
const COVERAGE_JSON = path.join(OUT_DIR, "v1131_loose_range_replay_coverage_extension.json");
const WATCH_JSON = path.join(ROOT, "reports", "v1130_observation", "v1130_watch_only_telemetry_report.json");
const TASK136 = path.join(ROOT, "reports", "audits", "task136_v1131_longer_replay_window_data_source_authorization.md");

function rel(file) {
  return path.relative(ROOT, file).replace(/\\/g, "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function buildReport() {
  const windowInventory = readJson(WINDOW_JSON);
  const coverage = readJson(COVERAGE_JSON);
  const watch = readJson(WATCH_JSON);

  const committed15m = windowInventory.committed_window_inventory?.["15m"] || {};
  const committed4h = windowInventory.committed_window_inventory?.["4h"] || {};
  const pairs = committed15m.pairs || watch.metadata?.pairs || [];
  const dataSources = watch.data_sources || [];

  const sourceRows = pairs.map((pair) => {
    const source = dataSources.find((item) => item.pair === pair) || {};
    return {
      pair,
      "15m_source_state": source.exists === true ? "observed" : "unknown",
      "15m_path": source.path || "unknown",
      "15m_total_rows": source.rows ?? "unknown",
      "15m_latest_window": source.latest_window || committed15m.latest_candle_time || "unknown",
      committed_replay_rows_per_pair: committed15m.rows_per_pair ?? "unknown",
      committed_replay_days_per_pair: committed15m.approximate_days_per_pair ?? "unknown",
      "4h_source_state": committed4h.state || "unknown",
      "4h_path": "unknown",
      "4h_row_count": "unknown",
    };
  });

  const report = {
    metadata: {
      strategy: "RegimeAwareV1131LooseRangeWatchShadow",
      report_status: "longer_replay_data_source_inventory_from_committed_read_only_evidence",
      generated_at: new Date().toISOString(),
      sources: [rel(WINDOW_JSON), rel(COVERAGE_JSON), rel(WATCH_JSON), rel(TASK136)],
      reads_secret: false,
      reads_env_files: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      runs_backtest: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
      downloads_or_refreshes_data: false,
      writes_sqlite: false,
    },
    approved_pair_set: {
      state: "observed",
      pairs,
      source: rel(WATCH_JSON),
    },
    data_source_inventory: {
      "15m": {
        state: "observed",
        source: rel(WATCH_JSON),
        data_kind: "server_read_only_feather_snapshot_report",
        total_rows_per_pair_in_source: dataSources.length > 0 ? dataSources[0].rows : "unknown",
        committed_replay_rows_per_pair: committed15m.rows_per_pair ?? "unknown",
        committed_replay_days_per_pair: committed15m.approximate_days_per_pair ?? "unknown",
        latest_committed_candle: committed15m.latest_candle_time || watch.summary?.latest_candle_time || "unknown",
        supports_1d_review: committed15m.supports_1d_review ?? "unknown",
        supports_7d_review: committed15m.supports_7d_review ?? "unknown",
        supports_14d_review: committed15m.supports_14d_review ?? "unknown",
        longer_source_may_exist: dataSources.every((item) => Number(item.rows) > Number(committed15m.rows_per_pair || 0)),
        caveat: "Committed replay output still uses only the latest 240 15m candles per pair.",
      },
      "4h": {
        state: committed4h.state || "unknown",
        source: rel(WINDOW_JSON),
        data_kind: "informative_timeframe_required_but_not_row_level_inventory",
        path: "unknown",
        rows: "unknown",
        supports_7d_review: committed4h.supports_7d_review ?? "unknown",
        supports_14d_review: committed4h.supports_14d_review ?? "unknown",
        caveat: committed4h.reason || "4h row-level source was not included in committed evidence.",
      },
      "1h": {
        state: "excluded",
        reason: "V11.31 currently excludes 1h features because earlier checks marked exact futures OHLCV stale.",
      },
    },
    per_pair_sources: sourceRows,
    alpha_taker_protection_status: {
      wider_window_alpha_flags: {
        state: "unknown",
        reason: "Committed wider watch layer is OHLCV-only.",
      },
      wider_window_taker_buy_pressure: {
        state: "unknown",
        reason: "No committed taker-buy pressure source is available for the longer window.",
      },
      wider_window_taker_sell_pressure: {
        state: "unknown",
        reason: "No committed taker-sell pressure source is available for the longer window.",
      },
      protection_or_pairlock_state: {
        state: "unknown",
        reason: "No committed protection/pairlock timeline is available for the longer window.",
      },
    },
    replay_gate_state: {
      alpha_screened_enabled: coverage.coverage_layers?.alpha_screened_replay?.enabled ?? "unknown",
      ohlcv_watch_only_enabled: coverage.coverage_layers?.ohlcv_watch_only?.enabled ?? "unknown",
      sample_gate: coverage.thresholds?.minimum_sample_gate ?? 30,
      can_reconsider_backtest: false,
      can_deploy_shadow: false,
      can_evaluate_replacement: false,
      reason: "Longer source may exist in server feather paths, but committed evidence has not produced an aligned 7d/14d 15m+4h replay with alpha/taker/protection state.",
    },
    authorized_next_questions: [
      "confirm_longer_15m_window_by_exact_pair_set",
      "confirm_aligned_4h_informative_window",
      "confirm_7d_and_14d_coverage",
      "confirm_or_mark_unknown_alpha_taker_protection_state",
      "only_then_reconsider_backtest_gate",
    ],
    explicit_non_conclusions: [
      "Does not prove V11.31 is profitable.",
      "Does not prove V11.31 is bad.",
      "Does not authorize a Freqtrade backtest.",
      "Does not authorize deployment or live shadow launch.",
      "Does not conclude V11.31 can replace V10.8.2, V11.29, or V11.30.",
    ],
    next_recommended_task: "Task 148: V11.31 Longer Replay Data Acquisition Authorization",
  };

  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.replay_gate_state.can_reconsider_backtest !== false) {
    throw new Error("backtest reconsideration must remain false");
  }
  return report;
}

function sourceRows(rows) {
  return rows
    .map((item) => `| \`${item.pair}\` | \`${item["15m_source_state"]}\` | ${item["15m_total_rows"]} | \`${item["15m_latest_window"]}\` | ${item.committed_replay_rows_per_pair} | ${item.committed_replay_days_per_pair} | \`${item["4h_source_state"]}\` |`)
    .join("\n");
}

function markdown(report) {
  const alphaRows = Object.entries(report.alpha_taker_protection_status)
    .map(([field, item]) => `| \`${field}\` | \`${item.state}\` | ${item.reason} |`)
    .join("\n");
  const nextQuestions = report.authorized_next_questions.map((item) => `- \`${item}\``).join("\n");
  const nonConclusions = report.explicit_non_conclusions.map((item) => `- ${item}`).join("\n");

  return `# V11.31 Longer Replay Data Source Inventory

## Summary

This report inventories V11.31 longer replay data-source readiness from
committed read-only evidence only. It does not connect to the server, download
data, run a backtest, modify strategy files, or modify bot config.

Decision:

\`\`\`text
longer_replay_data_source_inventory_incomplete
\`\`\`

## Sources

${report.metadata.sources.map((source) => `- \`${source}\``).join("\n")}

## Data Source Inventory

| timeframe | state | kind | 7d support | 14d support | caveat |
|---|---|---|---|---|---|
| 15m | \`${report.data_source_inventory["15m"].state}\` | \`${report.data_source_inventory["15m"].data_kind}\` | \`${report.data_source_inventory["15m"].supports_7d_review}\` | \`${report.data_source_inventory["15m"].supports_14d_review}\` | ${report.data_source_inventory["15m"].caveat} |
| 4h | \`${report.data_source_inventory["4h"].state}\` | \`${report.data_source_inventory["4h"].data_kind}\` | \`${report.data_source_inventory["4h"].supports_7d_review}\` | \`${report.data_source_inventory["4h"].supports_14d_review}\` | ${report.data_source_inventory["4h"].caveat} |
| 1h | \`${report.data_source_inventory["1h"].state}\` | n/a | n/a | n/a | ${report.data_source_inventory["1h"].reason} |

## Per-Pair Source Matrix

| pair | 15m source | 15m total rows | latest 15m source window | committed replay rows | committed replay days | 4h source |
|---|---|---:|---|---:|---:|---|
${sourceRows(report.per_pair_sources)}

## Alpha/Taker/Protection Status

| field | state | reason |
|---|---|---|
${alphaRows}

## Replay Gate State

| item | value |
|---|---|
| alpha-screened enabled | ${report.replay_gate_state.alpha_screened_enabled} |
| OHLCV watch-only enabled | ${report.replay_gate_state.ohlcv_watch_only_enabled} |
| sample gate | ${report.replay_gate_state.sample_gate} |
| can reconsider backtest | \`${report.replay_gate_state.can_reconsider_backtest}\` |
| can deploy shadow | \`${report.replay_gate_state.can_deploy_shadow}\` |
| reason | ${report.replay_gate_state.reason} |

## Authorized Next Questions

${nextQuestions}

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
