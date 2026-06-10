"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { classifyRegimeWindow } = require("../dashboard/lib/regime_router");

function candlesFromPrices(prices, startMs = Date.parse("2026-06-01T00:00:00.000Z"), stepMs = 15 * 60 * 1000) {
  return prices.map((close, index) => ({
    time: Math.floor((startMs + index * stepMs) / 1000),
    date: new Date(startMs + index * stepMs).toISOString(),
    open: index === 0 ? close : prices[index - 1],
    high: close * 1.003,
    low: close * 0.997,
    close,
    volume: 100,
  }));
}

function trendPrices({ start, step, count }) {
  return Array.from({ length: count }, (_, index) => start + step * index);
}

test("classifies a falling market with crowded longs as downtrend short playbook", () => {
  const candles15m = candlesFromPrices(trendPrices({ start: 82000, step: -38, count: 500 }));
  const candles4h = candlesFromPrices(
    trendPrices({ start: 83000, step: -180, count: 220 }),
    Date.parse("2026-05-01T00:00:00.000Z"),
    4 * 60 * 60 * 1000,
  );
  const snapshot = classifyRegimeWindow({
    pair: "BTC/USDT:USDT",
    candles15m,
    candles4h,
    alphaRisk: {
      risk: {
        level: "warning",
        flags: [
          { key: "longCrowding" },
          { key: "takerSellPressure" },
        ],
      },
      metrics: {
        takerFlow: { buySellRatio: 0.74 },
        globalLongShort: { ratio: 2.1 },
      },
    },
  });

  assert.equal(snapshot.windowType, "downtrend");
  assert.equal(snapshot.allowedPlaybook, "trend_short");
  assert.equal(snapshot.policy.allowTrendShort, true);
  assert.equal(snapshot.policy.allowRangeLong, false);
  assert.equal(snapshot.riskBudgetPct, 50);
  assert.ok(snapshot.confidence >= 70);
  assert.ok(snapshot.reasons.some((reason) => reason.key === "alpha_sell_pressure"));
});

test("classifies a low-volatility sideways market as range edge playbook", () => {
  const prices = Array.from({ length: 500 }, (_, index) => 70000 + Math.sin(index / 12) * 450);
  const candles15m = candlesFromPrices(prices);
  const candles4h = candlesFromPrices(
    Array.from({ length: 220 }, (_, index) => 70000 + Math.sin(index / 5) * 600),
    Date.parse("2026-05-01T00:00:00.000Z"),
    4 * 60 * 60 * 1000,
  );
  const snapshot = classifyRegimeWindow({
    pair: "BTC/USDT:USDT",
    candles15m,
    candles4h,
    alphaRisk: {
      risk: { level: "neutral", flags: [] },
      metrics: { takerFlow: { buySellRatio: 1.02 }, globalLongShort: { ratio: 1.02 } },
    },
  });

  assert.equal(snapshot.windowType, "range");
  assert.equal(snapshot.allowedPlaybook, "range_edge");
  assert.equal(snapshot.policy.allowRangeLong, true);
  assert.equal(snapshot.policy.allowRangeShort, true);
  assert.ok(snapshot.riskBudgetPct >= 50);
});

test("classifies a violent one-day drop as capitulation risk-off window", () => {
  const slowDrift = trendPrices({ start: 74000, step: -8, count: 420 });
  const crash = trendPrices({ start: slowDrift.at(-1), step: -170, count: 80 });
  const candles15m = candlesFromPrices([...slowDrift, ...crash]);
  const candles4h = candlesFromPrices(
    trendPrices({ start: 76000, step: -95, count: 220 }),
    Date.parse("2026-05-01T00:00:00.000Z"),
    4 * 60 * 60 * 1000,
  );
  const snapshot = classifyRegimeWindow({
    pair: "BTC/USDT:USDT",
    candles15m,
    candles4h,
    alphaRisk: {
      risk: { level: "danger", flags: [{ key: "longCrowding" }, { key: "takerSellPressure" }] },
      metrics: { takerFlow: { buySellRatio: 0.58 }, globalLongShort: { ratio: 2.4 } },
    },
  });

  assert.equal(snapshot.windowType, "capitulation");
  assert.equal(snapshot.allowedPlaybook, "flat");
  assert.equal(snapshot.policy.allowRangeLong, false);
  assert.equal(snapshot.policy.maxStakeMultiplier, 0);
  assert.ok(snapshot.riskBudgetPct <= 10);
});

test("classifies missing candle data as flat transition instead of range", () => {
  const snapshot = classifyRegimeWindow({
    pair: "BTC/USDT:USDT",
    candles15m: [],
    candles4h: [],
    alphaRisk: null,
  });

  assert.equal(snapshot.windowType, "chop");
  assert.equal(snapshot.allowedPlaybook, "flat");
  assert.equal(snapshot.policy.maxStakeMultiplier, 0.25);
  assert.ok(snapshot.confidence <= 30);
  assert.ok(snapshot.reasons.some((reason) => reason.key === "data_gap"));
});

test("does not label crowded longs with active taker buying as pure sell pressure", () => {
  const candles15m = candlesFromPrices(trendPrices({ start: 65000, step: -8, count: 500 }));
  const candles4h = candlesFromPrices(
    trendPrices({ start: 69000, step: -60, count: 220 }),
    Date.parse("2026-05-01T00:00:00.000Z"),
    4 * 60 * 60 * 1000,
  );
  const snapshot = classifyRegimeWindow({
    pair: "BTC/USDT:USDT",
    candles15m,
    candles4h,
    alphaRisk: {
      risk: {
        level: "neutral",
        flags: [
          { key: "longCrowding" },
          { key: "takerBuyPressure" },
        ],
      },
      metrics: {
        takerFlow: { buySellRatio: 1.7 },
        globalLongShort: { ratio: 2.1 },
      },
    },
  });

  assert.equal(snapshot.windowType, "chop");
  assert.equal(snapshot.allowedPlaybook, "flat");
  assert.equal(snapshot.reasons.some((reason) => reason.key === "alpha_crowding"), true);
  assert.equal(snapshot.reasons.some((reason) => reason.key === "alpha_sell_pressure"), false);
});
