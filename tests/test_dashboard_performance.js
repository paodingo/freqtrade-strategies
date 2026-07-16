"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { buildPerformanceSnapshot } = require("../dashboard/lib/performance");

test("performance snapshot exposes simulated realized and unrealized profit", () => {
  const snapshot = buildPerformanceSnapshot({
    ok: true,
    stakeCurrency: "USDT",
    profitClosedCoin: 18.25,
    profitAllCoin: 21.75,
    profitAllPercent: 2.175,
    tradeCount: 9,
    closedTradeCount: 7,
    winrate: 0.625,
    profitFactor: 1.4,
    currentDrawdownAbs: 2.5,
    maxDrawdownAbs: 8.75,
    openTrades: [{ profit_abs: 2.5 }, { total_profit_abs: 1 }],
  });

  assert.equal(snapshot.available, true);
  assert.equal(snapshot.realized_profit_abs, 18.25);
  assert.equal(snapshot.unrealized_profit_abs, 3.5);
  assert.equal(snapshot.total_profit_abs, 21.75);
  assert.equal(snapshot.total_profit_pct, 2.175);
  assert.equal(snapshot.trade_count, 9);
  assert.equal(snapshot.win_rate, 0.625);
  assert.equal(snapshot.profit_factor, 1.4);
  assert.equal(snapshot.max_drawdown_abs, 8.75);
});

test("performance snapshot never turns unavailable runtime into zero profit", () => {
  assert.deepEqual(buildPerformanceSnapshot({ ok: false, stakeCurrency: "USDT" }), {
    available: false,
    currency: "USDT",
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
    status_reason: "runtime_source_unavailable",
  });
});

test("performance snapshot reports incomplete open-trade values as unavailable", () => {
  const snapshot = buildPerformanceSnapshot({
    ok: true,
    profitAllCoin: 2,
    openTrades: [{ profit_abs: 1 }, {}],
  });
  assert.equal(snapshot.available, true);
  assert.equal(snapshot.unrealized_profit_abs, null);
  assert.equal(snapshot.total_profit_abs, 2);
});
