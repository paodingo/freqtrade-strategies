#!/usr/bin/env node
"use strict";

const http = require("http");

const { isAuthorized, unauthorized } = require("./lib/auth");
const {
  API_LATENCY_WARN_MS,
  ALPHA_RISK_CACHE_MS,
  ALPHA_RISK_LIMIT,
  ALPHA_RISK_PERIOD,
  ALPHA_RISK_TIMEOUT_MS,
  BOTS,
  DATA_STALE_SECONDS,
  DASHBOARD_PASSWORD,
  DEFAULT_CHART_TIMEFRAME,
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
  STRATEGY_INFORMATIVE_TIMEFRAME,
  STRATEGY_MAIN_TIMEFRAME,
} = require("./lib/config");
const { createBinanceFuturesAlphaFetcher } = require("./lib/binance_futures_alpha");
const { sendJson, serveStatic } = require("./lib/http");
const { buildDashboardInterpretation } = require("./lib/interpretation");
const { safeLimit } = require("./lib/limits");
const { MonitorStore } = require("./lib/monitor_store");
const { classifyRegimeWindow } = require("./lib/regime_router");
const { buildTradeSupervisorDecision } = require("./lib/trade_supervisor");

const monitorStore = new MonitorStore({
  dbFile: HISTORY_DB_FILE,
  retentionDays: HISTORY_RETENTION_DAYS,
});
const fetchAlphaRisk = createBinanceFuturesAlphaFetcher({
  cacheTtlMs: ALPHA_RISK_CACHE_MS,
  period: ALPHA_RISK_PERIOD,
  limit: ALPHA_RISK_LIMIT,
  timeoutMs: ALPHA_RISK_TIMEOUT_MS,
});
let sampleInFlight = false;
let lastSampleAt = null;
let lastSampleError = null;
let regimeRouterCache = {
  value: null,
  expiresAt: 0,
  promise: null,
};
let tradeSupervisorCache = {
  value: null,
  expiresAt: 0,
};

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

function timestampMillis(value, dateValue = null) {
  const number = numeric(value);
  if (number !== null) {
    return number > 10_000_000_000 ? number : number * 1000;
  }
  const parsed = Date.parse(dateValue || "");
  return Number.isFinite(parsed) ? parsed : null;
}

function allowedChartTimeframe(value) {
  const timeframe = String(value || DEFAULT_CHART_TIMEFRAME);
  return new Set(["5m", "15m", "1h", "4h"]).has(timeframe) ? timeframe : DEFAULT_CHART_TIMEFRAME;
}

function signalModeForTimeframe(timeframe, sourceType) {
  if (sourceType === "freqtrade") {
    return "strategy";
  }
  if (new Set(["5m", "15m"]).has(timeframe)) {
    return "auxiliary";
  }
  return "none";
}

function chartSourceBotForTimeframe(timeframe) {
  if (timeframe === "15m") {
    return BOTS.find((bot) => bot.key === "v65") || BOTS[1] || BOTS[0];
  }
  if (timeframe === "1h") {
    return BOTS.find((bot) => bot.key === "v63") || BOTS[0];
  }
  return BOTS[0];
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
    v66_ranging_long_edge: "震荡边缘做多",
    v66_ranging_short_edge: "震荡边缘做空",
    v66_ranging_time_stop: "震荡持仓超时",
    v66_trend_invalidated_by_range: "趋势被震荡破坏",
    v66_ranging_midbox_take_profit: "回到箱体中线止盈",
  }[tag] || tag || "-";
}

function formatExitReason(reason) {
  const raw = String(reason || "").trim();
  if (!raw) {
    return "Freqtrade 未返回退出原因";
  }
  return {
    roi: "达到 ROI / 止盈目标",
    stop_loss: "触发止损",
    trailing_stop_loss: "触发移动止损",
    exit_signal: "策略退出信号",
    force_exit: "手动或强制平仓",
    force_sell: "手动或强制平仓",
    emergency_exit: "紧急退出",
    liquidation: "强平",
    v65_ranging_time_stop: "V6.5 震荡单持仓超时",
    v65_reverse_long_signal_exit: "出现反向做多强信号，先平空单",
    v65_reverse_short_signal_exit: "出现反向做空强信号，先平多单",
    v66_trend_invalidated_by_range: "趋势被震荡行情破坏，退出趋势单",
    v66_ranging_midbox_take_profit: "震荡单回到箱体中线，先兑现利润",
    v661_short_bounce_exit: "空单遇到快速反弹，先退出",
  }[raw] || raw.replaceAll("_", " ");
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
      ? (trade.is_short ? "当前做空" : "当前做多")
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
      mainTimeframe: STRATEGY_MAIN_TIMEFRAME,
      informativeTimeframe: STRATEGY_INFORMATIVE_TIMEFRAME,
    }),
    chart: {
      defaultTimeframe: DEFAULT_CHART_TIMEFRAME,
      allowedTimeframes: ["5m", "15m", "1h", "4h"],
    },
  };
}

