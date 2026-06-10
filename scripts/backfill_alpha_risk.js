#!/usr/bin/env node
"use strict";

const {
  ALPHA_RISK_LIMIT,
  ALPHA_RISK_PERIOD,
  ALPHA_RISK_TIMEOUT_MS,
  DEFAULT_PAIR,
  HISTORY_DB_FILE,
  HISTORY_RETENTION_DAYS,
} = require("../dashboard/lib/config");
const {
  BINANCE_FUTURES_ALPHA_ENDPOINTS,
  pairToBinanceSymbol,
} = require("../dashboard/lib/binance_futures_alpha");
const {
  buildHistoricalAlphaSnapshots,
  periodToMs,
} = require("../dashboard/lib/alpha_backfill");
const { MonitorStore } = require("../dashboard/lib/monitor_store");

const BASE_URL = "https://fapi.binance.com";
const MAX_DATA_LIMIT = 500;
const MAX_FUNDING_LIMIT = 1000;

function argValue(name, fallback = null) {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) {
    return fallback;
  }
  return process.argv[index + 1];
}

function hasArg(name) {
  return process.argv.includes(name);
}

function numeric(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

async function fetchJson(endpoint, params, timeoutMs) {
  const url = new URL(endpoint, BASE_URL);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url.toString(), { signal: controller.signal });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 160)}`);
    }
    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

function pageEndTime(rows, timeKey) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return null;
  }
  return rows.reduce((latest, row) => Math.max(latest, numeric(row[timeKey], 0)), 0);
}

async function fetchPaginated(endpoint, params, {
  startMs,
  endMs,
  timeKey = "timestamp",
  limit = MAX_DATA_LIMIT,
  timeoutMs,
}) {
  const rows = [];
  let cursor = startMs;
  while (cursor <= endMs) {
    const page = await fetchJson(endpoint, {
      ...params,
      startTime: cursor,
      endTime: endMs,
      limit,
    }, timeoutMs);
    const items = Array.isArray(page) ? page : [];
    rows.push(...items);
    if (items.length < limit) {
      break;
    }
    const latest = pageEndTime(items, timeKey);
    if (!latest || latest < cursor) {
      break;
    }
    cursor = latest + 1;
  }
  return rows;
}

async function fetchDataset(name, endpoint, params, options) {
  try {
    return {
      name,
      rows: await fetchPaginated(endpoint, params, options),
      error: null,
    };
  } catch (error) {
    return {
      name,
      rows: [],
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function existingSampledAtSet(store) {
  const rows = store.db.prepare("SELECT sampled_at FROM alpha_risk_samples").all();
  return new Set(rows.map((row) => row.sampled_at));
}

async function main() {
  const days = numeric(argValue("--days", process.env.ALPHA_RISK_BACKFILL_DAYS), 7);
  const pair = argValue("--pair", process.env.MONITOR_PAIR || DEFAULT_PAIR);
  const symbol = argValue("--symbol", pairToBinanceSymbol(pair));
  const period = argValue("--period", process.env.ALPHA_RISK_PERIOD || ALPHA_RISK_PERIOD);
  const limit = numeric(argValue("--limit", process.env.ALPHA_RISK_LIMIT), ALPHA_RISK_LIMIT);
  const timeoutMs = numeric(argValue("--timeout-ms", process.env.ALPHA_RISK_TIMEOUT_MS), ALPHA_RISK_TIMEOUT_MS);
  const dryRun = hasArg("--dry-run");
  const periodMs = periodToMs(period);
  const endMs = Math.floor((Date.now() - periodMs) / periodMs) * periodMs;
  const startMs = endMs - Math.max(1, days) * 24 * 60 * 60 * 1000;
  const fetchStartMs = startMs - Math.max(0, limit - 1) * periodMs;

  const dataParams = { symbol, period };
  const datasets = await Promise.all([
    fetchDataset("fundingRates", BINANCE_FUTURES_ALPHA_ENDPOINTS.fundingRate, { symbol }, {
      startMs: fetchStartMs,
      endMs,
      timeKey: "fundingTime",
      limit: MAX_FUNDING_LIMIT,
      timeoutMs,
    }),
    fetchDataset("openInterestHist", BINANCE_FUTURES_ALPHA_ENDPOINTS.openInterestHist, dataParams, { startMs: fetchStartMs, endMs, timeoutMs }),
    fetchDataset("globalLongShort", BINANCE_FUTURES_ALPHA_ENDPOINTS.globalLongShort, dataParams, { startMs: fetchStartMs, endMs, timeoutMs }),
    fetchDataset("topTraderPosition", BINANCE_FUTURES_ALPHA_ENDPOINTS.topTraderPosition, dataParams, { startMs: fetchStartMs, endMs, timeoutMs }),
    fetchDataset("topTraderAccount", BINANCE_FUTURES_ALPHA_ENDPOINTS.topTraderAccount, dataParams, { startMs: fetchStartMs, endMs, timeoutMs }),
    fetchDataset("takerFlow", BINANCE_FUTURES_ALPHA_ENDPOINTS.takerFlow, dataParams, { startMs: fetchStartMs, endMs, timeoutMs }),
  ]);
  const datasetMap = Object.fromEntries(datasets.map((dataset) => [dataset.name, dataset.rows]));
  const fetchErrors = datasets
    .filter((dataset) => dataset.error)
    .map((dataset) => ({ key: dataset.name, message: dataset.error }));

  const snapshots = buildHistoricalAlphaSnapshots({
    pair,
    symbol,
    period,
    limit,
    startMs,
    endMs,
    payloads: {
      fundingRates: datasetMap.fundingRates,
      openInterestHist: datasetMap.openInterestHist,
      globalLongShort: datasetMap.globalLongShort,
      topTraderPosition: datasetMap.topTraderPosition,
      topTraderAccount: datasetMap.topTraderAccount,
      takerFlow: datasetMap.takerFlow,
    },
  });

  if (dryRun) {
    console.log(JSON.stringify({
      dryRun,
      pair,
      symbol,
      period,
      days,
      snapshots: snapshots.length,
      first: snapshots[0]?.sampledAt || null,
      last: snapshots.at(-1)?.sampledAt || null,
      errors: fetchErrors,
    }, null, 2));
    return;
  }

  const store = new MonitorStore({ dbFile: HISTORY_DB_FILE, retentionDays: HISTORY_RETENTION_DAYS });
  try {
    const existing = existingSampledAtSet(store);
    let inserted = 0;
    let skipped = 0;
    for (const snapshot of snapshots) {
      if (existing.has(snapshot.sampledAt)) {
        skipped += 1;
        continue;
      }
      store.recordAlphaRiskSample(snapshot);
      existing.add(snapshot.sampledAt);
      inserted += 1;
    }
    console.log(JSON.stringify({
      dryRun,
      dbFile: HISTORY_DB_FILE,
      pair,
      symbol,
      period,
      days,
      fetched: {
        fundingRates: datasetMap.fundingRates.length,
        openInterestHist: datasetMap.openInterestHist.length,
        globalLongShort: datasetMap.globalLongShort.length,
        topTraderPosition: datasetMap.topTraderPosition.length,
        topTraderAccount: datasetMap.topTraderAccount.length,
        takerFlow: datasetMap.takerFlow.length,
      },
      snapshots: snapshots.length,
      inserted,
      skipped,
      first: snapshots[0]?.sampledAt || null,
      last: snapshots.at(-1)?.sampledAt || null,
      errors: fetchErrors,
    }, null, 2));
  } finally {
    store.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exitCode = 1;
});
