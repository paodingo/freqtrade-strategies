"use strict";

function finiteNumber(value) {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function openProfitAbs(bot) {
  if (!Array.isArray(bot?.openTrades)) return null;
  if (bot.openTrades.length === 0) return 0;
  const values = bot.openTrades
    .map((trade) => finiteNumber(trade?.profit_abs ?? trade?.total_profit_abs))
    .filter((value) => value !== null);
  return values.length === bot.openTrades.length
    ? values.reduce((total, value) => total + value, 0)
    : null;
}

function buildPerformanceSnapshot(bot) {
  const currency = typeof bot?.stakeCurrency === "string" && bot.stakeCurrency
    ? bot.stakeCurrency
    : "USDT";
  const unavailable = (reason) => ({
    available: false,
    currency,
    realized_profit_abs: null,
    unrealized_profit_abs: null,
    total_profit_abs: null,
    total_profit_pct: null,
    trade_count: null,
    closed_trade_count: null,
    win_rate: null,
    profit_factor: null,
    current_drawdown_abs: null,
    max_drawdown_abs: null,
    status_reason: reason,
  });

  if (bot?.ok !== true) return unavailable("runtime_source_unavailable");

  const snapshot = {
    available: true,
    currency,
    realized_profit_abs: finiteNumber(bot.profitClosedCoin),
    unrealized_profit_abs: openProfitAbs(bot),
    total_profit_abs: finiteNumber(bot.profitAllCoin),
    total_profit_pct: finiteNumber(bot.profitAllPercent),
    trade_count: finiteNumber(bot.tradeCount),
    closed_trade_count: finiteNumber(bot.closedTradeCount),
    win_rate: finiteNumber(bot.winrate),
    profit_factor: finiteNumber(bot.profitFactor),
    current_drawdown_abs: finiteNumber(bot.currentDrawdownAbs),
    max_drawdown_abs: finiteNumber(bot.maxDrawdownAbs),
    status_reason: null,
  };
  const hasProfitData = snapshot.realized_profit_abs !== null
    || snapshot.unrealized_profit_abs !== null
    || snapshot.total_profit_abs !== null;
  return hasProfitData ? snapshot : unavailable("performance_data_unavailable");
}

module.exports = { buildPerformanceSnapshot, finiteNumber, openProfitAbs };
