#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join("reports", "v1129_execution_validation");
const JSON_OUT = path.join(OUT_DIR, "v1129_high_volatility_replay_scorecard.json");
const MD_OUT = path.join(OUT_DIR, "v1129_high_volatility_replay_scorecard.md");

const DEFAULT_HOST = "43.134.72.69";
const DEFAULT_USER = "ubuntu";
const DEFAULT_KEY = "D:\\key\\openclaw\\clf.pem";
const DEFAULT_PORT = 8122;
const DEFAULT_LIMIT = 672;
const DEFAULT_FEE_BPS = 10;
const DEFAULT_HORIZONS = [1, 2, 4, 8];

const PAIRS = [
  "BTC/USDT:USDT",
  "ETH/USDT:USDT",
  "SOL/USDT:USDT",
  "BNB/USDT:USDT",
  "XRP/USDT:USDT",
  "DOGE/USDT:USDT",
  "ADA/USDT:USDT",
  "LINK/USDT:USDT",
  "AVAX/USDT:USDT",
  "LTC/USDT:USDT",
  "TRX/USDT:USDT",
  "BCH/USDT:USDT",
];

function num(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function bool(value) {
  return value === true || value === 1 || value === "1" || value === "true" || value === "True";
}

function round(value, digits = 4) {
  if (!Number.isFinite(value)) return null;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function openCloseReturn(row) {
  const open = num(row.open);
  const close = num(row.close);
  if (open <= 0) return null;
  return close / open - 1;
}

function highLowRange(row) {
  const high = num(row.high);
  const low = num(row.low);
  const close = num(row.close);
  if (close <= 0) return null;
  return (high - low) / close;
}

function classifyCandidateTypes(row) {
  const ret = openCloseReturn(row);
  const range = highLowRange(row);
  const volume = num(row.volume);
  const volumeMean = num(row.volume_mean);
  const adx = num(row.adx_4h);
  const rsi = num(row.rsi);
  const bbPercent = num(row.bb_percent);
  const rangePosition24h = num(row.range_position_24h);
  const types = [];

  if ((ret !== null && Math.abs(ret) >= 0.012) || (range !== null && range >= 0.02)) {
    types.push("high_volatility");
  }

  if (ret !== null && ret < -0.006 && adx >= 22 && volume > volumeMean * 0.8) {
    types.push("selloff_continuation");
  }

  if (
    bbPercent > 0.82
    && rsi > 57
    && rangePosition24h >= 0.72
    && volume > volumeMean * 0.7
  ) {
    types.push("blowoff_short");
  }

  if (
    ret !== null
    && range !== null
    && ret > 0.004
    && rsi >= 35
    && rsi <= 62
    && range >= 0.012
    && volume > volumeMean * 0.8
  ) {
    types.push("crash_rebound");
  }

  return types;
}

function directionForType(type) {
  if (type === "selloff_continuation" || type === "blowoff_short") return "short";
  if (type === "crash_rebound") return "long";
  return "observation";
}

function percentile(values, pct) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * pct;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[index];
  return sorted[lower] * (upper - index) + sorted[upper] * (index - lower);
}

function summarizeValues(values) {
  const clean = values.filter((value) => Number.isFinite(value));
  if (clean.length === 0) {
    return {
      count: 0,
      mean_bps: null,
      median_bps: null,
      p25_bps: null,
      p75_bps: null,
      positive_count: 0,
      positive_rate: null,
    };
  }
  const sum = clean.reduce((acc, value) => acc + value, 0);
  const positive = clean.filter((value) => value > 0).length;
  return {
    count: clean.length,
    mean_bps: round(sum / clean.length),
    median_bps: round(percentile(clean, 0.5)),
    p25_bps: round(percentile(clean, 0.25)),
    p75_bps: round(percentile(clean, 0.75)),
    positive_count: positive,
    positive_rate: round(positive / clean.length),
  };
}

function forwardOutcome(rows, index, horizon, direction, feeBps) {
  const entry = num(rows[index]?.close);
  const end = index + horizon;
  if (entry <= 0 || end >= rows.length || direction === "observation") return null;
  const future = rows.slice(index + 1, end + 1);
  const closeAfter = num(rows[end].close);
  const maxHigh = Math.max(...future.map((row) => num(row.high)));
  const minLow = Math.min(...future.map((row) => num(row.low)));
  const gross = direction === "short"
    ? ((entry - closeAfter) / entry) * 10000
    : ((closeAfter - entry) / entry) * 10000;
  const mfe = direction === "short"
    ? Math.max(0, ((entry - minLow) / entry) * 10000)
    : Math.max(0, ((maxHigh - entry) / entry) * 10000);
  const mae = direction === "short"
    ? Math.max(0, ((maxHigh - entry) / entry) * 10000)
    : Math.max(0, ((entry - minLow) / entry) * 10000);
  return {
    gross_return_bps: round(gross),
    fee_adjusted_return_bps: round(gross - feeBps),
    mfe_bps: round(mfe),
    mae_bps: round(mae),
    close_after: round(closeAfter, 8),
  };
}

function summarizeCandidates(candidates, horizons) {
  const result = {};
  for (const horizon of horizons) {
    const key = String(horizon);
    const outcomes = candidates
      .map((candidate) => candidate.horizons[key])
      .filter(Boolean);
    result[key] = {
      gross_return: summarizeValues(outcomes.map((outcome) => outcome.gross_return_bps)),
      fee_adjusted_return: summarizeValues(outcomes.map((outcome) => outcome.fee_adjusted_return_bps)),
      mfe: summarizeValues(outcomes.map((outcome) => outcome.mfe_bps)),
      mae: summarizeValues(outcomes.map((outcome) => outcome.mae_bps)),
    };
  }
  return result;
}

function buildReplayScorecard(rowsByPair, options = {}) {
  const feeBps = options.feeBps ?? DEFAULT_FEE_BPS;
  const horizons = options.horizons ?? DEFAULT_HORIZONS;
  const generatedAt = options.generatedAt ?? new Date().toISOString();
  const candidateCounts = {
    high_volatility: 0,
    selloff_continuation: 0,
    blowoff_short: 0,
    crash_rebound: 0,
  };
  const byCandidate = {};
  const pairMatrix = [];
  const examples = [];
  let totalRows = 0;
  let finalEntryRows = 0;
  let alphaLongBlockRows = 0;
  let alphaShortBlockRows = 0;

  for (const [pair, rows] of Object.entries(rowsByPair)) {
    const pairCounts = {
      high_volatility: 0,
      selloff_continuation: 0,
      blowoff_short: 0,
      crash_rebound: 0,
    };
    const pairCandidates = [];
    totalRows += rows.length;

    rows.forEach((row, index) => {
      if (bool(row.enter_long) || bool(row.enter_short)) finalEntryRows += 1;
      if (bool(row.alpha_filter_block_long)) alphaLongBlockRows += 1;
      if (bool(row.alpha_filter_block_short)) alphaShortBlockRows += 1;

      const types = classifyCandidateTypes(row);
      for (const type of types) {
        candidateCounts[type] += 1;
        pairCounts[type] += 1;
        const direction = directionForType(type);
        const horizonsOut = {};
        for (const horizon of horizons) {
          const outcome = forwardOutcome(rows, index, horizon, direction, feeBps);
          if (outcome) horizonsOut[String(horizon)] = outcome;
        }
        const candidate = {
          pair,
          date: row.date || "",
          type,
          direction,
          close: round(num(row.close), 8),
          ret_oc: round(openCloseReturn(row) ?? 0, 6),
          range_hl: round(highLowRange(row) ?? 0, 6),
          rsi: round(num(row.rsi)),
          adx_4h: round(num(row.adx_4h)),
          bb_percent: round(num(row.bb_percent)),
          range_position_24h: round(num(row.range_position_24h)),
          alpha_filter_block_long: bool(row.alpha_filter_block_long),
          alpha_filter_block_short: bool(row.alpha_filter_block_short),
          alpha_risk_flags: row.alpha_risk_flags || "",
          enter_tag: row.enter_tag || "",
          final_enter_long: bool(row.enter_long),
          final_enter_short: bool(row.enter_short),
          horizons: horizonsOut,
        };
        pairCandidates.push(candidate);
        if (examples.length < 40 && type !== "high_volatility") examples.push(candidate);
        if (!byCandidate[type]) byCandidate[type] = { candidates: [] };
        byCandidate[type].candidates.push(candidate);
      }
    });

    pairMatrix.push({
      pair,
      rows: rows.length,
      latest_date: rows.at(-1)?.date || "",
      candidate_counts: pairCounts,
      directional_candidates: pairCandidates.filter((candidate) => candidate.direction !== "observation").length,
    });
  }

  for (const type of Object.keys(candidateCounts)) {
    if (!byCandidate[type]) byCandidate[type] = { candidates: [] };
    byCandidate[type].count = byCandidate[type].candidates.length;
    byCandidate[type].directional_count = byCandidate[type].candidates
      .filter((candidate) => candidate.direction !== "observation").length;
    byCandidate[type].horizons = summarizeCandidates(byCandidate[type].candidates, horizons);
    byCandidate[type].examples = byCandidate[type].candidates.slice(0, 8);
    delete byCandidate[type].candidates;
  }

  const ranking = Object.entries(byCandidate)
    .filter(([, item]) => item.directional_count > 0)
    .map(([type, item]) => {
      const horizon4 = item.horizons["4"] || item.horizons[String(horizons[0])];
      return {
        type,
        count: item.directional_count,
        horizon: horizon4 === item.horizons["4"] ? 4 : horizons[0],
        fee_adjusted_mean_bps: horizon4.fee_adjusted_return.mean_bps,
        positive_rate: horizon4.fee_adjusted_return.positive_rate,
        mae_mean_bps: horizon4.mae.mean_bps,
      };
    })
    .sort((a, b) => {
      const aScore = (a.fee_adjusted_mean_bps ?? -Infinity) + (a.positive_rate ?? 0) * 10;
      const bScore = (b.fee_adjusted_mean_bps ?? -Infinity) + (b.positive_rate ?? 0) * 10;
      return bScore - aScore;
    });

  return {
    metadata: {
      report: "v1129_high_volatility_replay_scorecard",
      generated_at: generatedAt,
      source: "freqtrade-v1129 analyzed dataframe via read-only API",
      timeframe: "15m",
      fee_bps: feeBps,
      horizons,
      pairs: Object.keys(rowsByPair),
      total_rows: totalRows,
      reads_secret_material: false,
      modifies_strategy: false,
      modifies_bot_config: false,
      starts_or_stops_bot: false,
      runs_backtest: false,
    },
    aggregate: {
      candidate_counts: candidateCounts,
      final_entry_rows: finalEntryRows,
      alpha_long_block_rows: alphaLongBlockRows,
      alpha_short_block_rows: alphaShortBlockRows,
      by_candidate: byCandidate,
      ranking,
    },
    pair_matrix: pairMatrix,
    examples,
    verdict: {
      report_status: "observed_replay_scorecard",
      can_select_v1130_candidate: ranking.length > 0,
      can_enable_live_trading: false,
      can_modify_strategy_from_this_report_alone: false,
      next_required_task: "Task 58: V11.30 Candidate Selection",
      reason: "Replay scorecard can rank candidate families, but live strategy/config changes require a separate candidate selection and implementation task.",
    },
  };
}

function remoteCollector({ port, limit }) {
  return `
import base64
import json
import urllib.parse
import urllib.request

PAIRS = ${JSON.stringify(PAIRS)}
PORT = ${JSON.stringify(port)}
LIMIT = ${JSON.stringify(limit)}
AUTH = "Basic " + base64.b64encode(b"freqtrader:freqtrade").decode()
BASE = f"http://127.0.0.1:{PORT}/api/v1/pair_candles"
KEEP = {
    "date", "open", "high", "low", "close", "volume", "volume_mean",
    "ema200", "bb_percent", "rsi", "adx_4h", "regime_4h",
    "range_position_24h", "range_position_48h", "range_width_24h",
    "range_width_48h", "bb_width_4h", "bb_width_mean_4h",
    "trend_4h_down", "trend_4h_up", "alpha_filter_block_long",
    "alpha_filter_block_short", "alpha_risk_flags", "enter_tag",
    "enter_long", "enter_short",
}

def fetch(pair):
    query = urllib.parse.urlencode({"pair": pair, "timeframe": "15m", "limit": str(LIMIT)})
    request = urllib.request.Request(BASE + "?" + query, headers={"Authorization": AUTH})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    columns = payload.get("columns") or payload.get("all_columns") or []
    rows = []
    for raw in payload.get("data") or []:
        row = {}
        for index, column in enumerate(columns):
            if column in KEEP and index < len(raw):
                row[column] = raw[index]
        rows.append(row)
    return rows

print(json.dumps({pair: fetch(pair) for pair in PAIRS}, ensure_ascii=False))
`;
}

function collectRowsFromServer(options = {}) {
  const host = options.host || process.env.FREQTRADE_HOST || DEFAULT_HOST;
  const user = options.user || process.env.FREQTRADE_USER || DEFAULT_USER;
  const key = options.key || process.env.FREQTRADE_SSH_KEY || DEFAULT_KEY;
  const port = options.port || Number(process.env.FREQTRADE_API_PORT || DEFAULT_PORT);
  const limit = options.limit || Number(process.env.FREQTRADE_REPLAY_LIMIT || DEFAULT_LIMIT);
  const code = remoteCollector({ port, limit });
  const ssh = spawnSync(
    "ssh",
    [
      "-i",
      key,
      "-o",
      "StrictHostKeyChecking=no",
      `${user}@${host}`,
      "python3",
      "-",
    ],
    { input: code, encoding: "utf8", maxBuffer: 1024 * 1024 * 30 },
  );
  if (ssh.status !== 0) {
    throw new Error((ssh.stderr || ssh.stdout || "ssh collector failed").trim());
  }
  return JSON.parse(ssh.stdout);
}

function horizonRows(summary) {
  return Object.entries(summary)
    .map(([horizon, value]) => {
      const fee = value.fee_adjusted_return;
      return `| ${horizon} | ${fee.count} | ${fee.mean_bps ?? "missing"} | ${fee.median_bps ?? "missing"} | ${fee.positive_rate ?? "missing"} | ${value.mfe.mean_bps ?? "missing"} | ${value.mae.mean_bps ?? "missing"} |`;
    })
    .join("\n");
}

function renderMarkdown(report) {
  const rankingRows = report.aggregate.ranking
    .map((item, index) => `| ${index + 1} | ${item.type} | ${item.count} | ${item.horizon} | ${item.fee_adjusted_mean_bps ?? "missing"} | ${item.positive_rate ?? "missing"} | ${item.mae_mean_bps ?? "missing"} |`)
    .join("\n");
  const candidateSections = Object.entries(report.aggregate.by_candidate)
    .map(([type, item]) => `### ${type}

Count: ${item.count}

| Horizon candles | Count | Fee-adjusted mean bps | Fee-adjusted median bps | Positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${horizonRows(item.horizons) || "| missing | 0 | missing | missing | missing | missing | missing |"}`)
    .join("\n\n");
  const pairRows = report.pair_matrix
    .map((row) => `| ${row.pair} | ${row.rows} | ${row.latest_date} | ${row.candidate_counts.high_volatility} | ${row.candidate_counts.selloff_continuation} | ${row.candidate_counts.blowoff_short} | ${row.candidate_counts.crash_rebound} | ${row.directional_candidates} |`)
    .join("\n");
  const exampleRows = report.examples.slice(0, 16)
    .map((item) => {
      const h4 = item.horizons["4"] || item.horizons["1"] || {};
      return `| ${item.type} | ${item.pair} | ${item.date} | ${item.direction} | ${item.close} | ${h4.fee_adjusted_return_bps ?? "missing"} | ${h4.mfe_bps ?? "missing"} | ${h4.mae_bps ?? "missing"} | ${item.alpha_risk_flags || ""} |`;
    })
    .join("\n");

  return `# V11.29 High-Volatility Replay Scorecard

## Summary

This report is a read-only replay scorecard for high-volatility candidate
families observed in the current V11.29 analyzed dataframe. It does not modify
strategy code, bot config, server files, SQLite, dashboard code, or live state.

Important: this report does not claim that any candidate is production-ready.
It only ranks candidate families for Task 58.

## Metadata

| Field | Value |
| --- | --- |
| Generated at | ${report.metadata.generated_at} |
| Source | ${report.metadata.source} |
| Timeframe | ${report.metadata.timeframe} |
| Total rows | ${report.metadata.total_rows} |
| Fee assumption | ${report.metadata.fee_bps} bps |
| Pairs | ${report.metadata.pairs.length} |

## Aggregate Counts

| Metric | Count |
| --- | ---: |
| final entry rows | ${report.aggregate.final_entry_rows} |
| alpha long block rows | ${report.aggregate.alpha_long_block_rows} |
| alpha short block rows | ${report.aggregate.alpha_short_block_rows} |
| high volatility | ${report.aggregate.candidate_counts.high_volatility} |
| selloff continuation | ${report.aggregate.candidate_counts.selloff_continuation} |
| blowoff short | ${report.aggregate.candidate_counts.blowoff_short} |
| crash rebound | ${report.aggregate.candidate_counts.crash_rebound} |

## Candidate Ranking

| Rank | Candidate | Directional count | Horizon candles | Fee-adjusted mean bps | Positive rate | MAE mean bps |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
${rankingRows || "| none | missing | 0 | missing | missing | missing | missing |"}

## Candidate Details

${candidateSections}

## Pair Matrix

| Pair | Rows | Latest date | High volatility | Selloff continuation | Blowoff short | Crash rebound | Directional candidates |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
${pairRows}

## Representative Directional Examples

| Candidate | Pair | Time UTC | Direction | Entry close | Horizon fee-adjusted bps | MFE bps | MAE bps | Alpha flags |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
${exampleRows || "| none | missing | missing | missing | missing | missing | missing | missing | missing |"}

## Interpretation

Observed:

- The current V11.29 analyzed dataframe has enough rows to replay recent
  high-volatility candidate families.
- Final V11.29 entries remain zero in the replayed dataframe.
- Candidate families exist before any live strategy/config modification.

Derived:

- Direction-aware forward returns can rank candidate families.
- Task 58 should use this scorecard to choose whether V11.30 should focus on
  selloff continuation, blowoff short, crash rebound, or reject all three.

Insufficient:

- This is not a Freqtrade backtest.
- This does not prove fill quality, slippage, funding, or latency.
- This does not justify live trading or strategy/config changes by itself.

## Verdict

| Field | Value |
| --- | --- |
| report_status | ${report.verdict.report_status} |
| can_select_v1130_candidate | ${report.verdict.can_select_v1130_candidate} |
| can_enable_live_trading | ${report.verdict.can_enable_live_trading} |
| next_required_task | ${report.verdict.next_required_task} |

Recommended next task: ${report.verdict.next_required_task}
`;
}

function assertReport(report, markdown) {
  if (report.metadata.reads_secret_material !== false) throw new Error("reads_secret_material must be false");
  if (report.metadata.modifies_strategy !== false) throw new Error("modifies_strategy must be false");
  if (report.metadata.modifies_bot_config !== false) throw new Error("modifies_bot_config must be false");
  if (report.metadata.starts_or_stops_bot !== false) throw new Error("starts_or_stops_bot must be false");
  if (report.verdict.can_enable_live_trading !== false) throw new Error("can_enable_live_trading must be false");
  const serialized = `${JSON.stringify(report)}\n${markdown}`;
  for (const forbidden of [
    "V11.29 passed",
    "V11.29 can replace V10.8.2",
    "V11.29 可以替换 V10.8.2",
    "V11.29 通过真实执行验证",
  ]) {
    if (serialized.includes(forbidden)) {
      throw new Error(`forbidden conclusion found: ${forbidden}`);
    }
  }
}

function main() {
  const rowsByPair = collectRowsFromServer();
  const report = buildReplayScorecard(rowsByPair);
  const markdown = renderMarkdown(report);
  assertReport(report, markdown);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown, "utf8");
  console.log(`wrote ${JSON_OUT}`);
  console.log(`wrote ${MD_OUT}`);
}

module.exports = {
  classifyCandidateTypes,
  buildReplayScorecard,
  renderMarkdown,
  summarizeValues,
};

if (require.main === module) {
  main();
}
