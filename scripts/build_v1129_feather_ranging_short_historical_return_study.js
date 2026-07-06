#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join("reports", "v1129_execution_validation");
const JSON_OUT = path.join(OUT_DIR, "v1129_feather_ranging_short_historical_return_study.json");
const MD_OUT = path.join(OUT_DIR, "v1129_feather_ranging_short_historical_return_study.md");

const DEFAULT_HOST = "43.134.72.69";
const DEFAULT_USER = "ubuntu";
const DEFAULT_KEY = "D:\\key\\openclaw\\clf.pem";
const DEFAULT_CONTAINER = "freqtrade-v1129";
const FEE_BPS = 10;
const STUDY_DAYS = 30;

const PAIRS = [
  "BTC",
  "ETH",
  "SOL",
  "BNB",
  "XRP",
  "DOGE",
  "ADA",
  "LINK",
  "AVAX",
  "LTC",
  "TRX",
  "BCH",
];

const REMOTE_COLLECTOR = String.raw`
import datetime
import json
import math
import os
import statistics

import pandas as pd

PAIRS = __PAIRS__
ROOT = "/freqtrade/project/user_data/data/futures"
FEE_BPS = __FEE_BPS__
STUDY_DAYS = __STUDY_DAYS__
HORIZONS = [1, 2, 4, 8]

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
    values = [float(v) for v in values if v is not None and not math.isnan(float(v))]
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
    positive = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "mean_bps": round(statistics.fmean(values), 4),
        "median_bps": round(statistics.median(values), 4),
        "p25_bps": round(percentile(values, 0.25), 4),
        "p75_bps": round(percentile(values, 0.75), 4),
        "positive_count": positive,
        "positive_rate": round(positive / len(values), 4),
    }

def summarize_candidates(candidates):
    result = {}
    for horizon in HORIZONS:
        key = str(horizon)
        returns = [c["horizons"][key]["return_bps"] for c in candidates if key in c["horizons"]]
        fee_returns = [c["horizons"][key]["fee_adjusted_return_bps"] for c in candidates if key in c["horizons"]]
        mfe = [c["horizons"][key]["mfe_bps"] for c in candidates if key in c["horizons"]]
        mae = [c["horizons"][key]["mae_bps"] for c in candidates if key in c["horizons"]]
        result[key] = {
            "gross_return": summarize_values(returns),
            "fee_adjusted_return": summarize_values(fee_returns),
            "mfe": summarize_values(mfe),
            "mae": summarize_values(mae),
        }
    return result

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, math.nan)
    return 100 - (100 / (1 + rs))

def adx(df, period=14):
    high = df["high"]
    low = df["low"]
    close = df["close"]
    plus_dm = (high.diff()).where((high.diff() > -low.diff()) & (high.diff() > 0), 0.0)
    minus_dm = (-low.diff()).where((-low.diff() > high.diff()) & (-low.diff() > 0), 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, math.nan)) * 100
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

def prepare_15m(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").reset_index(drop=True)
    df["ema200"] = df["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    df["rsi"] = rsi(df["close"])
    bb_mid = df["close"].rolling(20, min_periods=20).mean()
    bb_std = df["close"].rolling(20, min_periods=20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    width = (bb_upper - bb_lower).replace(0, math.nan)
    df["bb_percent"] = ((df["close"] - bb_lower) / width).clip(lower=0, upper=1)
    df["volume_mean"] = df["volume"].rolling(30, min_periods=30).mean()
    hi24 = df["high"].rolling(96, min_periods=96).max()
    lo24 = df["low"].rolling(96, min_periods=96).min()
    hi48 = df["high"].rolling(192, min_periods=192).max()
    lo48 = df["low"].rolling(192, min_periods=192).min()
    df["range_width_24h"] = (hi24 - lo24) / df["close"].replace(0, math.nan)
    df["range_width_48h"] = (hi48 - lo48) / df["close"].replace(0, math.nan)
    df["range_position_24h"] = (df["close"] - lo24) / (hi24 - lo24).replace(0, math.nan)
    df["range_position_48h"] = (df["close"] - lo48) / (hi48 - lo48).replace(0, math.nan)
    return df

def prepare_4h(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").reset_index(drop=True)
    df["adx_4h"] = adx(df)
    bb_mid = df["close"].rolling(20, min_periods=20).mean()
    bb_std = df["close"].rolling(20, min_periods=20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    df["bb_width_4h"] = (bb_upper - bb_lower) / bb_mid.replace(0, math.nan)
    df["bb_width_mean_4h"] = df["bb_width_4h"].rolling(20, min_periods=20).mean()
    df["ema50_4h"] = df["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    df["ema200_4h"] = df["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    df["regime_4h_derived"] = "unknown"
    ranging = (df["adx_4h"] < 42) & (df["bb_width_4h"] < df["bb_width_mean_4h"] * 1.15)
    trending = (df["adx_4h"] >= 25) & ((df["ema50_4h"] - df["ema200_4h"]).abs() / df["close"].replace(0, math.nan) > 0.005)
    df.loc[ranging, "regime_4h_derived"] = "ranging"
    df.loc[trending & ~ranging, "regime_4h_derived"] = "trending"
    return df[["date", "adx_4h", "bb_width_4h", "bb_width_mean_4h", "regime_4h_derived"]]

def is_candidate(row):
    if row.get("regime_4h_derived") != "ranging":
        return False
    values = [
        row.get("range_position_24h"),
        row.get("range_position_48h"),
        row.get("range_width_24h"),
        row.get("range_width_48h"),
        row.get("bb_percent"),
        row.get("rsi"),
        row.get("volume_mean"),
        row.get("ema200"),
        row.get("adx_4h"),
        row.get("bb_width_4h"),
        row.get("bb_width_mean_4h"),
    ]
    if any(pd.isna(value) for value in values):
        return False
    enough_range = row["range_width_24h"] >= 0.018 and row["range_width_48h"] >= 0.025
    range_not_expanding = row["adx_4h"] < 42 and row["bb_width_4h"] < row["bb_width_mean_4h"] * 1.15
    volume_ok = row["volume"] > row["volume_mean"] * 0.7
    near_upper = row["range_position_24h"] >= 0.72 and row["range_position_48h"] >= 0.65
    return (
        near_upper
        and enough_range
        and range_not_expanding
        and row["bb_percent"] > 0.82
        and row["rsi"] > 57
        and volume_ok
        and row["close"] < row["ema200"] * 1.10
        and row["volume"] > 0
    )

def candidate_for(pair, rows, index):
    row = rows.iloc[index]
    entry = float(row["close"])
    horizons = {}
    for horizon in HORIZONS:
        end = index + horizon
        if end >= len(rows) or entry <= 0:
            continue
        future = rows.iloc[index + 1 : end + 1]
        close_after = float(rows.iloc[end]["close"])
        max_high = float(future["high"].max())
        min_low = float(future["low"].min())
        return_bps = ((entry - close_after) / entry) * 10000
        mfe_bps = max(0.0, ((entry - min_low) / entry) * 10000)
        mae_bps = max(0.0, ((max_high - entry) / entry) * 10000)
        horizons[str(horizon)] = {
            "return_bps": round(return_bps, 4),
            "fee_adjusted_return_bps": round(return_bps - FEE_BPS, 4),
            "mfe_bps": round(mfe_bps, 4),
            "mae_bps": round(mae_bps, 4),
        }
    return {
        "pair": pair,
        "date": row["date"].isoformat(),
        "source": "derived_from_ohlcv_feather",
        "candidate_family": "v66_ranging_short_edge_derived",
        "alpha_state": "missing",
        "entry_close": round(entry, 8),
        "rsi": round(float(row["rsi"]), 4),
        "bb_percent": round(float(row["bb_percent"]), 4),
        "range_position_24h": round(float(row["range_position_24h"]), 4),
        "range_position_48h": round(float(row["range_position_48h"]), 4),
        "adx_4h": round(float(row["adx_4h"]), 4),
        "regime_4h_derived": row["regime_4h_derived"],
        "horizons": horizons,
    }

def inspect_pair(symbol):
    pair = f"{symbol}/USDT:USDT"
    file_symbol = f"{symbol}_USDT_USDT"
    path_15m = os.path.join(ROOT, f"{file_symbol}-15m-futures.feather")
    path_4h = os.path.join(ROOT, f"{file_symbol}-4h-futures.feather")
    if not os.path.exists(path_15m) or not os.path.exists(path_4h):
        return {
            "pair": pair,
            "source_status": "missing",
            "path_15m": path_15m,
            "path_4h": path_4h,
        }, []

    df15 = prepare_15m(pd.read_feather(path_15m))
    df4h = prepare_4h(pd.read_feather(path_4h))
    merged = pd.merge_asof(df15, df4h, on="date", direction="backward")
    max_date = merged["date"].max()
    study_start = max_date - pd.Timedelta(days=STUDY_DAYS)
    study = merged[merged["date"] >= study_start].copy().reset_index(drop=True)
    candidates = []
    for index, row in study.iterrows():
        if is_candidate(row):
            candidates.append(candidate_for(pair, study, index))

    return {
        "pair": pair,
        "source_status": "observed",
        "path_15m": path_15m,
        "path_4h": path_4h,
        "rows_15m_total": int(len(df15)),
        "rows_4h_total": int(len(df4h)),
        "study_rows": int(len(study)),
        "data_min": df15["date"].min().isoformat(),
        "data_max": max_date.isoformat(),
        "study_start": study_start.isoformat(),
        "study_days": round((max_date - study_start).total_seconds() / 86400, 4),
        "candidate_count": len(candidates),
        "summaries": summarize_candidates(candidates),
        "examples": candidates[:5],
    }, candidates

pairs = []
all_candidates = []
errors = []
for symbol in PAIRS:
    try:
        pair_report, candidates = inspect_pair(symbol)
        pairs.append(pair_report)
        all_candidates.extend(candidates)
    except Exception as error:
        errors.append({"symbol": symbol, "error_type": type(error).__name__, "error": str(error)[:300]})

classification = "insufficient"
classification_reasons = []
if len(all_candidates) < 100:
    classification_reasons.append("candidate sample is below the 100 candidate minimum gate")
if errors:
    classification_reasons.append("one or more pairs failed read-only feather inspection")
if not classification_reasons:
    h4 = summarize_candidates(all_candidates).get("4", {}).get("fee_adjusted_return", {})
    if h4.get("mean_bps") is not None and h4["mean_bps"] > 0:
        classification = "research_candidate"
        classification_reasons.append("derived candidate sample passes the initial fee-adjusted 4-candle mean gate")
    else:
        classification = "reject"
        classification_reasons.append("derived candidate sample does not pass the fee-adjusted 4-candle mean gate")

print(json.dumps({
    "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "container": "__CONTAINER__",
    "root": ROOT,
    "fee_bps": FEE_BPS,
    "study_days": STUDY_DAYS,
    "horizons_15m_candles": HORIZONS,
    "method": "derived_from_ohlcv_feather",
    "alpha_state": "missing",
    "pairs": pairs,
    "aggregate": {
        "candidate_count": len(all_candidates),
        "summaries": summarize_candidates(all_candidates),
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
  const container = process.env.V1129_CONTAINER || DEFAULT_CONTAINER;
  const script = REMOTE_COLLECTOR
    .replace("__PAIRS__", JSON.stringify(PAIRS))
    .replace("__FEE_BPS__", String(FEE_BPS))
    .replace("__STUDY_DAYS__", String(STUDY_DAYS))
    .replace("__CONTAINER__", container);
  const args = [
    "-i",
    key,
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "StrictHostKeyChecking=no",
    `${user}@${host}`,
    `docker exec -i ${container} python3 -`,
  ];
  const result = spawnSync("ssh", args, {
    input: script,
    encoding: "utf8",
    maxBuffer: 60 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(`collector failed: ${result.stderr || result.stdout || "unknown ssh/docker error"}`);
  }
  return JSON.parse(result.stdout.trim());
}

function buildReport(raw) {
  return {
    metadata: {
      strategy: "RegimeAwareV1129ResidualDragMicroSizer",
      generated_at: nowShanghaiIso(),
      observed_at_utc: raw.observed_at_utc,
      mode: "read_only_feather_ranging_short_historical_return_study",
      source: "server_container_feather_files",
      method: raw.method,
      alpha_state: raw.alpha_state,
      can_place_orders: false,
      reads_secret_material: false,
      reads_env_files: false,
      modifies_server_state: false,
      runs_backtest: false,
      modifies_strategy_or_config: false,
      downloads_or_refreshes_data: false,
      fee_bps: raw.fee_bps,
      study_days: raw.study_days,
      horizons_15m_candles: raw.horizons_15m_candles,
      container: raw.container,
      root: raw.root,
    },
    data_sources: [
      {
        id: "v1129_container_feather",
        kind: "server_container_feather_files",
        path_or_endpoint: raw.root,
        read_status: raw.errors.length === 0 ? "read" : "partial",
        contains_secret_material: false,
      },
    ],
    aggregate: raw.aggregate,
    pairs: raw.pairs,
    classification: raw.classification,
    errors: raw.errors,
    limitations: [
      "Candidate signals are derived from raw OHLCV feather files and recomputed indicators.",
      "Historical alpha-risk allowed/blocked state is missing.",
      "This is not a Freqtrade backtest and not a live execution-quality report.",
      "Feather data ends on 2026-07-03 and does not include the latest runtime API rows observed on 2026-07-06.",
    ],
    verdict: {
      can_enable_live_ranging_short: false,
      can_claim_replacement: false,
      can_claim_execution_quality: false,
      reason: "The study is offline and OHLCV-derived; it cannot authorize live strategy or configuration changes.",
      next_required_task: "Task 42: V11.29 Ranging-Short Calibration Decision Review",
    },
  };
}

function fmt(value) {
  if (value === null || value === undefined) return "missing";
  if (typeof value === "number") return String(Number(value.toFixed(4)));
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
      const h4 = pair.summaries?.["4"]?.fee_adjusted_return || {};
      return `| ${pair.pair} | ${pair.source_status} | ${fmt(pair.study_days)} | ${fmt(pair.study_rows)} | ${fmt(pair.candidate_count)} | ${fmt(pair.data_min)} | ${fmt(pair.data_max)} | ${fmt(h4.mean_bps)} |`;
    })
    .join("\n");
  const reasons = report.classification.reasons.map((reason) => `- ${reason}`).join("\n") || "- none";
  const limitations = report.limitations.map((item) => `- ${item}`).join("\n");
  const examples = (report.aggregate.sample_candidates || [])
    .slice(0, 8)
    .map((candidate) => {
      const h4 = candidate.horizons["4"] || {};
      return `| ${candidate.pair} | ${candidate.date} | ${fmt(candidate.entry_close)} | ${fmt(candidate.rsi)} | ${fmt(candidate.bb_percent)} | ${fmt(h4.fee_adjusted_return_bps)} | ${fmt(h4.mfe_bps)} | ${fmt(h4.mae_bps)} |`;
    })
    .join("\n");

  return `# V11.29 Feather-Based Ranging-Short Historical Return Study

