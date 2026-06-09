#!/usr/bin/env node
"use strict";

const http = require("http");

const { isAuthorized, unauthorized } = require("./lib/auth");
const {
  API_LATENCY_WARN_MS,
  BOTS,
  DATA_STALE_SECONDS,
  DASHBOARD_PASSWORD,
  DEFAULT_CANDLE_LIMIT,
  DEFAULT_PAIR,
  DEFAULT_TIMEFRAME,
  FREQTRADE_AUTH,
  HISTORY_DB_FILE,
  HISTORY_RETENTION_DAYS,
  HISTORY_SAMPLE_MS,
  HISTORY_SAMPLE_SECONDS,
  HOST,
  PORT,
  REFRESH_HINT_SECONDS,
} = require("./lib/config");
const { sendJson, serveStatic } = require("./lib/http");
const { buildDashboardInterpretation } = require("./lib/interpretation");
const { MonitorStore } = require("./lib/monitor_store");

const monitorStore = new MonitorStore({
  dbFile: HISTORY_DB_FILE,
  retentionDays: HISTORY_RETENTION_DAYS,
});
let sampleInFlight = false;
let lastSampleAt = null;
let lastSampleError = null;

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
  const baseConfig = BOTS[0];
  const challengerConfig = BOTS[1];
  const base = results.find((bot) => bot.key === baseConfig?.key);
  const challenger = results.find((bot) => bot.key === challengerConfig?.key);
  const meta = {
    baseKey: baseConfig?.key || "base",
    baseLabel: base?.label || baseConfig?.label || "基线",
    challengerKey: challengerConfig?.key || "challenger",
    challengerLabel: challenger?.label || challengerConfig?.label || "对照",
  };
  if (!base?.ok || !challenger?.ok) {
    return { ...meta, ready: false };
  }
  return {
    ...meta,
    ready: true,
    profitAllCoinDelta: Number(challenger.profitAllCoin || 0) - Number(base.profitAllCoin || 0),
    totalBotDelta: Number(challenger.balance?.totalBot || 0) - Number(base.balance?.totalBot || 0),
    valueBotDelta: Number(challenger.balance?.valueBot || 0) - Number(base.balance?.valueBot || 0),
    usedStakeDelta: Number(challenger.balance?.usedStake || 0) - Number(base.balance?.usedStake || 0),
    tradeCountDelta: Number(challenger.tradeCount || 0) - Number(base.tradeCount || 0),
    openTradesDelta: Number(challenger.currentOpenTrades || 0) - Number(base.currentOpenTrades || 0),
    closedTradeCountDelta: Number(challenger.closedTradeCount || 0) - Number(base.closedTradeCount || 0),
  };
}

