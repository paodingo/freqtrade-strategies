"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  buildHistoricalAlphaSnapshots,
  periodToMs,
  samplesUntil,
} = require("../dashboard/lib/alpha_backfill");

test("periodToMs parses Binance futures periods used by alpha risk", () => {
  assert.equal(periodToMs("15m"), 15 * 60 * 1000);
  assert.equal(periodToMs("1h"), 60 * 60 * 1000);
  assert.equal(periodToMs("1d"), 24 * 60 * 60 * 1000);
});

test("samplesUntil returns the rolling samples available at a target time", () => {
  const samples = [
    { timestamp: 1000, value: "old" },
    { timestamp: 2000, value: "current" },
    { timestamp: 3000, value: "future" },
  ];

  assert.deepEqual(samplesUntil(samples, 2000, 2), [
    { timestamp: 1000, value: "old" },
    { timestamp: 2000, value: "current" },
  ]);
});

test("buildHistoricalAlphaSnapshots creates bucketed alpha risk records", () => {
  const startMs = Date.parse("2026-06-10T00:00:00.000Z");
  const periodMs = 15 * 60 * 1000;
  const payloads = {
    fundingRates: [{ fundingTime: startMs, fundingRate: "0.0001" }],
    openInterestHist: [
      { timestamp: startMs, sumOpenInterest: "100", sumOpenInterestValue: "100000" },
      { timestamp: startMs + periodMs, sumOpenInterest: "110", sumOpenInterestValue: "110000" },
    ],
    globalLongShort: [
      { timestamp: startMs, longShortRatio: "1.1", longAccount: "0.52", shortAccount: "0.48" },
      { timestamp: startMs + periodMs, longShortRatio: "1.6", longAccount: "0.62", shortAccount: "0.38" },
    ],
    topTraderPosition: [
      { timestamp: startMs, longShortRatio: "1.2" },
      { timestamp: startMs + periodMs, longShortRatio: "1.3" },
    ],
    topTraderAccount: [
      { timestamp: startMs, longShortRatio: "1.1" },
      { timestamp: startMs + periodMs, longShortRatio: "1.6" },
    ],
    takerFlow: [
      { timestamp: startMs, buySellRatio: "1.0", buyVol: "50", sellVol: "50" },
      { timestamp: startMs + periodMs, buySellRatio: "0.8", buyVol: "40", sellVol: "50" },
    ],
  };

  const snapshots = buildHistoricalAlphaSnapshots({
    pair: "BTC/USDT:USDT",
    period: "15m",
    limit: 2,
    startMs,
    endMs: startMs + periodMs,
    payloads,
  });

  assert.equal(snapshots.length, 2);
  assert.equal(snapshots[0].sampledAt, "2026-06-10T00:00:00.000Z");
  assert.equal(snapshots[1].sampledAt, "2026-06-10T00:15:00.000Z");
  assert.equal(snapshots[1].source, "Binance Futures backfill");
  assert.equal(snapshots[1].metrics.openInterest.changePct, 10);
  assert.equal(snapshots[1].risk.level, "warning");
});