## Summary

This report studies a 30d feather-based, OHLCV-derived approximation of the
\`v66_ranging_short_edge\` candidate family. It reads server container feather
files in read-only mode. It does not download or refresh data, run a Freqtrade
backtest, read secrets, modify strategy code, modify bot configuration, write
SQLite, or start/stop/restart any bot.

- Method: \`${report.metadata.method}\`
- Study days: ${report.metadata.study_days}
- Candidate count: ${report.aggregate.candidate_count}
- Fee assumption: ${report.metadata.fee_bps} bps round trip
- Alpha state: \`${report.metadata.alpha_state}\`
- Classification: \`${report.classification.status}\`
- Can enable live ranging-short: \`${report.verdict.can_enable_live_ranging_short}\`
- Can claim V11.29 replacement: \`${report.verdict.can_claim_replacement}\`

## Classification Reasons

${reasons}

## Aggregate Forward Return Summary

For a short candidate, positive return means future close is lower than the
candidate close. Fee-adjusted return subtracts the conservative round-trip fee
assumption.

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${horizonSummaryRows(report.aggregate.summaries)}

## Pair Matrix

| Pair | Source | Study days | Study rows | Candidates | Data min | Data max | 4-candle fee-adjusted mean bps |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
${pairRows}

## Representative Candidate Outcomes

| Pair | Time UTC | Entry close | RSI | BB% | 4-candle fee-adjusted bps | 4-candle MFE bps | 4-candle MAE bps |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
${examples || "| none | missing | missing | missing | missing | missing | missing | missing |"}

## Limitations

${limitations}

## What This Can Conclude

Observed:

- 30d feather data can be read for the V11.29 pair universe.
- OHLCV-derived candidate reconstruction can be computed without modifying
  server files or strategy code.
- Forward return, MFE, and MAE can be computed from historical candles.

Derived:

- The result can inform a calibration decision review.
- Because alpha state is missing, this cannot replace the runtime
  alpha-allowed/blocked analysis.

Insufficient:

- This is not a full strategy backtest.
- This is not a live execution-quality report.
- This does not include real orders, fills, fees, funding, slippage, or latency.
- This does not authorize a live strategy/config change.

## Recommended Next Task

Task 42: V11.29 Ranging-Short Calibration Decision Review

Scope:

- Compare Task 39 runtime-data result and Task 41 feather-data result.
- Decide whether the ranging-short research lane is rejected, needs more data,
  or deserves a separately authorized shadow/dry-run design.
- Do not modify live V11.29 strategy/config in the review task.

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
- download or refresh market data;
- write SQLite;
- modify server files;
- modify the original dirty workspace.
`;
}

function assertReport(report, markdown) {
  if (report.metadata.can_place_orders !== false) throw new Error("can_place_orders must be false");
  if (report.metadata.reads_secret_material !== false) throw new Error("reads_secret_material must be false");
  if (report.metadata.runs_backtest !== false) throw new Error("runs_backtest must be false");
  if (report.metadata.downloads_or_refreshes_data !== false) {
    throw new Error("downloads_or_refreshes_data must be false");
  }
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