async function handleApiSummary(res) {
  sendJson(res, 200, await buildSummary());
}

async function handleApiAlphaRisk(res) {
  sendJson(res, 200, await fetchAlphaRisk({ pair: DEFAULT_PAIR }));
}

async function buildRegimeRouterSnapshot(alphaRisk = null) {
  const results = await Promise.allSettled([
    fetchBinanceFuturesCandles(DEFAULT_PAIR, "15m", 500),
    fetchBinanceFuturesCandles(DEFAULT_PAIR, "4h", 300),
  ]);
  const candles15m = results[0].status === "fulfilled" ? results[0].value : [];
  const candles4h = results[1].status === "fulfilled" ? results[1].value : [];
  const errors = results
    .filter((result) => result.status === "rejected")
    .map((result) => (result.reason instanceof Error ? result.reason.message : String(result.reason)));
  const snapshot = classifyRegimeWindow({
    pair: DEFAULT_PAIR,
    candles15m,
    candles4h,
    alphaRisk,
  });
  return {
    ...snapshot,
    status: errors.length ? (candles15m.length || candles4h.length ? "partial" : "error") : "ok",
    errors,
    sources: {
      candles15m: candles15m.length ? "Binance Futures" : null,
      candles4h: candles4h.length ? "Binance Futures" : null,
      alphaRisk: alphaRisk?.status || null,
    },
  };
}

async function getRegimeRouterSnapshot(alphaRisk = null, { force = false } = {}) {
  const now = Date.now();
  if (!force && regimeRouterCache.value && regimeRouterCache.expiresAt > now) {
    return regimeRouterCache.value;
  }
  if (!force && regimeRouterCache.promise) {
    return regimeRouterCache.promise;
  }

  const promise = buildRegimeRouterSnapshot(alphaRisk)
    .then((snapshot) => {
      regimeRouterCache = {
        value: snapshot,
        expiresAt: Date.now() + HISTORY_SAMPLE_MS,
        promise: null,
      };
      return snapshot;
    })
    .catch((error) => {
      regimeRouterCache.promise = null;
      throw error;
    });

  if (force) {
    return promise;
  }
  regimeRouterCache.promise = promise;
  return promise;
}

async function handleApiRegimeRouter(res) {
  if (regimeRouterCache.value && regimeRouterCache.expiresAt > Date.now()) {
    sendJson(res, 200, regimeRouterCache.value);
    return;
  }
  let alphaRisk = null;
  let alphaError = null;
  try {
    alphaRisk = await fetchAlphaRisk({ pair: DEFAULT_PAIR });
  } catch (error) {
    alphaError = error instanceof Error ? error.message : String(error);
  }
  const snapshot = await getRegimeRouterSnapshot(alphaRisk);
  sendJson(res, 200, {
    ...snapshot,
    status: alphaError ? (snapshot.status === "ok" ? "partial" : snapshot.status) : snapshot.status,
    errors: alphaError ? [...(snapshot.errors || []), alphaError] : snapshot.errors,
  });
}

async function buildTradeSupervisorSnapshot({ summary = null, regimeRouter = null } = {}) {
  const resolvedSummary = summary || monitorStore.readLatestHistory() || await buildSummary();
  const resolvedRegimeRouter = regimeRouter || await getRegimeRouterSnapshot(null);
  const decision = buildTradeSupervisorDecision({
    regimeRouter: resolvedRegimeRouter,
    bots: resolvedSummary.bots || [],
  });
  return {
    ...decision,
    regimeRouter: resolvedRegimeRouter,
  };
}

