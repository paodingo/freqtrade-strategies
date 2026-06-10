"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  BINANCE_FUTURES_ALPHA_ENDPOINTS,
  buildBinanceFuturesAlphaSnapshot,
  classifyAlphaRisk,
  createBinanceFuturesAlphaFetcher,
} = require("../dashboard/lib/binance_futures_alpha");

test("Binance futures alpha endpoint map covers contract intelligence sources", () => {
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.premiumIndex, "/fapi/v1/premiumIndex");
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.fundingRate, "/fapi/v1/fundingRate");
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.openInterestHist, "/futures/data/openInterestHist");
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.globalLongShort, "/futures/data/globalLongShortAccountRatio");
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.topTraderPosition, "/futures/data/topLongShortPositionRatio");
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.topTraderAccount, "/futures/data/topLongShortAccountRatio");
  assert.equal(BINANCE_FUTURES_ALPHA_ENDPOINTS.takerFlow, "/futures/data/takerlongshortRatio");
});

test("Alpha snapshot flags crowded long leverage as dangerous", () => {
  const snapshot = buildBinanceFuturesAlphaSnapshot({
    pair: "BTC/USDT:USDT",
    symbol: "BTCUSDT",
    now: new Date("2026-06-11T01:00:00+08:00"),
    payloads: {
      premiumIndex: {
        markPrice: "62080",
        indexPrice: "62000",
        lastFundingRate: "0.00072",
        nextFundingTime: 1781136000000,
      },
      fundingRates: [
        { fundingRate: "0.00044", fundingTime: 1781107200000 },
        { fundingRate: "0.00072", fundingTime: 1781136000000 },
      ],
      openInterestHist: [
        { sumOpenInterest: "100000", sumOpenInterestValue: "6200000000", timestamp: 1781110800000 },
        { sumOpenInterest: "109000", sumOpenInterestValue: "6765800000", timestamp: 1781111700000 },
      ],
      globalLongShort: [
        { longShortRatio: "1.86", longAccount: "0.6503", shortAccount: "0.3497", timestamp: 1781111700000 },
      ],
      topTraderPosition: [
        { longShortRatio: "2.40", longAccount: "0.7059", shortAccount: "0.2941", timestamp: 1781111700000 },
      ],
      topTraderAccount: [
        { longShortRatio: "1.78", longAccount: "0.6403", shortAccount: "0.3597", timestamp: 1781111700000 },
      ],
      takerFlow: [
        { buySellRatio: "0.72", buyVol: "1320", sellVol: "1833", timestamp: 1781111700000 },
      ],
    },
  });

  assert.equal(snapshot.status, "ok");
  assert.equal(snapshot.risk.level, "danger");
  assert.ok(snapshot.risk.score >= 75);
  assert.match(snapshot.risk.summary, /多头拥挤|杠杆过热|主动卖压/);
  assert.equal(snapshot.metrics.funding.level, "warning");
  assert.equal(snapshot.metrics.openInterest.level, "warning");
  assert.equal(snapshot.metrics.takerFlow.level, "danger");
  assert.ok(snapshot.signals.some((signal) => signal.key === "topTraderPosition"));
});

test("Alpha snapshot keeps balanced futures context low risk", () => {
  const snapshot = buildBinanceFuturesAlphaSnapshot({
    pair: "BTC/USDT:USDT",
    symbol: "BTCUSDT",
    now: new Date("2026-06-11T01:00:00+08:00"),
    payloads: {
      premiumIndex: {
        markPrice: "62003",
        indexPrice: "62000",
        lastFundingRate: "0.00008",
        nextFundingTime: 1781136000000,
      },
      fundingRates: [{ fundingRate: "0.00008", fundingTime: 1781136000000 }],
      openInterestHist: [
        { sumOpenInterest: "100000", sumOpenInterestValue: "6200000000", timestamp: 1781110800000 },
        { sumOpenInterest: "100600", sumOpenInterestValue: "6237200000", timestamp: 1781111700000 },
      ],
      globalLongShort: [
        { longShortRatio: "1.04", longAccount: "0.51", shortAccount: "0.49", timestamp: 1781111700000 },
      ],
      topTraderPosition: [
        { longShortRatio: "1.08", longAccount: "0.52", shortAccount: "0.48", timestamp: 1781111700000 },
      ],
      topTraderAccount: [
        { longShortRatio: "0.98", longAccount: "0.495", shortAccount: "0.505", timestamp: 1781111700000 },
      ],
      takerFlow: [
        { buySellRatio: "1.01", buyVol: "1505", sellVol: "1490", timestamp: 1781111700000 },
      ],
    },
  });

  assert.ok(["good", "neutral"].includes(snapshot.risk.level));
  assert.ok(snapshot.risk.score < 35);
  assert.equal(snapshot.metrics.funding.level, "neutral");
  assert.equal(snapshot.metrics.openInterest.level, "neutral");
});

