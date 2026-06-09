#!/usr/bin/env node
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.MONITOR_PORT || 8090);
const HOST = process.env.MONITOR_HOST || "0.0.0.0";
const DASHBOARD_USER = process.env.DASHBOARD_USER || "paodingo";
const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD;
const FREQTRADE_AUTH = process.env.FREQTRADE_API_AUTH || "freqtrader:freqtrade";
const REFRESH_HINT_SECONDS = Number(process.env.REFRESH_HINT_SECONDS || 15);
const PROJECT_DIR = path.join(__dirname, "..");
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

const PUBLIC_DIR = path.join(__dirname, "public");
const STATIC_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".map": "application/json; charset=utf-8",
};

let historyCache = [];
let sampleInFlight = false;
let lastSampleAt = null;
let lastSampleError = null;

function send(res, status, body, headers = {}) {
  const payload = Buffer.isBuffer(body) ? body : Buffer.from(String(body));
  res.writeHead(status, {
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
    ...headers,
  });
  res.end(payload);
}

function sendJson(res, status, body) {
  send(res, status, JSON.stringify(body), {
    "Content-Type": "application/json; charset=utf-8",
  });
}

function unauthorized(res) {
  res.writeHead(401, {
    "WWW-Authenticate": 'Basic realm="Freqtrade Monitor"',
    "Content-Type": "text/plain; charset=utf-8",
  });
  res.end("Authentication required\n");
}

function isAuthorized(req) {
  if (!DASHBOARD_PASSWORD) {
    return false;
  }

  const header = req.headers.authorization || "";
  if (!header.startsWith("Basic ")) {
    return false;
  }

  const decoded = Buffer.from(header.slice(6), "base64").toString("utf8");
  const separator = decoded.indexOf(":");
  if (separator < 0) {
    return false;
  }

  const username = decoded.slice(0, separator);
  const password = decoded.slice(separator + 1);
  return username === DASHBOARD_USER && password === DASHBOARD_PASSWORD;
}

function freqtradeHeaders() {
  return {
    Authorization: `Basic ${Buffer.from(FREQTRADE_AUTH).toString("base64")}`,
  };
}

