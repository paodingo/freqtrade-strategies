#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1131_observation");
const JSON_OUT = path.join(OUT_DIR, "v1131_loose_range_replay_report.json");
const MD_OUT = path.join(OUT_DIR, "v1131_loose_range_replay_report.md");
const INPUT_JSON = path.join(ROOT, "reports", "v1130_observation", "v1130_loose_range_replay_report.json");
const STRATEGY_PATH = "strategies/RegimeAwareV1131LooseRangeWatchShadow.py";
const CONFIG_PATH = "user_data/config_multi_futures_v1131_loose_range_watch_shadow.json";
const FEE_BPS = 10;
const MIN_SAMPLE_GATE = 30;

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function round(value, places = 4) {
  if (!Number.isFinite(Number(value))) {
    return null;
  }
  const factor = 10 ** places;
  return Math.round(Number(value) * factor) / factor;
}

function summarizeBps(values) {
  const clean = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (clean.length === 0) {
    return { samples: 0, mean_bps: null, median_bps: null, win_rate: null, min_bps: null, max_bps: null };
  }
  const sum = clean.reduce((acc, value) => acc + value, 0);
  const mid = Math.floor(clean.length / 2);
  const median = clean.length % 2 === 0 ? (clean[mid - 1] + clean[mid]) / 2 : clean[mid];
  return {
    samples: clean.length,
    mean_bps: round((sum / clean.length) * 10000, 2),
    median_bps: round(median * 10000, 2),
    win_rate: round(clean.filter((value) => value > 0).length / clean.length, 4),
    min_bps: round(clean[0] * 10000, 2),
    max_bps: round(clean[clean.length - 1] * 10000, 2),
  };
}

function withFee(summary) {
  if (!summary || summary.samples === 0) {
    return { samples: 0, mean_bps: null, median_bps: null, win_rate: null, min_bps: null, max_bps: null, fee_bps: FEE_BPS };
  }
  return {
    samples: summary.samples,
    mean_bps: round(summary.mean_bps - FEE_BPS, 2),
    median_bps: round(summary.median_bps - FEE_BPS, 2),
    win_rate: summary.win_rate,
    min_bps: round(summary.min_bps - FEE_BPS, 2),
    max_bps: round(summary.max_bps - FEE_BPS, 2),
    fee_bps: FEE_BPS,
  };
}

function countBy(items, keyFn) {
  const result = {};
  for (const item of items) {
    const key = keyFn(item);
    result[key] = (result[key] || 0) + 1;
  }
  return result;
}

function maxShare(map) {
  const values = Object.values(map || {}).map(Number).filter((value) => Number.isFinite(value));
  const total = values.reduce((acc, value) => acc + value, 0);
  if (!total) return null;
  return round(Math.max(...values) / total, 4);
}

function recomputeForward(enabled) {
  const horizons = ["1_candle", "4_candle", "8_candle", "16_candle"];
  const output = {};
  for (const horizon of horizons) {
    output[horizon] = summarizeBps(enabled.map((item) => item.forward_returns?.[horizon]));
  }
  return output;
}

function buildReport() {
  const source = readJson(INPUT_JSON);
  const config = readJson(path.join(ROOT, CONFIG_PATH));
  const enabled = source.enabled_examples || [];
  const blocked = source.blocked_examples || [];
  const forward = source.forward_return_summary || recomputeForward(enabled);
  const feeAdjusted = Object.fromEntries(Object.entries(forward).map(([key, value]) => [key, withFee(value)]));
  const enabledByPair = countBy(enabled, (item) => item.pair || "unknown");
  const enabledByDay = countBy(enabled, (item) => String(item.candle_time || "unknown").slice(0, 10));

  return {
    metadata: {
      strategy: "RegimeAwareV1131LooseRangeWatchShadow",
      report_status: "v1131_loose_range_watch_replay_from_existing_evidence",
      generated_at: new Date().toISOString(),
      source_report: path.relative(ROOT, INPUT_JSON).replace(/\\/g, "/"),
      strategy_path: STRATEGY_PATH,
      config_path: CONFIG_PATH,
      timeframe: "15m",
      informative_timeframes_used: ["4h"],
      excluded_timeframes: [{ timeframe: "1h", reason: "Task 103 found exact 1h futures OHLCV stale" }],
      pairs: config.exchange?.pair_whitelist || [],
      fee_bps: FEE_BPS,
      can_place_orders: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      reads_secret: false,
      runs_backtest: false,
      writes_sqlite: false,
      starts_or_stops_bot: false,
      deploys_to_server: false,
    },
    params: {
      entry_tag: "v1131_loose_range_watch_long",
      min_return: 0.004,
      min_range: 0.008,
      min_rsi: 35,
      max_rsi: 62,
      min_volume_ratio: 0.8,
      take_profit: 0.008,
      overbought_rsi: 68,
      time_exit_minutes: 120,
    },
    counts: {
      candidates: source.counts?.candidates ?? enabled.length + blocked.length,
      enabled: source.counts?.enabled ?? enabled.length,
      blocked: source.counts?.blocked ?? blocked.length,
      blocked_counts: source.counts?.blocked_counts || countBy(blocked, (item) => (
        item.blocked_taker_sell_pressure ? "takerSellPressure" : item.blocked_alpha_short ? "alpha_short" : "other"
      )),
    },
    concentration: {
      enabled_by_pair: enabledByPair,
      enabled_by_day: enabledByDay,
      max_pair_share: maxShare(enabledByPair),
    },
    forward_return_summary: forward,
    fee_adjusted_forward_return_summary: feeAdjusted,
    sample_status: {
      status: enabled.length >= MIN_SAMPLE_GATE ? "sufficient_initial" : "thin",
      enabled_samples: enabled.length,
      minimum_gate: MIN_SAMPLE_GATE,
      reason: enabled.length >= MIN_SAMPLE_GATE ? "enabled sample count reaches the initial gate" : "enabled sample count is below the initial gate",
    },
    data_quality: {
      data_mode: "existing_report_replay_aggregation",
      uses_fresh_15m_and_4h_lane: true,
      uses_1h: false,
      one_hour_status: "excluded_stale",
      backtest_status: "not_run",
      execution_quality_status: "not_measured",
    },
    enabled_examples: enabled,
    blocked_examples: blocked,
    limitations: [
      "Derived from existing V11.30 loose-range replay evidence because V11.31 uses the same loose-range entry thresholds.",
      "Not a Freqtrade backtest.",
      "No fills, funding, slippage, latency, protections, wallet constraints, or order book execution quality are modeled.",
      "Exit distribution is not proven; forward returns are close-to-close proxies.",
      "1h OHLCV is excluded because the exact futures 1h data was stale in Task 103.",
      "Does not prove V11.31 can replace V10.8.2 or V11.30.",
    ],
    verdict: {
      report_status: "replay_planning_evidence",
      can_proceed_to_backtest_plan: false,
      can_deploy_shadow: false,
      can_evaluate_replacement: false,
      reason: "The replay has positive 4/8 candle proxy evidence but only 23 enabled samples and no execution-quality model.",
      next_required_task: "Task 117: V11.31 Replay Result Review / Backtest Go-No-Go",
    },
  };
}

