"use strict";

const BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com";
const BINANCE_FUTURES_ALPHA_ENDPOINTS = {
  premiumIndex: "/fapi/v1/premiumIndex",
  fundingRate: "/fapi/v1/fundingRate",
  openInterestHist: "/futures/data/openInterestHist",
  globalLongShort: "/futures/data/globalLongShortAccountRatio",
  topTraderPosition: "/futures/data/topLongShortPositionRatio",
  topTraderAccount: "/futures/data/topLongShortAccountRatio",
  takerFlow: "/futures/data/takerlongshortRatio",
};

function numeric(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function pct(value, digits = 4) {
  const number = numeric(value);
  return number === null ? null : Number((number * 100).toFixed(digits));
}

function round(value, digits = 4) {
  const number = numeric(value);
  return number === null ? null : Number(number.toFixed(digits));
}

function pairToBinanceSymbol(pair) {
  return String(pair || "")
    .split(":")[0]
    .replace("/", "")
    .replace("-", "")
    .toUpperCase();
}

function latestSample(samples) {
  if (!Array.isArray(samples) || samples.length === 0) {
    return null;
  }
  return [...samples].sort((a, b) => sampleTime(a) - sampleTime(b)).at(-1);
}

function sampleTime(sample) {
  return numeric(sample?.timestamp ?? sample?.time ?? sample?.fundingTime, 0);
}

function changePct(firstValue, lastValue) {
  const first = numeric(firstValue);
  const last = numeric(lastValue);
  if (first === null || last === null || first === 0) {
    return null;
  }
  return ((last - first) / Math.abs(first)) * 100;
}

function metricLevel(value, thresholds) {
  const number = numeric(value);
  if (number === null) {
    return "neutral";
  }
  const abs = Math.abs(number);
  if (abs >= thresholds.danger) {
    return "danger";
  }
  if (abs >= thresholds.warning) {
    return "warning";
  }
  return "neutral";
}

function ratioLevel(ratio, warningHigh, dangerHigh, warningLow = null, dangerLow = null) {
  const value = numeric(ratio);
  if (value === null) {
    return "neutral";
  }
  if ((dangerLow !== null && value <= dangerLow) || value >= dangerHigh) {
    return "danger";
  }
  if ((warningLow !== null && value <= warningLow) || value >= warningHigh) {
    return "warning";
  }
  return "neutral";
}

function pushFlag(flags, condition, key, score, label, note) {
  if (condition) {
    flags.push({ key, score, label, note });
  }
}

function classifyAlphaRisk({
  fundingRate = null,
  openInterestChangePct = null,
  globalLongShortRatio = null,
  topTraderPositionRatio = null,
  topTraderAccountRatio = null,
  takerBuySellRatio = null,
  premiumPct = null,
} = {}) {
  const flags = [];
  pushFlag(
    flags,
    numeric(fundingRate) >= 0.0005,
    "positiveFunding",
    numeric(fundingRate) >= 0.001 ? 25 : 18,
    "资金费率偏高",
    "多头付费压力升高，追多胜率下降。",
  );
  pushFlag(
    flags,
    numeric(fundingRate) <= -0.0005,
    "negativeFunding",
    numeric(fundingRate) <= -0.001 ? 12 : 8,
    "负资金费率",
    "空头付费压力升高，可能出现挤空反弹。",
  );
  pushFlag(
    flags,
    numeric(openInterestChangePct) >= 5,
    "openInterestExpansion",
    numeric(openInterestChangePct) >= 12 ? 26 : numeric(openInterestChangePct) >= 8 ? 22 : 16,
    "杠杆过热",
    "未平仓合约快速增加，波动和清算风险变高。",
  );
  pushFlag(
    flags,
    numeric(globalLongShortRatio) >= 1.5,
    "longCrowding",
    16,
    "多头拥挤",
    "全市场账户偏多，继续追多需要更严格过滤。",
  );
  pushFlag(
    flags,
    numeric(topTraderPositionRatio) >= 1.8,
    "topTraderLongCrowding",
    18,
    "大户持仓偏多",
    "顶级交易员仓位明显偏多，拥挤方向更容易被洗。",
  );
  pushFlag(
    flags,
    numeric(topTraderAccountRatio) >= 1.5,
    "topTraderAccountLongCrowding",
    10,
    "大户账户偏多",
    "顶级账户数量偏多，市场预期可能趋同。",
  );
  pushFlag(
    flags,
    numeric(globalLongShortRatio) !== null && numeric(globalLongShortRatio) <= 0.65,
    "shortCrowding",
    12,
    "空头拥挤",
    "全市场账户偏空，低位追空需要警惕挤空。",
  );
  pushFlag(
    flags,
    numeric(topTraderPositionRatio) !== null && numeric(topTraderPositionRatio) <= 0.65,
    "topTraderShortCrowding",
    8,
    "大户持仓偏空",
    "顶级交易员仓位偏空，反弹时容易被动回补。",
  );
  pushFlag(
    flags,
    numeric(takerBuySellRatio) !== null && numeric(takerBuySellRatio) <= 0.85,
    "takerSellPressure",
    numeric(takerBuySellRatio) <= 0.75 ? 24 : 16,
    "主动卖压",
    "Taker sell volume 明显强于 buy volume。",
  );
  pushFlag(
    flags,
    numeric(takerBuySellRatio) !== null && numeric(takerBuySellRatio) >= 1.45,
    "takerBuyPressure",
    10,
    "主动买压",
    "Taker buy volume 明显强于 sell volume，追多需要看位置。",
  );
  pushFlag(
    flags,
    numeric(premiumPct) !== null && numeric(premiumPct) >= 0.10,
    "positivePremium",
    8,
    "合约溢价",
    "Mark price 相对 index price 偏高。",
  );
  pushFlag(
    flags,
    numeric(premiumPct) !== null && numeric(premiumPct) <= -0.10,
    "negativePremium",
    4,
    "合约折价",
    "Mark price 相对 index price 偏低。",
  );

  const score = Math.min(100, flags.reduce((sum, flag) => sum + flag.score, 0));
  const level = score >= 70 ? "danger" : score >= 40 ? "warning" : score >= 20 ? "neutral" : "good";
  const title = {
    good: "合约环境平稳",
    neutral: "合约环境中性",
    warning: "合约风险升高",
    danger: "合约风险偏高",
  }[level];
  const summary = flags.length
    ? flags.slice(0, 3).map((flag) => flag.label).join(" + ")
    : "未看到明显拥挤或杠杆过热信号。";

  return { score, level, title, summary, flags };
}

function ratioMetric(sample, ratioKey = "longShortRatio") {
  const ratio = numeric(sample?.[ratioKey]);
  const longAccount = numeric(sample?.longAccount);
  const shortAccount = numeric(sample?.shortAccount);
  return {
    ratio,
    longSharePct: longAccount === null ? null : pct(longAccount, 2),
    shortSharePct: shortAccount === null ? null : pct(shortAccount, 2),
    timestamp: sampleTime(sample) || null,
  };
}

function signal(key, label, value, level, note) {
  return { key, label, value, level, note };
}

function buildBinanceFuturesAlphaSnapshot({
  pair,
  symbol = pairToBinanceSymbol(pair),
  payloads = {},
  errors = [],
  now = new Date(),
  source = "Binance Futures",
} = {}) {
  const premium = payloads.premiumIndex || {};
  const dataAvailable = Object.entries(payloads).some(([key, value]) => (
    key !== "period"
    && (Array.isArray(value) ? value.length > 0 : value && Object.keys(value).length > 0)
  ));
  const latestFunding = latestSample(payloads.fundingRates);
  const fundingRate = numeric(premium.lastFundingRate ?? latestFunding?.fundingRate);
  const markPrice = numeric(premium.markPrice);
  const indexPrice = numeric(premium.indexPrice);
  const premiumPct = markPrice !== null && indexPrice ? ((markPrice - indexPrice) / indexPrice) * 100 : null;

  const oiSamples = Array.isArray(payloads.openInterestHist) ? payloads.openInterestHist : [];
  const firstOi = oiSamples[0] || null;
  const latestOi = latestSample(oiSamples);
  const openInterestContracts = numeric(latestOi?.sumOpenInterest ?? payloads.openInterest?.openInterest);
  const openInterestValue = numeric(latestOi?.sumOpenInterestValue);
  const openInterestChangePct = changePct(firstOi?.sumOpenInterest, latestOi?.sumOpenInterest);

  const global = ratioMetric(latestSample(payloads.globalLongShort));
  const topPosition = ratioMetric(latestSample(payloads.topTraderPosition));
  const topAccount = ratioMetric(latestSample(payloads.topTraderAccount));

  const taker = latestSample(payloads.takerFlow);
  const takerBuyVol = numeric(taker?.buyVol);
  const takerSellVol = numeric(taker?.sellVol);
  const takerBuySellRatio = numeric(taker?.buySellRatio)
    ?? (takerSellVol ? takerBuyVol / takerSellVol : null);
  const takerBuySharePct = takerBuyVol !== null && takerSellVol !== null && takerBuyVol + takerSellVol > 0
    ? (takerBuyVol / (takerBuyVol + takerSellVol)) * 100
    : null;

  const classifiedRisk = classifyAlphaRisk({
    fundingRate,
    openInterestChangePct,
    globalLongShortRatio: global.ratio,
    topTraderPositionRatio: topPosition.ratio,
    topTraderAccountRatio: topAccount.ratio,
    takerBuySellRatio,
    premiumPct,
  });
  const risk = dataAvailable
    ? classifiedRisk
    : {
        score: null,
        level: "neutral",
        title: "合约情报不足",
        summary: "Binance 合约数据暂不可用，先不要把它当成风险放行依据。",
        flags: [],
      };

  const metrics = {
    funding: {
      rate: fundingRate,
      ratePct: pct(fundingRate, 4),
      nextFundingTime: numeric(premium.nextFundingTime) ? new Date(Number(premium.nextFundingTime)).toISOString() : null,
      level: metricLevel(fundingRate, { warning: 0.0005, danger: 0.001 }),
    },
    openInterest: {
      contracts: round(openInterestContracts, 3),
      notional: round(openInterestValue, 2),
      changePct: round(openInterestChangePct, 2),
      level: metricLevel(openInterestChangePct, { warning: 5, danger: 12 }),
    },
    globalLongShort: {
      ...global,
      ratio: round(global.ratio, 3),
      level: ratioLevel(global.ratio, 1.5, 2.0, 0.65, 0.5),
    },
    topTraderPosition: {
      ...topPosition,
      ratio: round(topPosition.ratio, 3),
      level: ratioLevel(topPosition.ratio, 1.8, 2.3, 0.65, 0.5),
    },
    topTraderAccount: {
      ...topAccount,
      ratio: round(topAccount.ratio, 3),
      level: ratioLevel(topAccount.ratio, 1.5, 2.0, 0.65, 0.5),
    },
    takerFlow: {
      buySellRatio: round(takerBuySellRatio, 3),
      buyVol: round(takerBuyVol, 3),
      sellVol: round(takerSellVol, 3),
      buySharePct: round(takerBuySharePct, 2),
      timestamp: sampleTime(taker) || null,
      level: ratioLevel(takerBuySellRatio, 1.45, 1.8, 0.85, 0.75),
    },
    premium: {
      markPrice,
      indexPrice,
      premiumPct: round(premiumPct, 4),
      level: metricLevel(premiumPct, { warning: 0.1, danger: 0.25 }),
    },
  };

  const signals = [
    signal("funding", "Funding Rate", metrics.funding.ratePct === null ? "-" : `${metrics.funding.ratePct}%`, metrics.funding.level, "资金费率越高，多头越拥挤。"),
    signal("openInterest", "Open Interest", metrics.openInterest.changePct === null ? "-" : `${metrics.openInterest.changePct}%`, metrics.openInterest.level, "短周期 OI 变化衡量杠杆资金涌入。"),
    signal("globalLongShort", "Global Long/Short", metrics.globalLongShort.ratio ?? "-", metrics.globalLongShort.level, "全市场账户多空比。"),
    signal("topTraderPosition", "Top Trader Position", metrics.topTraderPosition.ratio ?? "-", metrics.topTraderPosition.level, "顶级交易员仓位多空比。"),
    signal("takerFlow", "Taker Flow", metrics.takerFlow.buySellRatio ?? "-", metrics.takerFlow.level, "主动买卖量强弱。"),
    signal("premium", "Mark/Index Premium", metrics.premium.premiumPct === null ? "-" : `${metrics.premium.premiumPct}%`, metrics.premium.level, "合约相对指数价格的溢价或折价。"),
  ];

  return {
    generatedAt: now instanceof Date ? now.toISOString() : new Date(now).toISOString(),
    pair,
    symbol,
    source,
    period: payloads.period || null,
    status: errors.length ? "partial" : "ok",
    errors,
    risk,
    metrics,
    signals,
  };
}

async function fetchJsonEndpoint(fetchImpl, baseUrl, endpoint, params, timeoutMs) {
  const url = new URL(endpoint, baseUrl);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(url.toString(), { signal: controller.signal });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 160)}`);
    }
    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

function createBinanceFuturesAlphaFetcher({
  baseUrl = BINANCE_FUTURES_BASE_URL,
  fetchImpl = global.fetch,
  cacheTtlMs = 30_000,
  timeoutMs = 8_000,
  period = "15m",
  limit = 12,
} = {}) {
  let cached = null;

  return async function fetchBinanceFuturesAlpha({ pair, symbol = pairToBinanceSymbol(pair) } = {}) {
    const cacheKey = `${symbol}:${period}:${limit}`;
    const nowMs = Date.now();
    if (cached && cached.key === cacheKey && cached.expiresAt > nowMs) {
      return {
        ...cached.snapshot,
        cache: { hit: true, expiresAt: new Date(cached.expiresAt).toISOString() },
      };
    }

    const dataParams = { symbol, period, limit };
    const endpointCalls = {
      premiumIndex: [BINANCE_FUTURES_ALPHA_ENDPOINTS.premiumIndex, { symbol }],
      fundingRates: [BINANCE_FUTURES_ALPHA_ENDPOINTS.fundingRate, { symbol, limit }],
      openInterestHist: [BINANCE_FUTURES_ALPHA_ENDPOINTS.openInterestHist, dataParams],
      globalLongShort: [BINANCE_FUTURES_ALPHA_ENDPOINTS.globalLongShort, dataParams],
      topTraderPosition: [BINANCE_FUTURES_ALPHA_ENDPOINTS.topTraderPosition, dataParams],
      topTraderAccount: [BINANCE_FUTURES_ALPHA_ENDPOINTS.topTraderAccount, dataParams],
      takerFlow: [BINANCE_FUTURES_ALPHA_ENDPOINTS.takerFlow, dataParams],
    };

    const entries = await Promise.all(Object.entries(endpointCalls).map(async ([key, [endpoint, params]]) => {
      try {
        return [key, await fetchJsonEndpoint(fetchImpl, baseUrl, endpoint, params, timeoutMs), null];
      } catch (error) {
        return [key, null, error instanceof Error ? error.message : String(error)];
      }
    }));

    const payloads = { period };
    const errors = [];
    for (const [key, value, error] of entries) {
      if (error) {
        errors.push({ key, message: error });
      } else {
        payloads[key] = value;
      }
    }

    const snapshot = buildBinanceFuturesAlphaSnapshot({
      pair,
      symbol,
      payloads,
      errors,
      now: new Date(),
    });
    cached = {
      key: cacheKey,
      expiresAt: nowMs + cacheTtlMs,
      snapshot,
    };
    return { ...snapshot, cache: { hit: false, expiresAt: new Date(cached.expiresAt).toISOString() } };
  };
}

module.exports = {
  BINANCE_FUTURES_ALPHA_ENDPOINTS,
  buildBinanceFuturesAlphaSnapshot,
  classifyAlphaRisk,
  createBinanceFuturesAlphaFetcher,
  pairToBinanceSymbol,
};
