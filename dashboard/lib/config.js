"use strict";

const path = require("path");

const PROJECT_DIR = path.join(__dirname, "..", "..");
const PUBLIC_DIR = path.join(__dirname, "..", "public");

const PORT = Number(process.env.MONITOR_PORT || 8090);
const HOST = process.env.MONITOR_HOST || "0.0.0.0";
const DASHBOARD_USER = process.env.DASHBOARD_USER || "paodingo";
const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD;
const FREQTRADE_AUTH = process.env.FREQTRADE_API_AUTH || "freqtrader:freqtrade";
const REFRESH_HINT_SECONDS = Number(process.env.REFRESH_HINT_SECONDS || 5);
const HISTORY_DB_FILE = process.env.MONITOR_HISTORY_DB_FILE
  || (process.env.MONITOR_HISTORY_FILE
    ? process.env.MONITOR_HISTORY_FILE.replace(/\.jsonl$/i, ".sqlite")
    : path.join(PROJECT_DIR, "user_data", "monitor_history.sqlite"));
const HISTORY_RETENTION_DAYS = Number(process.env.MONITOR_HISTORY_RETENTION_DAYS || 30);
const HISTORY_SAMPLE_MS = Number(process.env.MONITOR_SAMPLE_MS || 60_000);
const HISTORY_SAMPLE_SECONDS = Math.round(HISTORY_SAMPLE_MS / 1000);
const API_LATENCY_WARN_MS = Number(process.env.MONITOR_API_LATENCY_WARN_MS || 3000);
const DATA_STALE_SECONDS = Number(process.env.MONITOR_DATA_STALE_SECONDS || 7200);
const ALPHA_RISK_CACHE_MS = Number(process.env.ALPHA_RISK_CACHE_MS || 30_000);
const ALPHA_RISK_PERIOD = process.env.ALPHA_RISK_PERIOD || "15m";
const ALPHA_RISK_LIMIT = Number(process.env.ALPHA_RISK_LIMIT || 12);
const ALPHA_RISK_TIMEOUT_MS = Number(process.env.ALPHA_RISK_TIMEOUT_MS || 8_000);
const ALLOW_REMOTE_FREQTRADE = process.env.MONITOR_ALLOW_REMOTE_FREQTRADE === "1";
const DEFAULT_PAIR = process.env.MONITOR_PAIR || "BTC/USDT:USDT";
const DEFAULT_TIMEFRAME = process.env.MONITOR_TIMEFRAME || "1h";
const DEFAULT_CHART_TIMEFRAME = process.env.MONITOR_CHART_TIMEFRAME || "15m";
const STRATEGY_MAIN_TIMEFRAME = process.env.STRATEGY_MAIN_TIMEFRAME || "15m";
const STRATEGY_INFORMATIVE_TIMEFRAME = process.env.STRATEGY_INFORMATIVE_TIMEFRAME || "4h";
const DEFAULT_CANDLE_LIMIT = Number(process.env.MONITOR_CANDLE_LIMIT || 240);

const BOTS = [
  {
    key: "v1129",
    label: process.env.BOT_V1129_LABEL || "V11.29 current",
    url: process.env.BOT_V1129_URL || "http://localhost:8122",
  },
  {
    key: "v1129_shadow",
    label: process.env.BOT_V1129_SHADOW_LABEL || "V11.29 ranging-short shadow",
    source: "sqlite",
    botName: "V11.29 ranging-short shadow",
    strategy: "RegimeAwareV1129RangingShortShadow",
    runmode: "dry_run",
    dryRun: true,
    state: "running",
    maxOpenTrades: 2,
    stakeAmount: 250,
    stakeCurrency: "USDT",
    dbFile: process.env.BOT_V1129_SHADOW_DB_FILE
      || path.join(PROJECT_DIR, "user_data", "tradesv3_v1129_ranging_short_shadow.dryrun.sqlite"),
  },
];

function isLocalFreqtradeUrl(rawUrl) {
  try {
    const hostname = new URL(rawUrl).hostname.toLowerCase();
    return hostname === "localhost"
      || hostname === "127.0.0.1"
      || hostname === "::1"
      || hostname === "[::1]";
  } catch {
    return false;
  }
}

if (!ALLOW_REMOTE_FREQTRADE) {
  for (const bot of BOTS) {
    if (!bot.url) {
      continue;
    }
    if (!isLocalFreqtradeUrl(bot.url)) {
      throw new Error(
        `BOT ${bot.key} url must point to localhost unless MONITOR_ALLOW_REMOTE_FREQTRADE=1 is set.`,
      );
    }
  }
}

const STATIC_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".map": "application/json; charset=utf-8",
};

module.exports = {
  API_LATENCY_WARN_MS,
  ALPHA_RISK_CACHE_MS,
  ALPHA_RISK_LIMIT,
  ALPHA_RISK_PERIOD,
  ALPHA_RISK_TIMEOUT_MS,
  ALLOW_REMOTE_FREQTRADE,
  BOTS,
  DATA_STALE_SECONDS,
  DASHBOARD_PASSWORD,
  DASHBOARD_USER,
  DEFAULT_CANDLE_LIMIT,
  DEFAULT_CHART_TIMEFRAME,
  DEFAULT_PAIR,
  DEFAULT_TIMEFRAME,
  FREQTRADE_AUTH,
  HISTORY_DB_FILE,
  HISTORY_RETENTION_DAYS,
  HISTORY_SAMPLE_MS,
  HISTORY_SAMPLE_SECONDS,
  HOST,
  PORT,
  PROJECT_DIR,
  PUBLIC_DIR,
  REFRESH_HINT_SECONDS,
  STRATEGY_INFORMATIVE_TIMEFRAME,
  STRATEGY_MAIN_TIMEFRAME,
  STATIC_TYPES,
};