test("Alpha snapshot reports unavailable when all Binance endpoints fail", () => {
  const snapshot = buildBinanceFuturesAlphaSnapshot({
    pair: "BTC/USDT:USDT",
    symbol: "BTCUSDT",
    now: new Date("2026-06-11T01:00:00+08:00"),
    payloads: { period: "15m" },
    errors: [{ key: "premiumIndex", message: "timeout" }],
  });

  assert.equal(snapshot.status, "partial");
  assert.equal(snapshot.risk.level, "neutral");
  assert.equal(snapshot.risk.score, null);
  assert.equal(snapshot.risk.title, "合约情报不足");
  assert.match(snapshot.risk.summary, /暂不可用/);
});

test("Fetcher uses symbol parameter for Binance futures data endpoints", async () => {
  const requested = [];
  const fetchAlpha = createBinanceFuturesAlphaFetcher({
    baseUrl: "https://example.test",
    period: "15m",
    limit: 2,
    fetchImpl: async (url) => {
      requested.push(new URL(url));
      return {
        ok: true,
        text: async () => {
          const path = new URL(url).pathname;
          if (path.endsWith("/premiumIndex")) {
            return JSON.stringify({ markPrice: "62001", indexPrice: "62000", lastFundingRate: "0.00001" });
          }
          if (path.endsWith("/fundingRate")) {
            return JSON.stringify([{ fundingRate: "0.00001", fundingTime: 1781136000000 }]);
          }
          if (path.endsWith("/openInterestHist")) {
            return JSON.stringify([{ sumOpenInterest: "100", sumOpenInterestValue: "6200000", timestamp: 1781111700000 }]);
          }
          if (path.endsWith("/takerlongshortRatio")) {
            return JSON.stringify([{ buySellRatio: "1.00", buyVol: "100", sellVol: "100", timestamp: 1781111700000 }]);
          }
          return JSON.stringify([{ longShortRatio: "1.00", longAccount: "0.5", shortAccount: "0.5", timestamp: 1781111700000 }]);
        },
      };
    },
  });

  await fetchAlpha({ pair: "BTC/USDT:USDT" });

  const dataUrls = requested.filter((url) => url.pathname.startsWith("/futures/data/"));
  assert.equal(dataUrls.length, 5);
  assert.ok(dataUrls.every((url) => url.searchParams.get("symbol") === "BTCUSDT"));
  assert.ok(dataUrls.every((url) => !url.searchParams.has("pair")));
  assert.equal(requested.find((url) => url.pathname.endsWith("/fundingRate")).searchParams.get("symbol"), "BTCUSDT");
});

test("Risk classifier promotes severe negative funding as short squeeze context", () => {
  const risk = classifyAlphaRisk({
    fundingRate: -0.0012,
    openInterestChangePct: 8.5,
    globalLongShortRatio: 0.58,
    topTraderPositionRatio: 0.52,
    takerBuySellRatio: 1.35,
    premiumPct: -0.18,
  });

  assert.equal(risk.level, "warning");
  assert.ok(risk.flags.some((flag) => flag.key === "shortCrowding"));
  assert.ok(risk.flags.some((flag) => flag.key === "negativeFunding"));
});