async function handleApiTradeSupervisor(res) {
  if (tradeSupervisorCache.value && tradeSupervisorCache.expiresAt > Date.now()) {
    sendJson(res, 200, tradeSupervisorCache.value);
    return;
  }
  const decision = await buildTradeSupervisorSnapshot();
  tradeSupervisorCache = {
    value: decision,
    expiresAt: Date.now() + HISTORY_SAMPLE_MS,
  };
  sendJson(res, 200, decision);
}

function alphaRiskPoint(record) {
  const iso = record.sampledAt || record.generatedAt;
  const millis = Date.parse(iso || "");
  if (!Number.isFinite(millis)) {
    return null;
  }
  return {
    time: Math.floor(millis / 1000),
    iso,
    symbol: record.symbol,
    period: record.period,
    status: record.status,
    riskLevel: record.risk?.level || null,
    riskScore: numeric(record.risk?.score),
    fundingRatePct: numeric(record.metrics?.funding?.ratePct),
    openInterestChangePct: numeric(record.metrics?.openInterest?.changePct),
    globalLongShortRatio: numeric(record.metrics?.globalLongShort?.ratio),
    topTraderPositionRatio: numeric(record.metrics?.topTraderPosition?.ratio),
    topTraderAccountRatio: numeric(record.metrics?.topTraderAccount?.ratio),
    takerBuySellRatio: numeric(record.metrics?.takerFlow?.buySellRatio),
    premiumPct: numeric(record.metrics?.premium?.premiumPct),
  };
}

function handleApiAlphaRiskHistory(res, url) {
  const rangeDays = historyRangeDays(url.searchParams.get("range") || "30d");
  const limit = safeLimit(url.searchParams.get("limit"), 1000, 1, 5000);
  const cutoff = Date.now() - rangeDays * 24 * 60 * 60 * 1000;
  const records = monitorStore.readAlphaRiskSamples({ limit });
  const filtered = records.filter((record) => Date.parse(record.sampledAt || record.generatedAt || "") >= cutoff);
  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    rangeDays,
    retentionDays: HISTORY_RETENTION_DAYS,
    sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
    points: filtered.map(alphaRiskPoint).filter(Boolean),
    records: filtered,
  });
}

function regimeRouterPoint(record) {
  const iso = record.sampledAt || record.generatedAt;
  const millis = Date.parse(iso || "");
  if (!Number.isFinite(millis)) {
    return null;
  }
  return {
    time: Math.floor(millis / 1000),
    iso,
    pair: record.pair,
    windowType: record.windowType,
    confidence: numeric(record.confidence),
    allowedPlaybook: record.allowedPlaybook,
    riskBudgetPct: numeric(record.riskBudgetPct),
    directionBias: record.directionBias,
    return24hPct: numeric(record.metrics?.return24hPct),
    return7dPct: numeric(record.metrics?.return7dPct),
    range24hPct: numeric(record.metrics?.range24hPct),
    alphaLevel: record.metrics?.alphaLevel || null,
    takerBuySellRatio: numeric(record.metrics?.takerBuySellRatio),
  };
}

function handleApiRegimeRouterHistory(res, url) {
  const rangeDays = historyRangeDays(url.searchParams.get("range") || "30d");
  const limit = safeLimit(url.searchParams.get("limit"), 1000, 1, 5000);
  const cutoff = Date.now() - rangeDays * 24 * 60 * 60 * 1000;
  const records = monitorStore.readRegimeRouterSamples({ limit });
  const filtered = records.filter((record) => Date.parse(record.sampledAt || record.generatedAt || "") >= cutoff);
  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    rangeDays,
    retentionDays: HISTORY_RETENTION_DAYS,
    sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
    points: filtered.map(regimeRouterPoint).filter(Boolean),
    records: filtered,
  });
}

function tradeSupervisorPoint(record) {
  const iso = record.sampledAt || record.generatedAt;
  const millis = Date.parse(iso || "");
  if (!Number.isFinite(millis)) {
    return null;
  }
  return {
    time: Math.floor(millis / 1000),
    iso,
    mode: record.mode,
    systemAction: record.systemAction,
    windowType: record.windowType,
    allowedPlaybook: record.allowedPlaybook,
    riskBudgetPct: numeric(record.riskBudgetPct),
    maxNewStakePct: numeric(record.maxNewStakePct),
    v65Action: record.actions?.v65?.recommendedAction || null,
    v66Action: record.actions?.v66?.recommendedAction || null,
    v66AllowFreshEntries: record.actions?.v66?.allowFreshEntries ?? null,
  };
}

