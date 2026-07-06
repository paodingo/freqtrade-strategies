#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const OUT_DIR = path.join("reports", "v1129_execution_validation");
const JSON_OUT = path.join(OUT_DIR, "v1129_pre_filter_signal_reconstruction.json");
const MD_OUT = path.join(OUT_DIR, "v1129_pre_filter_signal_reconstruction.md");

const DEFAULT_HOST = "43.134.72.69";
const DEFAULT_USER = "ubuntu";
const DEFAULT_KEY = "D:\\key\\openclaw\\clf.pem";
const DEFAULT_PORT = 8122;
const DEFAULT_LIMIT = 672;

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
import os
import sqlite3
import urllib.parse
import urllib.request

PAIRS = __PAIRS__
PORT = __PORT__
LIMIT = __LIMIT__
AUTH = "Basic " + base64.b64encode(b"freqtrader:freqtrade").decode()
BASE = f"http://localhost:{PORT}/api/v1/pair_candles"
ALPHA_DB = "/freqtrade/project/user_data/monitor_history.sqlite"

CORE_PAIRS = {"BTC/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT"}
WATCH_PAIRS = {"ETH/USDT:USDT", "BNB/USDT:USDT"}

def as_bool(value):
    if value in (True, 1, "1", "true", "True"):
        return True
    return False

def num(row, key, default=0.0):
    try:
        value = row.get(key, default)
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def text(row, key):
    value = row.get(key)
    return "" if value is None else str(value)

def count(rows, predicate):
    total = 0
    for row in rows:
        try:
            if predicate(row):
                total += 1
        except Exception:
            pass
    return total