async function buildSummary() {
  const bots = await loadBots();
  const comparison = buildComparison(bots);
  return {
    generatedAt: new Date().toISOString(),
    refreshHintSeconds: REFRESH_HINT_SECONDS,
    history: {
      storage: "sqlite",
      retentionDays: HISTORY_RETENTION_DAYS,
      sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
      lastSampleAt,
      lastSampleError,
    },
    bots,
    comparison,
    interpretation: buildDashboardInterpretation({
      bots,
      comparison,
      mainTimeframe: DEFAULT_TIMEFRAME,
      informativeTimeframe: "4h",
    }),
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
  const generatedAt = new Date().toISOString();
  const lastAnalyzed = rawCandles.last_analyzed || latestCandle?.date || null;
  const lastAnalyzedMs = Date.parse(lastAnalyzed || "");
  const ageSeconds = Number.isFinite(lastAnalyzedMs)
    ? Math.max(0, Math.round((Date.now() - lastAnalyzedMs) / 1000))
    : null;
  const freshnessIsStale = ageSeconds !== null && ageSeconds > DATA_STALE_SECONDS;
  monitorStore.recordDataFreshness({
    timestamp: generatedAt,
    source: bot.label,
    pair,
    timeframe,
    lastAnalyzed,
    ageSeconds,
    severity: freshnessIsStale ? "warning" : "info",
    message: freshnessIsStale ? "Market data is stale" : "Market data freshness sampled",
  });
  if (freshnessIsStale) {
    monitorStore.recordAlert({
      timestamp: generatedAt,
      severity: "warning",
      botKey: bot.key,
      label: bot.label,
      message: "Market data is stale",
      payload: { pair, timeframe, lastAnalyzed, ageSeconds, staleSeconds: DATA_STALE_SECONDS },
    });
  }

  sendJson(res, 200, {
    generatedAt,
    pair,
    timeframe,
    limit,
    sourceBot: bot.label,
    columns,
    candles,
    markers: marketMarkers(candles),
    openTrades,
    lastAnalyzed,
    dataFreshness: {
      ageSeconds,
      staleSeconds: DATA_STALE_SECONDS,
      stale: freshnessIsStale,
    },
  });
}

function tradeEventKey(bot, trade) {
  const id = trade.tradeId ?? trade.openTimestamp ?? trade.openDate ?? trade.pair;
  return `${bot.key}:${trade.pair}:${id}`;
}

function openTradeMap(snapshot) {
  const entries = new Map();
  for (const bot of snapshot?.bots || []) {
    for (const trade of bot.openTrades || []) {
      entries.set(tradeEventKey(bot, trade), { bot, trade });
    }
  }
  return entries;
}

function recordSnapshotEvents(snapshot, previousSnapshot) {
  const timestamp = snapshot.sampledAt;
  const previousBots = new Map((previousSnapshot?.bots || []).map((bot) => [bot.key, bot]));

  for (const bot of snapshot.bots || []) {
    const previousBot = previousBots.get(bot.key);
    monitorStore.recordApiLatency({
      timestamp,
      botKey: bot.key,
      label: bot.label,
      ok: bot.ok,
      latencyMs: bot.latencyMs,
      error: bot.error,
    });

    if (!bot.ok) {
      monitorStore.recordAlert({
        timestamp,
        severity: "error",
        botKey: bot.key,
        label: bot.label,
        message: "Freqtrade API unavailable",
        payload: { error: bot.error },
      });
    } else if (previousBot && previousBot.ok === false) {
      monitorStore.recordAlert({
        timestamp,
        severity: "info",
        botKey: bot.key,
        label: bot.label,
        message: "Freqtrade API recovered",
        payload: { latencyMs: bot.latencyMs },
      });
    } else if (numeric(bot.latencyMs, 0) > API_LATENCY_WARN_MS) {
      monitorStore.recordAlert({
        timestamp,
        severity: "warning",
        botKey: bot.key,
        label: bot.label,
        message: "Freqtrade API latency is high",
        payload: { latencyMs: bot.latencyMs, warnMs: API_LATENCY_WARN_MS },
      });
    }
  }

  const previousTrades = openTradeMap(previousSnapshot);
  const currentTrades = openTradeMap(snapshot);
  for (const [key, current] of currentTrades.entries()) {
    const previous = previousTrades.get(key);
    if (!previous) {
      monitorStore.recordTradeEvent({
        timestamp,
        botKey: current.bot.key,
        label: current.bot.label,
        message: `Open trade detected for ${current.trade.pair}`,
        payload: { action: "open", trade: current.trade },
      });
      continue;
    }

    const oldStake = numeric(previous.trade.stakeAmount, 0);
    const newStake = numeric(current.trade.stakeAmount, 0);
    if (Math.abs(newStake - oldStake) > 0.000001) {
      monitorStore.recordTradeEvent({
        timestamp,
        botKey: current.bot.key,
        label: current.bot.label,
        message: `Trade stake changed for ${current.trade.pair}`,
        payload: {
          action: "stake_changed",
          previousStake: oldStake,
          currentStake: newStake,
          trade: current.trade,
        },
      });
    }
  }

  for (const [key, previous] of previousTrades.entries()) {
    if (currentTrades.has(key)) {
      continue;
    }
    monitorStore.recordTradeEvent({
      timestamp,
      botKey: previous.bot.key,
      label: previous.bot.label,
      message: `Open trade disappeared for ${previous.trade.pair}`,
      payload: { action: "closed_or_missing", trade: previous.trade },
    });
  }
}

async function sampleHistory() {
  if (sampleInFlight) {
    return;
  }
  sampleInFlight = true;
  try {
    const summary = await buildSummary();
    const previousSnapshot = monitorStore.readLatestHistory();
    const snapshot = monitorStore.historySnapshot(summary);
    monitorStore.appendHistorySnapshot(snapshot);
    recordSnapshotEvents(snapshot, previousSnapshot);
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
    fundingFees: numeric(bot?.fundingFees, 0),
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
    base: historyBotPoint(record, BOTS[0]?.key),
    challenger: historyBotPoint(record, BOTS[1]?.key),
    comparison: record.comparison || null,
  };
}

function handleApiHistory(res, url) {
  const rangeDays = historyRangeDays(url.searchParams.get("range") || "30d");
  const cutoff = Date.now() - rangeDays * 24 * 60 * 60 * 1000;
  const records = monitorStore.readHistory();
  const points = records
    .filter((record) => Date.parse(record.sampledAt || record.generatedAt || "") >= cutoff)
    .map(historyPoint)
    .filter(Boolean);

  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    rangeDays,
    retentionDays: HISTORY_RETENTION_DAYS,
    sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
    points,
    records,
  });
}

function handleApiEvents(res, url) {
  const limit = safeLimit(url.searchParams.get("limit"), 100, 1, 500);
  const type = url.searchParams.get("type") || null;
  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    events: monitorStore.readEvents({ limit, type }),
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
    if (url.pathname === "/api/events") {
      handleApiEvents(res, url);
      return;
    }
    serveStatic(url.pathname, res);
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

sampleHistory();
setInterval(sampleHistory, HISTORY_SAMPLE_MS).unref();

server.listen(PORT, HOST, () => {
  console.log(`freqtrade monitor listening on http://${HOST}:${PORT}`);
});

function shutdown() {
  monitorStore.close();
  process.exit(0);
}

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