function handleApiTradeSupervisorHistory(res, url) {
  const rangeDays = historyRangeDays(url.searchParams.get("range") || "30d");
  const limit = safeLimit(url.searchParams.get("limit"), 1000, 1, 5000);
  const cutoff = Date.now() - rangeDays * 24 * 60 * 60 * 1000;
  const records = monitorStore.readTradeSupervisorDecisions({ limit });
  const filtered = records.filter((record) => Date.parse(record.sampledAt || record.generatedAt || "") >= cutoff);
  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    rangeDays,
    retentionDays: HISTORY_RETENTION_DAYS,
    sampleIntervalSeconds: HISTORY_SAMPLE_SECONDS,
    points: filtered.map(tradeSupervisorPoint).filter(Boolean),
    records: filtered,
  });
}

function normalizeClosedTrade(bot, trade) {
  const closeTimestamp = timestampMillis(trade.close_timestamp, trade.close_date);
  if (trade.is_open || !closeTimestamp) {
    return null;
  }
  const profitRatio = numeric(trade.realized_profit_ratio ?? trade.close_profit ?? trade.profit_ratio);
  return {
    botKey: bot.key,
    botLabel: bot.label,
    tradeId: trade.trade_id ?? trade.id ?? null,
    pair: trade.pair || DEFAULT_PAIR,
    isOpen: Boolean(trade.is_open),
    isShort: Boolean(trade.is_short),
    enterTag: trade.enter_tag || null,
    signalText: formatSignal(trade.enter_tag),
    exitReason: trade.exit_reason || trade.sell_reason || trade.close_reason || null,
    exitReasonText: formatExitReason(trade.exit_reason || trade.sell_reason || trade.close_reason),
    openRate: numeric(trade.open_rate),
    closeRate: numeric(trade.close_rate),
    realizedProfit: numeric(trade.realized_profit ?? trade.close_profit_abs ?? trade.profit_abs, 0),
    realizedProfitRatio: profitRatio === null ? null : profitRatio * 100,
    stakeAmount: numeric(trade.stake_amount),
    feeOpenCost: numeric(trade.fee_open_cost, 0),
    feeCloseCost: numeric(trade.fee_close_cost, 0),
    openTimestamp: timestampMillis(trade.open_timestamp, trade.open_date),
    closeTimestamp,
    openDate: trade.open_date || null,
    closeDate: trade.close_date || null,
  };
}

