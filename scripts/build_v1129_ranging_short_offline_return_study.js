#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join("reports", "v1129_execution_validation");
const JSON_OUT = path.join(OUT_DIR, "v1129_ranging_short_offline_return_study.json");
const MD_OUT = path.join(OUT_DIR, "v1129_ranging_short_offline_return_study.md");

const DEFAULT_HOST = "43.134.72.69";
const DEFAULT_USER = "ubuntu";
const DEFAULT_KEY = "D:\\key\\openclaw\\clf.pem";
const DEFAULT_PORT = 8122;
const DEFAULT_LIMIT = 3000;
const FEE_BPS = 10;

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

const REMOTE_COLLECTOR = String.raw`
import base64
import collections
import datetime
import json
import math
import statistics
import urllib.parse
import urllib.request

PAIRS = __PAIRS__
PORT = __PORT__
LIMIT = __LIMIT__
FEE_BPS = __FEE_BPS__
AUTH = "Basic " + base64.b64encode(b"freqtrader:freqtrade").decode()
BASE = f"http://localhost:{PORT}/api/v1/pair_candles"
HORIZONS = [1, 2, 4, 8]

def as_bool(value):
    return value in (True, 1, "1", "true", "True")

def num(row, key, default=0.0):
    try:
        value = row.get(key, default)
        if value is None or value == "":
            return float(default)
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return float(default)
        return parsed
    except Exception:
        return float(default)

def text(row, key):
    value = row.get(key)
    return "" if value is None else str(value)

def parse_dt(value):
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(raw)
    except Exception:
        pass
    try:
        return datetime.datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None

def fetch_pair(pair):
    query = urllib.parse.urlencode({"pair": pair, "timeframe": "15m", "limit": str(LIMIT)})
    req = urllib.request.Request(BASE + "?" + query, headers={"Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    columns = data.get("columns") or []
    rows = [dict(zip(columns, raw)) for raw in data.get("data", [])]
    return data, rows

def is_ranging_short(row):
    regime = text(row, "regime_4h").lower()
    volume = num(row, "volume")
    close = num(row, "close")
    ema200 = num(row, "ema200")
    enough_range = num(row, "range_width_24h") >= 0.018 and num(row, "range_width_48h") >= 0.025
    range_not_expanding = (
        num(row, "adx_4h", 100) < 42
        and num(row, "bb_width_4h", 1.0) < num(row, "bb_width_mean_4h", 0.0) * 1.15
    )
    volume_ok = volume > num(row, "volume_mean") * 0.7
    near_upper = num(row, "range_position_24h", 0.5) >= 0.72 and num(row, "range_position_48h", 0.5) >= 0.65
    return (
        regime == "ranging"
        and near_upper
        and enough_range
        and range_not_expanding
        and num(row, "bb_percent", 0.5) > 0.82
        and num(row, "rsi", 50) > 57
        and volume_ok
        and close < ema200 * 1.10
        and volume > 0
    )

def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)

def summarize_values(values):
    if not values:
        return {
            "count": 0,
            "mean_bps": None,
            "median_bps": None,
            "p25_bps": None,
            "p75_bps": None,
            "positive_count": 0,
            "positive_rate": None,
        }
    return {
        "count": len(values),
        "mean_bps": round(statistics.fmean(values), 4),
        "median_bps": round(statistics.median(values), 4),
        "p25_bps": round(percentile(values, 0.25), 4),
        "p75_bps": round(percentile(values, 0.75), 4),
        "positive_count": sum(1 for value in values if value > 0),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }

def summarize_candidates(candidates):
    result = {}
    for horizon in HORIZONS:
        returns = [c["horizons"][str(horizon)]["return_bps"] for c in candidates if str(horizon) in c["horizons"]]
        fee_returns = [
            c["horizons"][str(horizon)]["fee_adjusted_return_bps"]
            for c in candidates
            if str(horizon) in c["horizons"]
        ]
        mfe = [c["horizons"][str(horizon)]["mfe_bps"] for c in candidates if str(horizon) in c["horizons"]]
        mae = [c["horizons"][str(horizon)]["mae_bps"] for c in candidates if str(horizon) in c["horizons"]]
        result[str(horizon)] = {
            "gross_return": summarize_values(returns),
            "fee_adjusted_return": summarize_values(fee_returns),
            "mfe": summarize_values(mfe),
            "mae": summarize_values(mae),
        }
    return result

def candidate_for(pair, rows, index):
    row = rows[index]
    entry = num(row, "close")
    horizons = {}
    for horizon in HORIZONS:
        end = index + horizon
        if end >= len(rows) or entry <= 0:
            continue
        future = rows[index + 1 : end + 1]
        close_after = num(rows[end], "close")
        max_high = max(num(item, "high") for item in future)
        min_low = min(num(item, "low") for item in future)
        return_bps = ((entry - close_after) / entry) * 10000
        mfe_bps = max(0.0, ((entry - min_low) / entry) * 10000)
        mae_bps = max(0.0, ((max_high - entry) / entry) * 10000)
        horizons[str(horizon)] = {
            "return_bps": round(return_bps, 4),
            "fee_adjusted_return_bps": round(return_bps - FEE_BPS, 4),
            "mfe_bps": round(mfe_bps, 4),
            "mae_bps": round(mae_bps, 4),
        }
    alpha_short = as_bool(row.get("alpha_filter_block_short"))
    return {
        "pair": pair,
        "date": text(row, "date"),
        "regime_4h": text(row, "regime_4h"),
        "date_4h": text(row, "date_4h"),
        "enter_tag": text(row, "enter_tag"),
        "alpha_filter_block_short": alpha_short,
        "blocked_reason": "alpha_filter_block_short" if alpha_short else "v102_short_core_prunes_ranging_non_core_short",
        "entry_close": round(entry, 8),
        "rsi": round(num(row, "rsi"), 4),
        "bb_percent": round(num(row, "bb_percent"), 4),
        "range_position_24h": round(num(row, "range_position_24h"), 4),
        "range_position_48h": round(num(row, "range_position_48h"), 4),
        "adx_4h": round(num(row, "adx_4h"), 4),
        "enter_short": row.get("enter_short"),
        "horizons": horizons,
    }

def bucket_counts(candidates, stop_dt):
    result = {"1d": 0, "7d": 0, "14d": 0, "30d": 0}
    if stop_dt is None:
        return result
    for candidate in candidates:
        date = parse_dt(candidate.get("date"))
        if date is None:
            continue
        delta = stop_dt - date
        seconds = delta.total_seconds()
        if seconds <= 86400:
            result["1d"] += 1
        if seconds <= 86400 * 7:
            result["7d"] += 1
        if seconds <= 86400 * 14:
            result["14d"] += 1
        if seconds <= 86400 * 30:
            result["30d"] += 1
    return result

def inspect_pair(pair):
    data, rows = fetch_pair(pair)
    candidates = []
    for index, row in enumerate(rows):
        if is_ranging_short(row):
            candidates.append(candidate_for(pair, rows, index))
    stop_dt = parse_dt(data.get("data_stop"))
    start_dt = parse_dt(data.get("data_start"))
    available_days = None
    if start_dt is not None and stop_dt is not None:
        available_days = round((stop_dt - start_dt).total_seconds() / 86400, 4)
    return {
        "pair": pair,
        "rows": len(rows),
        "data_start": data.get("data_start"),
        "data_stop": data.get("data_stop"),
        "available_days": available_days,
        "last_analyzed": data.get("last_analyzed"),
        "candidate_count": len(candidates),
        "window_counts": bucket_counts(candidates, stop_dt),
        "blocked_reasons": dict(collections.Counter(c["blocked_reason"] for c in candidates)),
        "alpha_split": {
            "alpha_allowed": sum(1 for c in candidates if not c["alpha_filter_block_short"]),
            "alpha_blocked": sum(1 for c in candidates if c["alpha_filter_block_short"]),
        },
        "summaries": summarize_candidates(candidates),
        "examples": candidates[:5],
    }, candidates

pairs = []
all_candidates = []
errors = []
for pair in PAIRS:
    try:
        pair_report, candidates = inspect_pair(pair)
        pairs.append(pair_report)
        all_candidates.extend(candidates)
    except Exception as error:
        errors.append({"pair": pair, "error_type": type(error).__name__, "error": str(error)[:240]})

alpha_allowed = [candidate for candidate in all_candidates if not candidate["alpha_filter_block_short"]]
alpha_blocked = [candidate for candidate in all_candidates if candidate["alpha_filter_block_short"]]
available_days = [pair["available_days"] for pair in pairs if pair.get("available_days") is not None]
max_available_days = max(available_days) if available_days else None

classification = "insufficient"
classification_reasons = []
if max_available_days is None or max_available_days < 30:
    classification_reasons.append("available runtime candle window is shorter than the 30d minimum gate")
if len(all_candidates) < 100:
    classification_reasons.append("candidate sample is below the 100 candidate minimum gate")
if not classification_reasons:
    h4 = summarize_candidates(alpha_allowed).get("4", {}).get("fee_adjusted_return", {})
    if h4.get("mean_bps") is not None and h4["mean_bps"] > 0:
        classification = "research_candidate"
        classification_reasons.append("alpha-allowed candidate sample passes the initial fee-adjusted 4-candle mean gate")
    else:
        classification = "reject"
        classification_reasons.append("alpha-allowed candidate sample does not pass the fee-adjusted 4-candle mean gate")

print(json.dumps({
    "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "port": PORT,
    "limit": LIMIT,
    "fee_bps": FEE_BPS,
    "horizons_15m_candles": HORIZONS,
    "pairs": pairs,
    "aggregate": {
        "candidate_count": len(all_candidates),
        "max_available_days": max_available_days,
        "window_counts": bucket_counts(all_candidates, max((parse_dt(p.get("data_stop")) for p in pairs if parse_dt(p.get("data_stop"))), default=None)),
        "blocked_reasons": dict(collections.Counter(c["blocked_reason"] for c in all_candidates)),
        "alpha_split": {
            "alpha_allowed": len(alpha_allowed),
            "alpha_blocked": len(alpha_blocked),
        },
        "summaries": summarize_candidates(all_candidates),
        "alpha_allowed_summaries": summarize_candidates(alpha_allowed),
        "alpha_blocked_summaries": summarize_candidates(alpha_blocked),
        "sample_candidates": all_candidates[:20],
    },
    "classification": {
        "status": classification,
        "reasons": classification_reasons,
    },
    "errors": errors,
}, ensure_ascii=False))
`;