async function fetchJson(baseUrl, endpoint) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(`${baseUrl}${endpoint}`, {
      headers: freqtradeHeaders(),
      signal: controller.signal,
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 120)}`);
    }
    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

function numeric(value, fallback = null) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatBotState(state) {
  return {
    running: "运行中",
    stopped: "已停止",
    paused: "暂停中",
    reload_config: "重载配置中",
  }[state] || state || "-";
}

function formatRunmode(runmode, dryRun) {
  if (dryRun || runmode === "dry_run") {
    return "模拟盘";
  }
  if (runmode === "live") {
    return "实盘";
  }
  if (runmode === "backtest") {
    return "回测";
  }
  return runmode || "-";
}

function formatSignal(tag) {
  return {
    trending_long: "趋势做多",
    trending_short: "趋势做空",
    ranging_long: "震荡做多",
    ranging_short: "震荡做空",
  }[tag] || tag || "-";
}

function latestOpenTrade(bot) {
  return Array.isArray(bot?.openTrades) && bot.openTrades.length > 0 ? bot.openTrades[0] : null;
}

function buildBotPlainStatus(bot) {
  if (!bot?.ok) {
    return {
      stateText: "API 不可用",
      runmodeText: "-",
      signalText: "-",
      directionText: "暂时无法读取 bot 状态。",
      legacyStakeNotice: null,
    };
  }

  const trade = latestOpenTrade(bot);
  const plannedStake = numeric(bot.stakeAmount, 0);
  const currentStake = numeric(trade?.stake_amount, 0);
  const legacyStakeNotice = trade && plannedStake && currentStake && currentStake < plannedStake * 0.5
    ? `当前持仓仍是旧仓，占用约 ${currentStake.toFixed(2)} USDT；这笔平仓后，下一次新开仓会按计划单笔投入 ${plannedStake.toFixed(2)} USDT 计算。`
    : null;

  return {
    stateText: formatBotState(bot.state),
    runmodeText: formatRunmode(bot.runmode, bot.dryRun),
    signalText: formatSignal(trade?.enter_tag),
    directionText: trade
      ? (trade.is_short ? "当前做空，BTC 下跌时盈利。" : "当前做多，BTC 上涨时盈利。")
      : "当前没有持仓，等待下一次信号。",
    legacyStakeNotice,
  };
}

async function loadBot(bot) {
  const startedAt = Date.now();
  try {
    const [ping, config, count, profit, balance, status] = await Promise.all([
      fetchJson(bot.url, "/api/v1/ping"),
      fetchJson(bot.url, "/api/v1/show_config"),
      fetchJson(bot.url, "/api/v1/count"),
      fetchJson(bot.url, "/api/v1/profit"),
      fetchJson(bot.url, "/api/v1/balance").catch(() => null),
      fetchJson(bot.url, "/api/v1/status").catch(() => []),
    ]);

    const stakeCurrency = balance?.stake || "USDT";
    const stakeBalance = Array.isArray(balance?.currencies)
      ? balance.currencies.find((item) => item.currency === stakeCurrency && !item.is_position)
      : null;

    return {
      key: bot.key,
      label: bot.label,
      ok: true,
      latencyMs: Date.now() - startedAt,
      ping: ping.status,
      botName: config.bot_name,
      strategy: config.strategy,
      state: config.state,
      runmode: config.runmode,
      dryRun: config.dry_run,
      maxOpenTrades: config.max_open_trades,
      stakeAmount: config.stake_amount,
      tradableBalanceRatio: config.tradable_balance_ratio,
      currentOpenTrades: count.current,
      totalStake: count.total_stake,
      stakeCurrency,
      balance: balance
        ? {
            total: balance.total,
            totalBot: balance.total_bot,
            value: balance.value,
            valueBot: balance.value_bot,
            startingCapital: balance.starting_capital,
            startingCapitalPct: balance.starting_capital_pct,
            freeStake: stakeBalance?.free,
            usedStake: stakeBalance?.used,
            botOwnedStake: stakeBalance?.bot_owned,
          }
        : null,
      profitAllCoin: profit.profit_all_coin,
      profitAllPercentMean: profit.profit_all_percent_mean,
      profitAllPercent: profit.profit_all_percent,
      profitClosedCoin: profit.profit_closed_coin,
      profitClosedPercent: profit.profit_closed_percent,
      tradeCount: profit.trade_count,
      closedTradeCount: profit.closed_trade_count,
      firstTradeDate: profit.first_trade_date,
      latestTradeDate: profit.latest_trade_date,
      botStartDate: profit.bot_start_date,
      tradingVolume: profit.trading_volume,
      currentDrawdown: profit.current_drawdown,
      currentDrawdownAbs: profit.current_drawdown_abs,
      winrate: profit.winrate,
      profitFactor: profit.profit_factor,
      maxDrawdown: profit.max_drawdown,
      maxDrawdownAbs: profit.max_drawdown_abs,
      openTrades: Array.isArray(status) ? status : [],
      plain: null,
      error: null,
    };
  } catch (error) {
    return {
      key: bot.key,
      label: bot.label,
      ok: false,
      latencyMs: Date.now() - startedAt,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function loadBots() {
  const bots = await Promise.all(BOTS.map(loadBot));
  return bots.map((bot) => ({
    ...bot,
    plain: buildBotPlainStatus(bot),
  }));
}

function buildComparison(results) {
  const v6 = results.find((bot) => bot.key === "v6");
  const v61 = results.find((bot) => bot.key === "v61");
  if (!v6?.ok || !v61?.ok) {
    return null;
  }
  return {
    profitAllCoinDelta: Number(v61.profitAllCoin || 0) - Number(v6.profitAllCoin || 0),
    totalBotDelta: Number(v61.balance?.totalBot || 0) - Number(v6.balance?.totalBot || 0),
    valueBotDelta: Number(v61.balance?.valueBot || 0) - Number(v6.balance?.valueBot || 0),
    usedStakeDelta: Number(v61.balance?.usedStake || 0) - Number(v6.balance?.usedStake || 0),
    tradeCountDelta: Number(v61.tradeCount || 0) - Number(v6.tradeCount || 0),
    openTradesDelta: Number(v61.currentOpenTrades || 0) - Number(v6.currentOpenTrades || 0),
    closedTradeCountDelta: Number(v61.closedTradeCount || 0) - Number(v6.closedTradeCount || 0),
  };
}

async function buildSummary() {
  const bots = await loadBots();
  return {
    generatedAt: new Date().toISOString(),
    refreshHintSeconds: REFRESH_HINT_SECONDS,
    history: {
      retentionDays: HISTORY_RETENTION_DAYS,
      sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
      lastSampleAt,
      lastSampleError,
    },
    bots,
    comparison: buildComparison(bots),
  };
}

async function handleApiSummary(res) {
  sendJson(res, 200, await buildSummary());
}

function safeLimit(value, fallback, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, Math.floor(number)));
}

function rowToObject(columns, row) {
  if (!Array.isArray(row)) {
    return row || {};
  }
  return Object.fromEntries(columns.map((column, index) => [column, row[index]]));
}

function candleTime(value) {
  const millis = Date.parse(value);
  if (!Number.isFinite(millis)) {
    return null;
  }
  return Math.floor(millis / 1000);
}

function candlePoint(row) {
  const time = candleTime(row.date);
  if (!time) {
    return null;
  }
  return {
    time,
    date: row.date,
    open: numeric(row.open),
    high: numeric(row.high),
    low: numeric(row.low),
    close: numeric(row.close),
    volume: numeric(row.volume, 0),
    ema21: numeric(row.ema21),
    ema55: numeric(row.ema55),
    ema200: numeric(row.ema200),
    rsi: numeric(row.rsi),
    atr: numeric(row.atr),
    bbUpper: numeric(row.bb_upper),
    bbMiddle: numeric(row.bb_middle),
    bbLower: numeric(row.bb_lower),
    regime4h: row.regime_4h || null,
    enterTag: row.enter_tag || null,
    enterLong: numeric(row.enter_long),
    enterShort: numeric(row.enter_short),
  };
}

function marketMarkers(candles) {
  return candles
    .filter((candle) => candle.enterLong || candle.enterShort)
    .map((candle) => ({
      time: candle.time,
      position: candle.enterShort ? "aboveBar" : "belowBar",
      color: candle.enterShort ? "#ff6b6b" : "#44d07b",
      shape: candle.enterShort ? "arrowDown" : "arrowUp",
      text: formatSignal(candle.enterTag),
    }));
}

function roiForOpenTrade(trade) {
  const openedAt = Number(trade.open_timestamp || 0);
  const elapsedHours = openedAt ? (Date.now() - openedAt) / 3_600_000 : 0;
  if (elapsedHours >= 720) {
    return 0.03;
  }
  if (elapsedHours >= 240) {
    return 0.04;
  }
  return 0.05;
}

function takeProfitTarget(trade, latestCandle) {
  const openRate = numeric(trade.open_rate);
  if (!openRate) {
    return { price: null, reason: null, roi: null };
  }

  const enterTag = trade.enter_tag || "";
  if (enterTag.includes("ranging") && latestCandle) {
    if (trade.is_short) {
      return {
        price: numeric(latestCandle.bbMiddle ?? latestCandle.bbLower),
        reason: "震荡空单目标：布林带中轨/下轨",
        roi: null,
      };
    }
    return {
      price: numeric(latestCandle.bbMiddle ?? latestCandle.bbUpper),
      reason: "震荡多单目标：布林带中轨/上轨",
      roi: null,
    };
  }

  const roi = roiForOpenTrade(trade);
  const leverage = Math.max(1, numeric(trade.leverage, 1));
  const priceMove = roi / leverage;
  return {
    price: trade.is_short ? openRate * (1 - priceMove) : openRate * (1 + priceMove),
    reason: `趋势单 ROI 目标 ${(roi * 100).toFixed(0)}%`,
    roi,
  };
}

async function handleApiMarket(req, res, url) {
  const pair = url.searchParams.get("pair") || DEFAULT_PAIR;
  const timeframe = url.searchParams.get("timeframe") || DEFAULT_TIMEFRAME;
  const limit = safeLimit(url.searchParams.get("limit"), DEFAULT_CANDLE_LIMIT, 24, 1000);
  const bot = BOTS[0];
  const query = new URLSearchParams({ pair, timeframe, limit: String(limit) });
  const [rawCandles, bots] = await Promise.all([
    fetchJson(bot.url, `/api/v1/pair_candles?${query.toString()}`),
    loadBots(),
  ]);

  const columns = rawCandles.columns || [];
  const candles = (rawCandles.data || [])
    .map((row) => candlePoint(rowToObject(columns, row)))
    .filter(Boolean);
  const latestCandle = candles.at(-1) || null;
  const openTrades = bots.flatMap((loadedBot) => (loadedBot.ok ? loadedBot.openTrades.map((trade) => ({
    ...(() => {
      const target = takeProfitTarget(trade, latestCandle);
      return {
        takeProfit: target.price,
        takeProfitReason: target.reason,
        takeProfitRoi: target.roi,
      };
    })(),
    bot: loadedBot.label,
    pair: trade.pair,
    isShort: Boolean(trade.is_short),
    signalText: formatSignal(trade.enter_tag),
    openRate: numeric(trade.open_rate),
    currentRate: numeric(trade.current_rate),
    stopLoss: numeric(trade.stop_loss_abs),
    liquidationPrice: numeric(trade.liquidation_price),
    stakeAmount: numeric(trade.stake_amount),
    profitAbs: numeric(trade.profit_abs ?? trade.total_profit_abs),
    profitPct: numeric(trade.profit_pct),
    fundingFees: numeric(trade.funding_fees, 0),
    openTimestamp: trade.open_timestamp,
    openDate: trade.open_date,
  })) : []));

  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    pair,
    timeframe,
    limit,
    sourceBot: bot.label,
    columns,
    candles,
    markers: marketMarkers(candles),
    openTrades,
    lastAnalyzed: rawCandles.last_analyzed,
  });
}

function ensureHistoryDir() {
  fs.mkdirSync(path.dirname(HISTORY_FILE), { recursive: true });
}

function trimHistory(records, now = Date.now()) {
  const cutoff = now - HISTORY_RETENTION_MS;
  return records.filter((record) => {
    const timestamp = Date.parse(record.generatedAt || record.sampledAt || "");
    return Number.isFinite(timestamp) && timestamp >= cutoff;
  });
}

function readHistory() {
  try {
    if (!fs.existsSync(HISTORY_FILE)) {
      return [];
    }
    const lines = fs.readFileSync(HISTORY_FILE, "utf8")
      .split(/\r?\n/)
      .filter(Boolean);
    const records = [];
    for (const line of lines) {
      try {
        records.push(JSON.parse(line));
      } catch {
        // Ignore corrupt lines and continue with the valid history we still have.
      }
    }
    return trimHistory(records);
  } catch {
    return [];
  }
}

function writeHistory(records) {
  ensureHistoryDir();
  const payload = records.map((record) => JSON.stringify(record)).join("\n");
  const tempFile = `${HISTORY_FILE}.tmp`;
  fs.writeFileSync(tempFile, payload ? `${payload}\n` : "");
  fs.renameSync(tempFile, HISTORY_FILE);
}

function historySnapshot(summary) {
  const sampledAt = new Date().toISOString();
  return {
    generatedAt: summary.generatedAt,
    sampledAt,
    bots: summary.bots.map((bot) => {
      const trade = latestOpenTrade(bot);
      return {
        key: bot.key,
        label: bot.label,
        ok: bot.ok,
        state: bot.state,
        runmode: bot.runmode,
        totalBot: numeric(bot.balance?.totalBot),
        freeStake: numeric(bot.balance?.freeStake),
        usedStake: numeric(bot.balance?.usedStake ?? bot.totalStake),
        profitAllCoin: numeric(bot.profitAllCoin),
        currentDrawdown: numeric(bot.currentDrawdown, 0),
        currentDrawdownAbs: numeric(bot.currentDrawdownAbs, 0),
        currentOpenTrades: numeric(bot.currentOpenTrades, 0),
        closedTradeCount: numeric(bot.closedTradeCount, 0),
        fundingFees: numeric(trade?.funding_fees, 0),
        currentRate: numeric(trade?.current_rate),
        openRate: numeric(trade?.open_rate),
        stopLoss: numeric(trade?.stop_loss_abs),
        liquidationPrice: numeric(trade?.liquidation_price),
      };
    }),
    comparison: summary.comparison,
  };
}

async function sampleHistory() {
  if (sampleInFlight) {
    return;
  }
  sampleInFlight = true;
  try {
    const summary = await buildSummary();
    const snapshot = historySnapshot(summary);
    historyCache = trimHistory([...historyCache, snapshot]);
    writeHistory(historyCache);
    lastSampleAt = snapshot.sampledAt;
    lastSampleError = null;
  } catch (error) {
    lastSampleError = error instanceof Error ? error.message : String(error);
    console.error("history sample failed:", lastSampleError);
  } finally {
    sampleInFlight = false;
  }
}

function historyRangeDays(range) {
  const match = String(range || "").match(/^(\d+)\s*d$/i);
  if (!match) {
    return HISTORY_RETENTION_DAYS;
  }
  return Math.max(1, Math.min(HISTORY_RETENTION_DAYS, Number(match[1])));
}

function historyBotPoint(record, key) {
  const bot = Array.isArray(record.bots) ? record.bots.find((item) => item.key === key) : null;
  return {
    equity: numeric(bot?.totalBot),
    pnl: numeric(bot?.profitAllCoin),
    drawdown: numeric(bot?.currentDrawdown),
    drawdownAbs: numeric(bot?.currentDrawdownAbs),
    funding: numeric(bot?.fundingFees, 0),
    usedStake: numeric(bot?.usedStake),
    openTrades: numeric(bot?.currentOpenTrades, 0),
    currentRate: numeric(bot?.currentRate),
  };
}

function historyPoint(record) {
  const iso = record.sampledAt || record.generatedAt;
  const millis = Date.parse(iso);
  if (!Number.isFinite(millis)) {
    return null;
  }
  return {
    time: Math.floor(millis / 1000),
    iso,
    v6: historyBotPoint(record, "v6"),
    v61: historyBotPoint(record, "v61"),
    comparison: record.comparison || null,
  };
}

function handleApiHistory(res, url) {
  const rangeDays = historyRangeDays(url.searchParams.get("range") || "30d");
  const cutoff = Date.now() - rangeDays * 24 * 60 * 60 * 1000;
  historyCache = trimHistory(historyCache.length ? historyCache : readHistory());
  const points = historyCache
    .filter((record) => Date.parse(record.sampledAt || record.generatedAt || "") >= cutoff)
    .map(historyPoint)
    .filter(Boolean);

  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    rangeDays,
    retentionDays: HISTORY_RETENTION_DAYS,
    sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
    points,
    records: historyCache,
  });
}

function serveStatic(req, res) {
  const requestPath = req.url === "/" ? "/index.html" : decodeURIComponent(req.url);
  const normalized = path.normalize(requestPath).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(PUBLIC_DIR, normalized);

  if (!filePath.startsWith(PUBLIC_DIR)) {
    send(res, 403, "Forbidden\n", { "Content-Type": "text/plain; charset=utf-8" });
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      send(res, 404, "Not found\n", { "Content-Type": "text/plain; charset=utf-8" });
      return;
    }

    const ext = path.extname(filePath);
    send(res, 200, data, {
      "Content-Type": STATIC_TYPES[ext] || "application/octet-stream",
    });
  });
}

const server = http.createServer(async (req, res) => {
  if (!isAuthorized(req)) {
    unauthorized(res);
    return;
  }

  try {
    const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
    if (url.pathname === "/api/summary") {
      await handleApiSummary(res);
      return;
    }
    if (url.pathname === "/api/market") {
      await handleApiMarket(req, res, url);
      return;
    }
    if (url.pathname === "/api/history") {
      handleApiHistory(res, url);
      return;
    }
    serveStatic({ ...req, url: url.pathname }, res);
  } catch (error) {
    sendJson(res, 500, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

if (!DASHBOARD_PASSWORD) {
  console.error("DASHBOARD_PASSWORD is required.");
  process.exit(1);
}

historyCache = readHistory();
sampleHistory();
setInterval(sampleHistory, HISTORY_SAMPLE_MS).unref();

server.listen(PORT, HOST, () => {
  console.log(`freqtrade monitor listening on http://${HOST}:${PORT}`);
});