async function loadBotTrades(bot, limit) {
  try {
    const query = new URLSearchParams({ limit: String(limit), offset: "0" });
    const raw = await fetchJson(bot.url, `/api/v1/trades?${query.toString()}`);
    const sourceTrades = Array.isArray(raw) ? raw : raw.trades || [];
    return {
      key: bot.key,
      label: bot.label,
      ok: true,
      trades: sourceTrades.map((trade) => normalizeClosedTrade(bot, trade)).filter(Boolean),
      error: null,
    };
  } catch (error) {
    return {
      key: bot.key,
      label: bot.label,
      ok: false,
      trades: [],
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function handleApiTrades(res, url) {
  const limit = safeLimit(url.searchParams.get("limit"), 200, 1, 500);
  const bots = await Promise.all(BOTS.map((bot) => loadBotTrades(bot, limit)));
  const trades = bots
    .flatMap((bot) => bot.trades)
    .sort((left, right) => left.closeTimestamp - right.closeTimestamp);

  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    limit,
    bots,
    trades,
  });
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

function pairToBinanceSymbol(pair) {
  return String(pair || "")
    .split(":")[0]
    .replace("/", "")
    .toUpperCase();
}

function applyEma(candles, period, field) {
  const multiplier = 2 / (period + 1);
  let ema = null;
  for (const candle of candles) {
    if (!Number.isFinite(candle.close)) {
      continue;
    }
    ema = ema === null ? candle.close : (candle.close - ema) * multiplier + ema;
    candle[field] = ema;
  }
}

function applyAuxiliarySignals(candles, timeframe) {
  if (!new Set(["5m", "15m"]).has(timeframe)) {
    return;
  }

  for (let index = 1; index < candles.length; index += 1) {
    const previous = candles[index - 1];
    const candle = candles[index];
    const longTrend = candle.ema21 > candle.ema55 && candle.ema55 > candle.ema200 && candle.close > candle.ema200;
    const shortTrend = candle.ema21 < candle.ema55 && candle.ema55 < candle.ema200 && candle.close < candle.ema200;
    const regainedEma21 = previous.close <= previous.ema21 && candle.close > candle.ema21;
    const lostEma21 = previous.close >= previous.ema21 && candle.close < candle.ema21;

    if (longTrend && regainedEma21) {
      candle.enterLong = 1;
      candle.enterTag = "aux_long";
    } else if (shortTrend && lostEma21) {
      candle.enterShort = 1;
      candle.enterTag = "aux_short";
    }
  }
}

async function fetchBinanceFuturesCandles(pair, timeframe, limit) {
  const symbol = pairToBinanceSymbol(pair);
  if (!symbol) {
    return [];
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const query = new URLSearchParams({
      symbol,
      interval: timeframe,
      limit: String(limit),
    });
    const response = await fetch(`https://fapi.binance.com/fapi/v1/klines?${query.toString()}`, {
      signal: controller.signal,
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 120)}`);
    }
    const candles = JSON.parse(text).map((row) => ({
      time: Math.floor(Number(row[0]) / 1000),
      date: new Date(Number(row[0])).toISOString(),
      open: numeric(row[1]),
      high: numeric(row[2]),
      low: numeric(row[3]),
      close: numeric(row[4]),
      volume: numeric(row[5], 0),
      ema21: null,
      ema55: null,
      ema200: null,
      rsi: null,
      atr: null,
      bbUpper: null,
      bbMiddle: null,
      bbLower: null,
      regime4h: null,
      enterTag: null,
      enterLong: null,
      enterShort: null,
    })).filter((candle) => candle.time && Number.isFinite(candle.close));
    applyEma(candles, 21, "ema21");
    applyEma(candles, 55, "ema55");
    applyEma(candles, 200, "ema200");
    applyAuxiliarySignals(candles, timeframe);
    return candles;
  } finally {
    clearTimeout(timer);
  }
}

async function fetchBinanceFuturesTicker(pair) {
  const symbol = pairToBinanceSymbol(pair);
  if (!symbol) {
    return null;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const query = new URLSearchParams({ symbol });
    const response = await fetch(`https://fapi.binance.com/fapi/v1/ticker/price?${query.toString()}`, {
      signal: controller.signal,
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 120)}`);
    }

    const payload = JSON.parse(text);
    const price = numeric(payload.price);
    if (price === null) {
      return null;
    }

    return {
      symbol: payload.symbol || symbol,
      price,
      updatedAt: numeric(payload.time) ? new Date(Number(payload.time)).toISOString() : new Date().toISOString(),
      source: "Binance Futures",
    };
  } finally {
    clearTimeout(timer);
  }
}

async function loadMarketCandles(bot, pair, timeframe, limit) {
  const query = new URLSearchParams({ pair, timeframe, limit: String(limit) });
  const rawCandles = await fetchJson(bot.url, `/api/v1/pair_candles?${query.toString()}`);
  const columns = rawCandles.columns || [];
  const candles = (rawCandles.data || [])
    .map((row) => candlePoint(rowToObject(columns, row)))
    .filter(Boolean);
  if (candles.length > 0) {
    return {
      columns,
      candles,
      lastAnalyzed: rawCandles.last_analyzed || candles.at(-1)?.date || null,
      source: bot.label,
      sourceType: "freqtrade",
      fallback: false,
    };
  }

  const fallbackCandles = await fetchBinanceFuturesCandles(pair, timeframe, limit);
  return {
    columns: ["date", "open", "high", "low", "close", "volume", "ema21", "ema55", "ema200"],
    candles: fallbackCandles,
    lastAnalyzed: fallbackCandles.at(-1)?.date || rawCandles.last_analyzed || null,
    source: fallbackCandles.length ? "Binance Futures" : bot.label,
    sourceType: fallbackCandles.length ? "binance_futures" : "freqtrade",
    fallback: fallbackCandles.length > 0,
  };
}

function marketMarkers(candles, mode = "strategy") {
  return candles
    .filter((candle) => candle.enterLong || candle.enterShort)
    .map((candle) => ({
      kind: mode,
      time: candle.time,
      position: candle.enterShort ? "aboveBar" : "belowBar",
      color: mode === "auxiliary"
        ? (candle.enterShort ? "#f4c35d" : "#55c8e8")
        : (candle.enterShort ? "#ff6b6b" : "#44d07b"),
      shape: candle.enterShort ? "arrowDown" : "arrowUp",
      text: candle.enterTag === "aux_long"
        ? "辅助买入观察"
        : candle.enterTag === "aux_short"
          ? "辅助卖出观察"
          : formatSignal(candle.enterTag),
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
  const timeframe = allowedChartTimeframe(url.searchParams.get("timeframe") || DEFAULT_CHART_TIMEFRAME);
  const limit = safeLimit(url.searchParams.get("limit"), DEFAULT_CANDLE_LIMIT, 24, 1000);
  const bot = chartSourceBotForTimeframe(timeframe);
  const [marketCandles, bots, tickerPrice] = await Promise.all([
    loadMarketCandles(bot, pair, timeframe, limit),
    loadBots(),
    fetchBinanceFuturesTicker(pair).catch(() => null),
  ]);

  const columns = marketCandles.columns;
  const candles = marketCandles.candles;
  const signalMode = signalModeForTimeframe(timeframe, marketCandles.sourceType);
  const markers = signalMode === "none" ? [] : marketMarkers(candles, signalMode);
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
  const lastAnalyzed = marketCandles.lastAnalyzed || latestCandle?.date || null;
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
    sourceBot: marketCandles.source,
    sourceType: marketCandles.sourceType,
    fallback: marketCandles.fallback,
    signalMode,
    signalInfo: {
      mode: signalMode,
      available: signalMode !== "none",
      source: signalMode === "strategy" ? "freqtrade_strategy" : signalMode === "auxiliary" ? "dashboard_auxiliary" : "none",
      message: signalMode === "strategy"
        ? `${timeframe} 当前显示 ${marketCandles.source} 的 Freqtrade 真实策略信号。`
        : signalMode === "auxiliary"
          ? "当前周期显示面板辅助观察信号，不等于 bot 会直接下单。"
          : "当前周期不显示入场信号。",
    },
    columns,
    candles,
    markers,
    openTrades,
    ticker: tickerPrice,
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
    const [summary, alphaRisk] = await Promise.all([
      buildSummary(),
      fetchAlphaRisk({ pair: DEFAULT_PAIR }),
    ]);
    const previousSnapshot = monitorStore.readLatestHistory();
    const snapshot = monitorStore.historySnapshot(summary);
    monitorStore.appendHistorySnapshot(snapshot);
    monitorStore.recordAlphaRiskSample({
      ...alphaRisk,
      sampledAt: snapshot.sampledAt,
    });
    try {
      const regimeRouter = await getRegimeRouterSnapshot(alphaRisk, { force: true });
      monitorStore.recordRegimeRouterSample({
        ...regimeRouter,
        sampledAt: snapshot.sampledAt,
      });
      const supervisorDecision = await buildTradeSupervisorSnapshot({ summary, regimeRouter });
      monitorStore.recordTradeSupervisorDecision({
        ...supervisorDecision,
        sampledAt: snapshot.sampledAt,
      });
      tradeSupervisorCache = {
        value: supervisorDecision,
        expiresAt: Date.now() + HISTORY_SAMPLE_MS,
      };
    } catch (error) {
      monitorStore.recordAlert({
        timestamp: snapshot.sampledAt,
        severity: "warning",
        botKey: "monitor",
        label: "Regime Router",
        message: "Regime router sample failed",
        payload: {
          error: error instanceof Error ? error.message : String(error),
        },
      });
    }
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
    if (url.pathname === "/api/alpha-risk/history") {
      handleApiAlphaRiskHistory(res, url);
      return;
    }
    if (url.pathname === "/api/alpha-risk") {
      await handleApiAlphaRisk(res);
      return;
    }
    if (url.pathname === "/api/regime-router/history") {
      handleApiRegimeRouterHistory(res, url);
      return;
    }
    if (url.pathname === "/api/regime-router") {
      await handleApiRegimeRouter(res);
      return;
    }
    if (url.pathname === "/api/trade-supervisor/history") {
      handleApiTradeSupervisorHistory(res, url);
      return;
    }
    if (url.pathname === "/api/trade-supervisor") {
      await handleApiTradeSupervisor(res);
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
    if (url.pathname === "/api/trades") {
      await handleApiTrades(res, url);
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
