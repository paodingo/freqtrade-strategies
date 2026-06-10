"use strict";

const {
  buildBinanceFuturesAlphaSnapshot,
  pairToBinanceSymbol,
} = require("./binance_futures_alpha");

function periodToMs(period) {
  const match = String(period || "").match(/^(\d+)([mhd])$/i);
  if (!match) {
    throw new Error(`Unsupported period: ${period}`);
  }
  const amount = Number(match[1]);
  const unit = match[2].toLowerCase();
  const unitMs = unit === "m" ? 60_000 : unit === "h" ? 3_600_000 : 86_400_000;
  return amount * unitMs;
}

function sampleTimestamp(sample) {
  const value = sample?.timestamp ?? sample?.time ?? sample?.fundingTime;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function samplesUntil(samples, targetMs, limit) {
  return [...(samples || [])]
    .filter((sample) => {
      const timestamp = sampleTimestamp(sample);
      return timestamp !== null && timestamp <= targetMs;
    })
    .sort((a, b) => sampleTimestamp(a) - sampleTimestamp(b))
    .slice(-limit);
}

function hasHistoricalPayload(payloads) {
  return [
    "openInterestHist",
    "globalLongShort",
    "topTraderPosition",
    "topTraderAccount",
    "takerFlow",
  ].some((key) => Array.isArray(payloads[key]) && payloads[key].length > 0);
}

function buildHistoricalAlphaSnapshots({
  pair,
  symbol = pairToBinanceSymbol(pair),
  period = "15m",
  limit = 12,
  startMs,
  endMs,
  payloads,
} = {}) {
  const periodMs = periodToMs(period);
  const snapshots = [];
  for (let targetMs = startMs; targetMs <= endMs; targetMs += periodMs) {
    const historicalPayloads = {
      period,
      fundingRates: samplesUntil(payloads.fundingRates, targetMs, 24),
      openInterestHist: samplesUntil(payloads.openInterestHist, targetMs, limit),
      globalLongShort: samplesUntil(payloads.globalLongShort, targetMs, limit),
      topTraderPosition: samplesUntil(payloads.topTraderPosition, targetMs, limit),
      topTraderAccount: samplesUntil(payloads.topTraderAccount, targetMs, limit),
      takerFlow: samplesUntil(payloads.takerFlow, targetMs, limit),
    };
    if (!hasHistoricalPayload(historicalPayloads)) {
      continue;
    }
    const sampledAt = new Date(targetMs).toISOString();
    snapshots.push({
      ...buildBinanceFuturesAlphaSnapshot({
        pair,
        symbol,
        payloads: historicalPayloads,
        errors: [],
        now: new Date(targetMs),
        source: "Binance Futures backfill",
      }),
      sampledAt,
    });
  }
  return snapshots;
}

module.exports = {
  buildHistoricalAlphaSnapshots,
  periodToMs,
  samplesUntil,
};