function nowShanghaiIso() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day}T${byType.hour}:${byType.minute}:${byType.second}+08:00`;
}

function runCollector() {
  const host = process.env.V1129_SSH_HOST || DEFAULT_HOST;
  const user = process.env.V1129_SSH_USER || DEFAULT_USER;
  const key = process.env.V1129_SSH_KEY || DEFAULT_KEY;
  const port = Number(process.env.V1129_API_PORT || DEFAULT_PORT);
  const limit = Number(process.env.V1129_RETURN_STUDY_LIMIT || DEFAULT_LIMIT);
  const script = REMOTE_COLLECTOR
    .replace("__PAIRS__", JSON.stringify(PAIRS))
    .replace("__PORT__", String(port))
    .replace("__LIMIT__", String(limit))
    .replace("__FEE_BPS__", String(FEE_BPS));
  const args = [
    "-i",
    key,
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "StrictHostKeyChecking=no",
    `${user}@${host}`,
    "python3 -",
  ];
  const result = spawnSync("ssh", args, {
    input: script,
    encoding: "utf8",
    maxBuffer: 40 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(`collector failed: ${result.stderr || result.stdout || "unknown ssh error"}`);
  }
  return JSON.parse(result.stdout.trim());
}

function round(value) {
  return typeof value === "number" ? Number(value.toFixed(4)) : value;
}

function buildReport(raw) {
  return {
    metadata: {
      strategy: "RegimeAwareV1129ResidualDragMicroSizer",
      generated_at: nowShanghaiIso(),
      observed_at_utc: raw.observed_at_utc,
      mode: "read_only_ranging_short_offline_return_study",
      source: "runtime_pair_candles_api",
      can_place_orders: false,
      reads_secret_material: false,
      reads_env_files: false,
      modifies_server_state: false,
      runs_backtest: false,
      modifies_strategy_or_config: false,
      fee_bps: raw.fee_bps,
      horizons_15m_candles: raw.horizons_15m_candles,
      api_port: raw.port,
      candle_limit: raw.limit,
    },
    data_sources: [
      {
        id: "v1129_pair_candles_api",
        kind: "freqtrade_api",
        endpoint: "http://localhost:8122/api/v1/pair_candles",
        read_status: raw.errors.length === 0 ? "read" : "partial",
        contains_secret_material: false,
      },
    ],
    aggregate: raw.aggregate,
    pairs: raw.pairs,
    classification: raw.classification,
    errors: raw.errors,
    verdict: {
      can_enable_live_ranging_short: false,
      can_claim_replacement: false,
      can_claim_execution_quality: false,
      reason: "This is a candidate-only offline return study from runtime candles, not a live execution or replacement validation.",
      next_required_task: "Task 40: V11.29 Ranging-Short Historical Data Coverage Extension",
    },
  };
}

function fmt(value) {
  if (value === null || value === undefined) return "missing";
  if (typeof value === "number") return String(round(value));
  return String(value);
}

function horizonSummaryRows(summary) {
  return ["1", "2", "4", "8"]
    .map((horizon) => {
      const item = summary[horizon] || {};
      const gross = item.gross_return || {};
      const fee = item.fee_adjusted_return || {};
      const mfe = item.mfe || {};
      const mae = item.mae || {};
      return `| ${horizon} | ${fmt(gross.count)} | ${fmt(gross.mean_bps)} | ${fmt(fee.mean_bps)} | ${fmt(fee.positive_rate)} | ${fmt(mfe.mean_bps)} | ${fmt(mae.mean_bps)} |`;
    })
    .join("\n");
}

function renderMarkdown(report) {
  const pairRows = report.pairs
    .map((pair) => {
      const h4 = pair.summaries["4"]?.fee_adjusted_return || {};
      return `| ${pair.pair} | ${pair.rows} | ${fmt(pair.available_days)} | ${pair.candidate_count} | ${pair.window_counts["1d"]} | ${pair.window_counts["7d"]} | ${pair.window_counts["30d"]} | ${pair.alpha_split.alpha_allowed} | ${pair.alpha_split.alpha_blocked} | ${fmt(h4.mean_bps)} |`;
    })
    .join("\n");
  const reasons = report.classification.reasons.map((reason) => `- ${reason}`).join("\n") || "- none";
  const examples = (report.aggregate.sample_candidates || [])
    .slice(0, 8)
    .map((candidate) => {
      const h4 = candidate.horizons["4"] || {};
      return `| ${candidate.pair} | ${candidate.date} | ${candidate.blocked_reason} | ${candidate.alpha_filter_block_short} | ${fmt(h4.fee_adjusted_return_bps)} | ${fmt(h4.mfe_bps)} | ${fmt(h4.mae_bps)} |`;
    })
    .join("\n");

  return `# V11.29 Ranging-Short Offline Candidate Return Study

