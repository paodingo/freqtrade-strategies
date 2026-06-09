"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  buildDashboardInterpretation,
  costPressure,
} = require("../dashboard/lib/interpretation");

function botFixture(overrides = {}) {
  return {
    key: "v63",
    label: "V6.3",
    ok: true,
    tradeCount: 1,
    firstTradeDate: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    profitAllCoin: 10,
    balance: { totalBot: 9900, usedStake: 0 },
    openTrades: [],
    ...overrides,
  };
}

function shortTrade(overrides = {}) {
  return {
    pair: "BTC/USDT:USDT",
    is_short: true,
    stake_amount: 1500,
    open_rate: 62000,
    current_rate: 61000,
    stop_loss_abs: 64000,
    liquidation_price: 76000,
    profit_abs: 20,
    profit_pct: 0.8,
    funding_fees: 2,
    ...overrides,
  };
}

test("dashboard interpretation states 1h main timeframe and 4h filter", () => {
  const result = buildDashboardInterpretation({
    bots: [],
    comparison: null,
    mainTimeframe: "1h",
    informativeTimeframe: "4h",
  });

  assert.equal(result.timeframes.main, "1h");
  assert.equal(result.timeframes.informative, "4h");
  assert.match(result.timeframes.summary, /1h/);
  assert.match(result.timeframes.summary, /4h/);
});

test("comparison interpretation marks challenger as more restrained when it is flat", () => {
  const base = botFixture({
    key: "v62",
    label: "V6.2",
    balance: { totalBot: 9900, usedStake: 1500 },
    openTrades: [shortTrade()],
  });
  const challenger = botFixture({ key: "v63", label: "V6.3" });

  const result = buildDashboardInterpretation({
    bots: [base, challenger],
    comparison: {
      ready: true,
      baseKey: "v62",
      baseLabel: "V6.2",
      challengerKey: "v63",
      challengerLabel: "V6.3",
      profitAllCoinDelta: -10,
      usedStakeDelta: -1500,
      openTradesDelta: -1,
    },
  });

  assert.equal(result.position.title, "V6.2 单边持仓");
  assert.equal(result.comparison.title, "V6.3 更克制");
  assert.equal(result.comparison.level, "good");
  assert.equal(result.position.entries[1].stopDistancePct, null);
  assert.equal(result.position.entries[1].liquidationDistancePct, null);
});

test("cost pressure rises when funding fees consume too much floating pnl", () => {
  const low = costPressure(botFixture({
    openTrades: [shortTrade({ profit_abs: 100, funding_fees: 2 })],
  }));
  const high = costPressure(botFixture({
    openTrades: [shortTrade({ profit_abs: 10, funding_fees: 4 })],
  }));

  assert.equal(low.level, "good");
  assert.equal(high.level, "danger");
  assert.equal(high.title, "成本压力偏高");
});