function assertReport(report) {
  if (report.metadata.can_place_orders !== false) throw new Error("can_place_orders must be false");
  if (report.metadata.modifies_strategy !== false) throw new Error("modifies_strategy must be false");
  if (report.metadata.modifies_bot_config !== false) throw new Error("modifies_bot_config must be false");
  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.metadata.starts_or_stops_bot !== false) throw new Error("starts_or_stops_bot must be false");
  if (report.metadata.excluded_timeframes[0].timeframe !== "1h") throw new Error("1h stale exclusion must be explicit");
}

function tableRows(map) {
  return Object.entries(map || {}).map(([key, value]) => `| \`${key}\` | ${value} |`).join("\n") || "| none | 0 |";
}

function markdown(report) {
  const fwdRows = Object.entries(report.forward_return_summary)
    .map(([horizon, row]) => `| \`${horizon}\` | ${row.samples} | ${row.mean_bps ?? "-"} | ${row.median_bps ?? "-"} | ${row.win_rate ?? "-"} | ${row.min_bps ?? "-"} | ${row.max_bps ?? "-"} |`)
    .join("\n");
  const feeRows = Object.entries(report.fee_adjusted_forward_return_summary)
    .map(([horizon, row]) => `| \`${horizon}\` | ${row.samples} | ${row.mean_bps ?? "-"} | ${row.median_bps ?? "-"} | ${row.fee_bps} |`)
    .join("\n");

  return `# V11.31 Loose-Range Watch Replay Report

## Summary

This is a read-only replay-planning report for:

\`\`\`text
RegimeAwareV1131LooseRangeWatchShadow
\`\`\`

It reuses existing V11.30 loose-range replay evidence because V11.31 implements
the same loose-range entry thresholds as a local shadow strategy.

## Data Gate

| item | value |
|---|---|
| timeframe | \`${report.metadata.timeframe}\` |
| informative timeframes | \`${report.metadata.informative_timeframes_used.join(",")}\` |
| excluded timeframe | \`1h: ${report.metadata.excluded_timeframes[0].reason}\` |
| backtest run | \`${report.metadata.runs_backtest}\` |
| strategy modified by report | \`${report.metadata.modifies_strategy}\` |
| bot config modified by report | \`${report.metadata.modifies_bot_config}\` |
| server operation | \`${report.metadata.starts_or_stops_bot}\` |

## Counts

| metric | count |
|---|---:|
| candidates | ${report.counts.candidates} |
| enabled | ${report.counts.enabled} |
| blocked | ${report.counts.blocked} |
| blocked by taker sell pressure | ${report.counts.blocked_counts.takerSellPressure || 0} |
| blocked by alpha short | ${report.counts.blocked_counts.alpha_short || 0} |

## Forward Returns

| horizon | samples | mean bps | median bps | win rate | min bps | max bps |
|---|---:|---:|---:|---:|---:|---:|
${fwdRows}

## Fee-Adjusted Forward Returns

| horizon | samples | mean bps | median bps | fee bps |
|---|---:|---:|---:|---:|
${feeRows}

## Concentration

| pair | enabled |
|---|---:|
${tableRows(report.concentration.enabled_by_pair)}

max_pair_share: \`${report.concentration.max_pair_share}\`

## Sample Status

- status: \`${report.sample_status.status}\`
- enabled_samples: \`${report.sample_status.enabled_samples}\`
- minimum_gate: \`${report.sample_status.minimum_gate}\`
- reason: ${report.sample_status.reason}

## Limitations

${report.limitations.map((item) => `- ${item}`).join("\n")}

## Verdict

- can_proceed_to_backtest_plan: \`${report.verdict.can_proceed_to_backtest_plan}\`
- can_deploy_shadow: \`${report.verdict.can_deploy_shadow}\`
- can_evaluate_replacement: \`${report.verdict.can_evaluate_replacement}\`
- reason: ${report.verdict.reason}
- next_required_task: \`${report.verdict.next_required_task}\`
`;
}

function main() {
  const report = buildReport();
  assertReport(report);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown(report), "utf8");
  console.log(`wrote ${path.relative(ROOT, JSON_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, MD_OUT)}`);
}

main();