def fetch_pair(pair):
    query = urllib.parse.urlencode({"pair": pair, "timeframe": "15m", "limit": str(LIMIT)})
    req = urllib.request.Request(BASE + "?" + query, headers={"Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)
    columns = data.get("columns") or []
    rows = [dict(zip(columns, raw)) for raw in data.get("data", [])]
    return data, rows

def masks(row):
    trend_up = as_bool(row.get("trend_4h_up"))
    trend_down = as_bool(row.get("trend_4h_down"))
    pullback_long = as_bool(row.get("pullback_ema_long"))
    breakout_long = as_bool(row.get("bb_breakout_long"))
    rsi_recovery = as_bool(row.get("rsi_recovery"))
    pullback_short = as_bool(row.get("pullback_ema_short"))
    breakout_short = as_bool(row.get("bb_breakout_short"))
    rsi_exhaustion = as_bool(row.get("rsi_exhaustion"))
    volume = num(row, "volume")
    close = num(row, "close")
    ema200 = num(row, "ema200")
    regime = text(row, "regime_4h").lower()

    trending_long = (
        regime == "trending"
        and trend_up
        and close > ema200
        and (pullback_long or breakout_long or rsi_recovery)
        and volume > 0
    )
    trending_short = (
        regime == "trending"
        and trend_down
        and close < ema200
        and (pullback_short or breakout_short or rsi_exhaustion)
        and volume > 0
    )

    enough_range = num(row, "range_width_24h") >= 0.018 and num(row, "range_width_48h") >= 0.025
    range_not_expanding = (
        num(row, "adx_4h", 100) < 42
        and num(row, "bb_width_4h", 1.0) < num(row, "bb_width_mean_4h", 0.0) * 1.15
    )
    volume_ok = volume > num(row, "volume_mean") * 0.7
    near_lower = num(row, "range_position_24h", 0.5) <= 0.28 and num(row, "range_position_48h", 0.5) <= 0.35
    near_upper = num(row, "range_position_24h", 0.5) >= 0.72 and num(row, "range_position_48h", 0.5) >= 0.65
    ranging_long = (
        regime == "ranging"
        and near_lower
        and enough_range
        and range_not_expanding
        and num(row, "bb_percent", 0.5) < 0.18
        and num(row, "rsi", 50) < 43
        and volume_ok
        and close > ema200 * 0.90
        and volume > 0
    )
    ranging_short = (
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

    alpha_long = as_bool(row.get("alpha_filter_block_long"))
    alpha_short = as_bool(row.get("alpha_filter_block_short"))
    raw_long = trending_long or ranging_long
    raw_short = trending_short or ranging_short
    after_alpha_long = raw_long and not alpha_long
    after_alpha_short = raw_short and not alpha_short
    after_alpha_trending_short = trending_short and not alpha_short
    after_alpha_ranging_short = ranging_short and not alpha_short

    return {
        "trending_long": trending_long,
        "trending_short": trending_short,
        "ranging_long": ranging_long,
        "ranging_short": ranging_short,
        "raw_long": raw_long,
        "raw_short": raw_short,
        "alpha_long": alpha_long,
        "alpha_short": alpha_short,
        "after_alpha_long": after_alpha_long,
        "after_alpha_short": after_alpha_short,
        "after_alpha_trending_short": after_alpha_trending_short,
        "after_alpha_ranging_short": after_alpha_ranging_short,
    }

def pair_tier(pair):
    if pair in CORE_PAIRS:
        return "core"
    if pair in WATCH_PAIRS:
        return "watch"
    return "watch"

def inspect_pair(pair):
    data, rows = fetch_pair(pair)
    mask_rows = [masks(row) for row in rows]
    tags = collections.Counter(text(row, "enter_tag") for row in rows if text(row, "enter_tag"))
    tier = pair_tier(pair)
    core_candidate = sum(1 for mask in mask_rows if mask["after_alpha_trending_short"])
    watch_candidate = core_candidate if tier == "watch" else 0
    core_pair_candidate = core_candidate if tier == "core" else 0
    gate_counts = {
        "v1118_blocked": count(rows, lambda row: text(row, "v1118_volatility_shock_gate").startswith("blocked")),
        "v1122_retagged_or_sized": count(rows, lambda row: text(row, "v1122_ada_capitulation_gate") not in ("", "pass")),
        "v1124_retagged_or_sized": count(rows, lambda row: text(row, "v1124_rebound_sizer_gate") not in ("", "pass")),
        "v1127_retagged_or_sized": count(rows, lambda row: text(row, "v1127_dual_trap_gate") not in ("", "pass")),
        "v1129_retagged_or_sized": count(rows, lambda row: text(row, "v1129_residual_drag_gate") not in ("", "pass")),
    }

    return {
        "pair": pair,
        "source_status": "observed",
        "rows": len(rows),
        "data_start": data.get("data_start", ""),
        "data_stop": data.get("data_stop", ""),
        "last_analyzed": data.get("last_analyzed", ""),
        "last_4h_context": rows[-1].get("date_4h") if rows else None,
        "raw_candidates": {
            "trending_long": sum(1 for mask in mask_rows if mask["trending_long"]),
            "trending_short": sum(1 for mask in mask_rows if mask["trending_short"]),
            "ranging_long": sum(1 for mask in mask_rows if mask["ranging_long"]),
            "ranging_short": sum(1 for mask in mask_rows if mask["ranging_short"]),
        },
        "alpha_filter": {
            "raw_long_candidates": sum(1 for mask in mask_rows if mask["raw_long"]),
            "raw_short_candidates": sum(1 for mask in mask_rows if mask["raw_short"]),
            "blocked_long_candidates": sum(1 for mask in mask_rows if mask["raw_long"] and mask["alpha_long"]),
            "blocked_short_candidates": sum(1 for mask in mask_rows if mask["raw_short"] and mask["alpha_short"]),
            "surviving_long_after_alpha": sum(1 for mask in mask_rows if mask["after_alpha_long"]),
            "surviving_short_after_alpha": sum(1 for mask in mask_rows if mask["after_alpha_short"]),
        },
        "short_core": {
            "long_blocked_by_design": sum(1 for mask in mask_rows if mask["after_alpha_long"]),
            "ranging_blocked_by_design": sum(1 for mask in mask_rows if mask["after_alpha_ranging_short"]),
            "non_core_short_blocked": sum(
                1 for mask in mask_rows if mask["after_alpha_short"] and not mask["after_alpha_trending_short"]
            ),
            "v102_trending_short_core": core_candidate,
        },
        "pair_tier": {
            "tier": tier,
            "core_candidate_rows": core_pair_candidate,
            "watch_candidate_rows": watch_candidate,
            "blocked_pair_rows": 0,
            "stake_eligible_rows": core_candidate,
            "stake_unknown_rows": 0,
        },
        "v11_gates": {
            **gate_counts,
            "final_enter_long": count(rows, lambda row: row.get("enter_long") == 1),
            "final_enter_short": count(rows, lambda row: row.get("enter_short") == 1),
        },
        "observed_tags": dict(tags.most_common(12)),
        "observed_api_signals": {
            "enter_long_signals": data.get("enter_long_signals"),
            "enter_short_signals": data.get("enter_short_signals"),
        },
    }

def alpha_summary():
    if not os.path.exists(ALPHA_DB):
        return {"source_status": "missing", "path": ALPHA_DB}
    conn = sqlite3.connect("file:" + ALPHA_DB + "?mode=ro", uri=True)
    cur = conn.cursor()
    try:
        count_row = cur.execute(
            "select count(*), min(sampled_at), max(sampled_at) from alpha_risk_samples"
        ).fetchone()
        rows = cur.execute(
            "select sampled_at, risk_level, risk_score, payload from alpha_risk_samples order by sampled_at desc limit 96"
        ).fetchall()
        levels = collections.Counter()
        flags = collections.Counter()
        scores = []
        for sampled_at, risk_level, risk_score, payload in rows:
            levels[risk_level or ""] += 1
            if risk_score is not None:
                scores.append(float(risk_score))
            try:
                parsed = json.loads(payload or "{}")
                for flag in parsed.get("risk", {}).get("flags", []):
                    key = flag.get("key")
                    if key:
                        flags[key] += 1
            except Exception:
                pass
        return {
            "source_status": "observed",
            "path": ALPHA_DB,
            "count": count_row[0],
            "min_sampled_at": count_row[1],
            "max_sampled_at": count_row[2],
            "recent_96_levels": dict(levels),
            "recent_96_top_flags": dict(flags.most_common(12)),
            "recent_96_score_min": min(scores) if scores else None,
            "recent_96_score_max": max(scores) if scores else None,
        }
    finally:
        conn.close()

pairs = []
errors = []
for pair in PAIRS:
    try:
        pairs.append(inspect_pair(pair))
    except Exception as error:
        errors.append({"pair": pair, "error_type": type(error).__name__, "error": str(error)[:240]})

print(json.dumps({
    "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "port": PORT,
    "limit": LIMIT,
    "pairs": pairs,
    "errors": errors,
    "alpha_summary": alpha_summary(),
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

function addCounts(target, source) {
  for (const [key, value] of Object.entries(source || {})) {
    if (typeof value === "number") {
      target[key] = (target[key] || 0) + value;
    }
  }
}

function runCollector() {
  const host = process.env.V1129_SSH_HOST || DEFAULT_HOST;
  const user = process.env.V1129_SSH_USER || DEFAULT_USER;
  const key = process.env.V1129_SSH_KEY || DEFAULT_KEY;
  const port = Number(process.env.V1129_API_PORT || DEFAULT_PORT);
  const limit = Number(process.env.V1129_RECONSTRUCTION_LIMIT || DEFAULT_LIMIT);
  const script = REMOTE_COLLECTOR
    .replace("__PAIRS__", JSON.stringify(PAIRS))
    .replace("__PORT__", String(port))
    .replace("__LIMIT__", String(limit));
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
    maxBuffer: 20 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(`collector failed: ${result.stderr || result.stdout || "unknown ssh error"}`);
  }
  return JSON.parse(result.stdout.trim());
}

function assessRootCause(aggregate) {
  const rawShort = aggregate.raw_candidates.trending_short + aggregate.raw_candidates.ranging_short;
  const blockedShort = aggregate.alpha_filter.blocked_short_candidates;
  const survivingShort = aggregate.alpha_filter.surviving_short_after_alpha;
  const shortCore = aggregate.short_core.v102_trending_short_core;
  const v11Blocked = aggregate.v11_gates.v1118_blocked + aggregate.v11_gates.v1129_retagged_or_sized;

  if (rawShort === 0) {
    return {
      primary_layer: "raw_trending_short_absent",
      secondary_layers: ["long_candidates_blocked_by_design", "alpha_long_filter"],
      confidence: "high",
      reason: "No raw short candidates were reconstructed from the runtime dataframe columns.",
    };
  }
  if (blockedShort >= rawShort && survivingShort === 0) {
    return {
      primary_layer: "alpha_filter_short_block",
      secondary_layers: ["raw_short_candidates_present"],
      confidence: "high",
      reason: "Raw short candidates exist, but all are blocked by alpha_filter_block_short.",
    };
  }
  if (survivingShort > 0 && shortCore === 0) {
    return {
      primary_layer: "v102_short_core_pruning",
      secondary_layers: ["non_core_or_ranging_short_candidates"],
      confidence: "high",
      reason: "Short candidates survive alpha, but none satisfy V10.2 trending-short core semantics.",
    };
  }
  if (shortCore > 0 && aggregate.v11_gates.final_enter_short === 0 && v11Blocked > 0) {
    return {
      primary_layer: "v11_gate_block",
      secondary_layers: ["short_core_candidates_present"],
      confidence: "medium",
      reason: "Short-core candidates exist, final entries are zero, and later V11 gate activity is present.",
    };
  }
  return {
    primary_layer: "unknown",
    secondary_layers: [],
    confidence: "low",
    reason: "Available counts do not isolate a single suppressing layer.",
  };
}

function buildReport(raw) {
  const aggregate = {
    rows: 0,
    raw_candidates: {},
    alpha_filter: {},
    short_core: {},
    pair_tier: {},
    v11_gates: {},
    final_entries: {},
    observed_tags: {},
  };

  for (const pair of raw.pairs) {
    aggregate.rows += pair.rows || 0;
    addCounts(aggregate.raw_candidates, pair.raw_candidates);
    addCounts(aggregate.alpha_filter, pair.alpha_filter);
    addCounts(aggregate.short_core, pair.short_core);
    addCounts(aggregate.pair_tier, pair.pair_tier);
    addCounts(aggregate.v11_gates, pair.v11_gates);
    aggregate.final_entries.enter_long = (aggregate.final_entries.enter_long || 0) + pair.v11_gates.final_enter_long;
    aggregate.final_entries.enter_short = (aggregate.final_entries.enter_short || 0) + pair.v11_gates.final_enter_short;
    for (const [tag, count] of Object.entries(pair.observed_tags || {})) {
      aggregate.observed_tags[tag] = (aggregate.observed_tags[tag] || 0) + count;
    }
  }

  return {
    metadata: {
      strategy: "RegimeAwareV1129ResidualDragMicroSizer",
      generated_at: nowShanghaiIso(),
      observed_at_utc: raw.observed_at_utc,
      mode: "read_only_pre_filter_signal_reconstruction",
      source: "runtime_pair_candles_api",
      can_place_orders: false,
      reads_secret_material: false,
      reads_env_files: false,
      modifies_server_state: false,
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
      {
        id: "alpha_summary",
        kind: "sqlite_summary",
        path_or_endpoint: raw.alpha_summary.path,
        read_status: raw.alpha_summary.source_status,
        contains_secret_material: false,
      },
    ],
    alpha_summary: raw.alpha_summary,
    aggregate,
    pairs: raw.pairs,
    errors: raw.errors,
    root_cause_assessment: assessRootCause(aggregate),
    recommended_next_task: "Task 36: V11.29 Short-Core Condition Calibration Plan",
  };
}

function assertReport(report, markdown) {
  const allowedPrimary = new Set([
    "raw_trending_short_absent",
    "alpha_filter_short_block",
    "v102_short_core_pruning",
    "v11_gate_block",
    "unknown",
  ]);
  if (!allowedPrimary.has(report.root_cause_assessment.primary_layer)) {
    throw new Error(`invalid primary_layer: ${report.root_cause_assessment.primary_layer}`);
  }
  if (report.metadata.can_place_orders !== false || report.metadata.reads_secret_material !== false) {
    throw new Error("safety metadata must remain false");
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

function renderMarkdown(report) {
  const aggregate = report.aggregate;
  const topTags = Object.entries(aggregate.observed_tags)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([tag, count]) => `| \`${tag}\` | ${count} |`)
    .join("\n");
  const pairRows = report.pairs
    .map(
      (pair) =>
        `| ${pair.pair} | ${pair.rows} | ${pair.raw_candidates.trending_short} | ${pair.raw_candidates.ranging_short} | ${pair.alpha_filter.blocked_short_candidates} | ${pair.short_core.v102_trending_short_core} | ${pair.v11_gates.final_enter_short} |`,
    )
    .join("\n");

  return `# V11.29 Pre-Filter Signal Reconstruction

## Summary

This report reconstructs V11.29 signal counts from the read-only runtime
\`pair_candles\` API and a sanitized alpha-risk SQLite summary. It does not read
secret files, place orders, run backtests, modify strategy code, modify bot
configuration, or restart any bot.

- Rows reconstructed: ${aggregate.rows}
- Raw trending short candidates: ${aggregate.raw_candidates.trending_short || 0}
- Raw ranging short candidates: ${aggregate.raw_candidates.ranging_short || 0}
- Short candidates blocked by alpha: ${aggregate.alpha_filter.blocked_short_candidates || 0}
- V10.2 short-core candidates: ${aggregate.short_core.v102_trending_short_core || 0}
- Final enter_short rows: ${aggregate.final_entries.enter_short || 0}
- Primary layer: \`${report.root_cause_assessment.primary_layer}\`
- Confidence: \`${report.root_cause_assessment.confidence}\`

## Root Cause Assessment

${report.root_cause_assessment.reason}

## Aggregate Funnel

| Layer | Count |
| --- | ---: |
| raw trending long | ${aggregate.raw_candidates.trending_long || 0} |
| raw trending short | ${aggregate.raw_candidates.trending_short || 0} |
| raw ranging long | ${aggregate.raw_candidates.ranging_long || 0} |
| raw ranging short | ${aggregate.raw_candidates.ranging_short || 0} |
| alpha blocked long candidates | ${aggregate.alpha_filter.blocked_long_candidates || 0} |
| alpha blocked short candidates | ${aggregate.alpha_filter.blocked_short_candidates || 0} |
| surviving long after alpha | ${aggregate.alpha_filter.surviving_long_after_alpha || 0} |
| surviving short after alpha | ${aggregate.alpha_filter.surviving_short_after_alpha || 0} |
| V10.2 long blocked by design | ${aggregate.short_core.long_blocked_by_design || 0} |
| V10.2 ranging blocked by design | ${aggregate.short_core.ranging_blocked_by_design || 0} |
| V10.2 non-core short blocked | ${aggregate.short_core.non_core_short_blocked || 0} |
| V10.2 short-core candidates | ${aggregate.short_core.v102_trending_short_core || 0} |
| V11.18 blocked | ${aggregate.v11_gates.v1118_blocked || 0} |
| V11.29 retagged/sized | ${aggregate.v11_gates.v1129_retagged_or_sized || 0} |
| final enter_long | ${aggregate.final_entries.enter_long || 0} |
| final enter_short | ${aggregate.final_entries.enter_short || 0} |

## Pair Breakdown

| Pair | Rows | Raw trending short | Raw ranging short | Alpha blocked short | V10.2 short core | Final short |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
${pairRows}

## Observed Tags

| Tag | Rows |
| --- | ---: |
${topTags || "| none | 0 |"}

## Alpha Summary

- Source status: \`${report.alpha_summary.source_status}\`
- Sample count: ${report.alpha_summary.count ?? "unknown"}
- Min sampled_at: \`${report.alpha_summary.min_sampled_at ?? "unknown"}\`
- Max sampled_at: \`${report.alpha_summary.max_sampled_at ?? "unknown"}\`
- Recent levels: \`${JSON.stringify(report.alpha_summary.recent_96_levels || {})}\`
- Recent top flags: \`${JSON.stringify(report.alpha_summary.recent_96_top_flags || {})}\`

## Interpretation

The reconstruction identifies the suppressing layer before final entries are
created. A non-empty \`enter_tag\` remains metadata; it is not an order trigger.
Final entries require \`enter_long == 1\` or \`enter_short == 1\`.

## Recommended Next Task

${report.recommended_next_task}
`;
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