## Summary

This report studies the \`v66_ranging_short_edge\` candidate family using the
read-only V11.29 runtime \`pair_candles\` API. It does not run a Freqtrade
backtest, read secrets, modify strategy code, modify bot configuration, write
SQLite, or start/stop/restart any bot.

- Candidate count: ${report.aggregate.candidate_count}
- Max available runtime candle window: ${fmt(report.aggregate.max_available_days)} days
- Fee assumption: ${report.metadata.fee_bps} bps round trip
- Classification: \`${report.classification.status}\`
- Can enable live ranging-short: \`${report.verdict.can_enable_live_ranging_short}\`
- Can claim V11.29 replacement: \`${report.verdict.can_claim_replacement}\`

## Classification Reasons

${reasons}

## Aggregate Forward Return Summary

For a short candidate, positive return means the future close is lower than the
candidate close. Fee-adjusted return subtracts the conservative round-trip fee
assumption.

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${horizonSummaryRows(report.aggregate.summaries)}

## Alpha-Allowed Candidate Summary

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${horizonSummaryRows(report.aggregate.alpha_allowed_summaries)}

## Alpha-Blocked Candidate Summary

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${horizonSummaryRows(report.aggregate.alpha_blocked_summaries)}

## Pair Matrix

| Pair | Rows | Available days | Candidates | 1d | 7d | 30d | Alpha allowed | Alpha blocked | 4-candle fee-adjusted mean bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${pairRows}

## Representative Candidate Outcomes

| Pair | Time UTC | Blocked reason | Alpha short block | 4-candle fee-adjusted bps | 4-candle MFE bps | 4-candle MAE bps |
| --- | --- | --- | --- | ---: | ---: | ---: |
${examples || "| none | missing | missing | missing | missing | missing | missing |"}

## What This Can Conclude

Observed:

- Runtime candle data was readable through the V11.29 API.
- The candidate family exists in the current runtime dataframe.
- Forward return, MFE, and MAE can be derived from candles for available rows.

Derived:

- The current sample can rank candidate behavior by pair and alpha state.
- The current sample can inform a later historical data extension task.

Insufficient:

- The available runtime window is shorter than the 30d calibration gate.
- This report is not a live execution-quality report.
- This report does not verify fees, fills, funding, slippage, or latency from
  real orders.
- This report cannot justify live strategy/config changes.

## Recommended Next Task

Task 40: V11.29 Ranging-Short Historical Data Coverage Extension

Scope:

- Acquire or locate at least 30d of clean 15m/4h candle context for the
  candidate family.
- Re-run the same candidate-only return study on the longer window.
- Keep the work offline until sample sufficiency and fee-adjusted gates are
  satisfied.

## Boundary Confirmation

This task did not:

- modify \`strategies/**\`;
- modify \`user_data/**\`;
- modify \`configs/**\`;
- modify \`dashboard/**\`;
- modify \`deploy/**\`;
- read \`.env\`;
- read \`user_data/monitor.env\`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run \`docker inspect\`;
- start, stop, or restart bots;
- run \`freqtrade trade\`;
- run a Freqtrade backtest;
- write SQLite;
- modify server files;
- modify the original dirty workspace.
`;
}

function assertReport(report, markdown) {
  if (report.metadata.can_place_orders !== false) throw new Error("can_place_orders must be false");
  if (report.metadata.reads_secret_material !== false) throw new Error("reads_secret_material must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.verdict.can_enable_live_ranging_short !== false) {
    throw new Error("can_enable_live_ranging_short must remain false");
  }
  const serialized = `${JSON.stringify(report)}\n${markdown}`;
  for (const forbidden of [
    "V11.29 passed",
    "V11.29 failed",
    "V11.29 can replace V10.8.2",
    "V11.29 cannot replace V10.8.2",
    "V11.29 通过真实执行验证",
    "V11.29 可以替换 V10.8.2",
  ]) {
    if (serialized.includes(forbidden)) {
      throw new Error(`forbidden conclusion found: ${forbidden}`);
    }
  }
}

function main() {
  const raw = runCollector();
  const report = buildReport(raw);
  const markdown = renderMarkdown(report);
  assertReport(report, markdown);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(MD_OUT, markdown, "utf8");
  console.log(`wrote ${JSON_OUT}`);
  console.log(`wrote ${MD_OUT}`);
}

main();
