"use strict";

const path = require("path");

const PROJECT_DIR = path.join(__dirname, "..", "..");
const PUBLIC_DIR = path.join(__dirname, "..", "public");

const PORT = Number(process.env.MONITOR_PORT || 8090);
const HOST = process.env.MONITOR_HOST || "0.0.0.0";
const DASHBOARD_USER = process.env.DASHBOARD_USER || "paodingo";
const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD;
const FREQTRADE_AUTH = process.env.FREQTRADE_API_AUTH || "freqtrader:freqtrade";
const REFRESH_HINT_SECONDS = Number(process.env.REFRESH_HINT_SECONDS || 15);
const HISTORY_FILE = process.env.MONITOR_HISTORY_FILE
  || path.join(PROJECT_DIR, "user_data", "monitor_history.jsonl");
const HISTORY_RETENTION_DAYS = Number(process.env.MONITOR_HISTORY_RETENTION_DAYS || 30);
const HISTORY_RETENTION_MS = HISTORY_RETENTION_DAYS * 24 * 60 * 60 * 1000;
const HISTORY_SAMPLE_MS = Number(process.env.MONITOR_SAMPLE_MS || 60_000);
const HISTORY_SAMPLE_SECONDS = Math.round(HISTORY_SAMPLE_MS / 1000);
const DEFAULT_PAIR = process.env.MONITOR_PAIR || "BTC/USDT:USDT";
const DEFAULT_TIMEFRAME = process.env.MONITOR_TIMEFRAME || "1h";
const DEFAULT_CANDLE_LIMIT = Number(process.env.MONITOR_CANDLE_LIMIT || 240);

const BOTS = [
  {
    key: "v6",
    label: process.env.BOT_V6_LABEL || "V6.2",
    url: process.env.BOT_V6_URL || "http://localhost:8080",
  },
  {
    key: "v61",
    label: "V6.1",
    url: process.env.BOT_V61_URL || "http://localhost:8081",
  },
];

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
  BOTS,
  DASHBOARD_PASSWORD,
  DASHBOARD_USER,
  DEFAULT_CANDLE_LIMIT,
  DEFAULT_PAIR,
  DEFAULT_TIMEFRAME,
  FREQTRADE_AUTH,
  HISTORY_FILE,
  HISTORY_RETENTION_DAYS,
  HISTORY_RETENTION_MS,
  HISTORY_SAMPLE_MS,
  HISTORY_SAMPLE_SECONDS,
  HOST,
  PORT,
  PUBLIC_DIR,
  REFRESH_HINT_SECONDS,
  STATIC_TYPES,
};
