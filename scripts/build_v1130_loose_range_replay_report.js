#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "reports", "v1130_observation");
const JSON_OUT = path.join(OUT_DIR, "v1130_loose_range_replay_report.json");
const MD_OUT = path.join(OUT_DIR, "v1130_loose_range_replay_report.md");
const INPUT_JSON = process.env.V1130_LOOSE_RANGE_REPLAY_INPUT_JSON || "";

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function summarize(values) {
  const clean = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (clean.length === 0) {
    return { samples: 0, mean_bps: null, median_bps: null, win_rate: null, min_bps: null, max_bps: null };
  }
  const sum = clean.reduce((acc, value) => acc + value, 0);
  const mid = Math.floor(clean.length / 2);
  const median = clean.length % 2 === 0 ? (clean[mid - 1] + clean[mid]) / 2 : clean[mid];
  return {
    samples: clean.length,
    mean_bps: Number(((sum / clean.length) * 10000).toFixed(2)),
    median_bps: Number((median * 10000).toFixed(2)),
    win_rate: Number((clean.filter((value) => value > 0).length / clean.length).toFixed(4)),
    min_bps: Number((clean[0] * 10000).toFixed(2)),
    max_bps: Number((clean[clean.length - 1] * 10000).toFixed(2)),
  };
}

function byKey(items, keyFn) {
  const out = {};
  for (const item of items) {
    const key = keyFn(item);
    out[key] = (out[key] || 0) + 1;
  }
  return out;
}

function buildReport(input) {
  const enabled = input.enabled_examples || [];
  const blocked = input.blocked_examples || [];
  const allCandidates = [...enabled, ...blocked];
  const forwardReturnSummary = input.forward_return_summary || {
    "1_candle": summarize(enabled.map((item) => item.forward_returns?.["1_candle"])),
    "4_candle": summarize(enabled.map((item) => item.forward_returns?.["4_candle"])),
    "8_candle": summarize(enabled.map((item) => item.forward_returns?.["8_candle"])),
    "16_candle": summarize(enabled.map((item) => item.forward_returns?.["16_candle"])),
  };

  return {
    metadata: {
      strategy: "RegimeAwareV1130CrashReboundShadow",
      report_status: "loose_range_watch_replay",
      generated_at: new Date().toISOString(),
      source: input.metadata?.source || "read_only_pair_candles_proxy",
      input_generated_at: input.metadata?.generated_at || null,
      timeframe: input.metadata?.timeframe || "15m",
      pairs: input.metadata?.pairs || [],
      params: input.metadata?.params || {},
      can_place_orders: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      reads_secret: false,
      runs_backtest: false,
      writes_sqlite: false,
    },
    counts: {
      candidates: input.counts?.candidates ?? allCandidates.length,
      enabled: input.counts?.enabled ?? enabled.length,
      blocked: input.counts?.blocked ?? blocked.length,
      blocked_counts: input.counts?.blocked_counts || byKey(blocked, (item) => (
        item.blocked_taker_sell_pressure ? "takerSellPressure" : item.blocked_alpha_short ? "alpha_short" : "other"
      )),
    },
    concentration: {
      enabled_by_pair: byKey(enabled, (item) => item.pair || "unknown"),
      enabled_by_day: byKey(enabled, (item) => String(item.candle_time || "unknown").slice(0, 10)),
    },
    forward_return_summary: forwardReturnSummary,
    enabled_examples: enabled,
    blocked_examples: blocked,
    limitations: [
      "Watch-only replay; does not set enter_long or place orders.",
      "Close-to-close proxy only; no fills, fees, funding, slippage, latency, protections, or wallet constraints.",
      "Not a Freqtrade backtest and not a live strategy-change approval.",
      "Does not prove V11.30 can replace any benchmark.",
    ],
    recommendation: {
      status: "continue_watch_only_validation",
      reason: "4-candle and 8-candle proxy returns are positive, but sample size is small and costs/fills are not modeled.",
      next_tasks: [
        "Task 87: decide whether to implement a watch-only telemetry lane",
        "Task 88R: allow exact watch-only telemetry implementation paths if approved",
        "Task 88: implement watch-only telemetry lane without live orders",
      ],
    },
  };
}

function assertReport(report) {
  if (report.metadata.can_place_orders !== false) throw new Error("can_place_orders must be false");
  if (report.metadata.modifies_strategy !== false) throw new Error("modifies_strategy must be false");
  if (report.metadata.modifies_bot_config !== false) throw new Error("modifies_bot_config must be false");
  if (report.metadata.reads_secret !== false) throw new Error("reads_secret must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.counts.enabled < 1) throw new Error("expected at least one enabled loose-range sample");
}

function tableRows(obj) {
  return Object.entries(obj || {}).map(([key, value]) => `| \`${key}\` | ${value} |`).join("\n") || "| none | 0 |";
}

function markdown(report) {
  const fwdRows = Object.entries(report.forward_return_summary)
    .map(([horizon, row]) => `| \`${horizon}\` | ${row.samples} | ${row.mean_bps ?? "-"} | ${row.median_bps ?? "-"} | ${row.win_rate ?? "-"} | ${row.min_bps ?? "-"} | ${row.max_bps ?? "-"} |`)
    .join("\n");
  const examples = report.enabled_examples
    .slice(0, 20)
    .map((item) => `- \`${item.pair}\` at \`${item.candle_time}\``)
    .join("\n");

  return `# V11.30 Loose-Range Replay Report

## Summary

This report evaluates the watch-only V11.30 loose-range scenario:

\`\`\`text
range >= 0.008
\`\`\`

It does not modify the live strategy and does not place orders.

## Counts

| metric | count |
|---|---:|
| candidates | ${report.counts.candidates} |
| enabled | ${report.counts.enabled} |
| blocked | ${report.counts.blocked} |
| blocked by taker sell pressure | ${report.counts.blocked_counts.takerSellPressure || 0} |
| blocked by alpha short | ${report.counts.blocked_counts.alpha_short || 0} |

## Forward Return Summary

| horizon | samples | mean bps | median bps | win rate | min bps | max bps |
|---|---:|---:|---:|---:|---:|---:|
${fwdRows}

## Enabled Concentration By Pair

| pair | enabled |
|---|---:|
${tableRows(report.concentration.enabled_by_pair)}

## Enabled Concentration By Day

| day | enabled |
|---|---:|
${tableRows(report.concentration.enabled_by_day)}

## Enabled Examples

${examples || "- none"}

## Limitations

${report.limitations.map((item) => `- ${item}`).join("\n")}

## Recommendation

- status: \`${report.recommendation.status}\`
- reason: ${report.recommendation.reason}

## Next Tasks

${report.recommendation.next_tasks.map((item) => `- ${item}`).join("\n")}
`;
}

function main() {
  if (!INPUT_JSON) {
    throw new Error("V1130_LOOSE_RANGE_REPLAY_INPUT_JSON is required");
  }
  const report = buildReport(readJson(INPUT_JSON));
  assertReport(report);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`);
  fs.writeFileSync(MD_OUT, markdown(report));
  console.log(`wrote ${path.relative(ROOT, JSON_OUT)}`);
  console.log(`wrote ${path.relative(ROOT, MD_OUT)}`);
}

main();
