"use strict";

const MS_PER_HOUR = 60 * 60 * 1000;

function numeric(value, fallback = null) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function candleTimeMs(candle) {
  const rawTime = numeric(candle?.time ?? candle?.timestamp);
  if (rawTime !== null) {
    return rawTime > 10_000_000_000 ? rawTime : rawTime * 1000;
  }
  const parsed = Date.parse(candle?.date || candle?.datetime || "");
  return Number.isFinite(parsed) ? parsed : null;
}

function closePrice(candle) {
  return numeric(candle?.close);
}

function sortedCandles(candles) {
  return (Array.isArray(candles) ? candles : [])
    .map((candle) => ({
      ...candle,
      _timeMs: candleTimeMs(candle),
      _close: closePrice(candle),
    }))
    .filter((candle) => candle._timeMs !== null && candle._close !== null)
    .sort((a, b) => a._timeMs - b._timeMs);
}

function percentChange(from, to) {
  const start = numeric(from);
  const end = numeric(to);
  if (start === null || end === null || start === 0) {
    return null;
  }
  return ((end - start) / start) * 100;
}

function returnSince(candles, hours) {
  if (candles.length < 2) {
    return null;
  }
  const latest = candles.at(-1);
  const cutoff = latest._timeMs - hours * MS_PER_HOUR;
  const base = candles.findLast((candle) => candle._timeMs <= cutoff) || candles[0];
  return percentChange(base._close, latest._close);
}

function rangeSince(candles, hours) {
  if (candles.length < 2) {
    return null;
  }
  const latest = candles.at(-1);
  const cutoff = latest._timeMs - hours * MS_PER_HOUR;
  const windowCandles = candles.filter((candle) => candle._timeMs >= cutoff);
  if (windowCandles.length < 2) {
    return null;
  }
  const highs = windowCandles.map((candle) => numeric(candle.high, candle._close)).filter((value) => value !== null);
  const lows = windowCandles.map((candle) => numeric(candle.low, candle._close)).filter((value) => value !== null);
  if (highs.length === 0 || lows.length === 0) {
    return null;
  }
  const high = Math.max(...highs);
  const low = Math.min(...lows);
  const mid = (high + low) / 2;
  return mid > 0 ? ((high - low) / mid) * 100 : null;
}

function ema(values, period) {
  if (values.length === 0) {
    return null;
  }
  const alpha = 2 / (period + 1);
  return values.reduce((current, value, index) => {
    if (index === 0) {
      return value;
    }
    return value * alpha + current * (1 - alpha);
  }, values[0]);
}

function latestEmaStack(candles) {
  const latest = candles.at(-1);
  if (!latest) {
    return "unknown";
  }
  const closes = candles.map((candle) => candle._close);
  const ema21 = numeric(latest.ema21, ema(closes.slice(-120), 21));
  const ema55 = numeric(latest.ema55, ema(closes.slice(-220), 55));
  const ema200 = numeric(latest.ema200, ema(closes.slice(-260), 200));
  const close = latest._close;
  if ([ema21, ema55, ema200, close].some((value) => value === null)) {
    return "unknown";
  }
  if (close > ema21 && ema21 > ema55 && ema55 > ema200) {
    return "bull";
  }
  if (close < ema21 && ema21 < ema55 && ema55 < ema200) {
    return "bear";
  }
  return "mixed";
}

function alphaFlagSet(alphaRisk) {
  return new Set((alphaRisk?.risk?.flags || [])
    .map((flag) => flag?.key)
    .filter(Boolean));
}

function hasAnyFlag(flags, keys) {
  return keys.some((key) => flags.has(key));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function reason(key, label, value, level = "info", note = null) {
  return { key, label, value, level, note };
}

function basePolicy(overrides = {}) {
  return {
    allowTrendLong: false,
    allowTrendShort: false,
    allowRangeLong: false,
    allowRangeShort: false,
    maxStakeMultiplier: 0,
    notes: [],
    ...overrides,
  };
}

function snapshotFor(kind, context) {
  const {
    pair,
    metrics,
    reasons,
    confidence,
    generatedAt,
  } = context;
  const shared = {
    generatedAt,
    pair,
    confidence: clamp(Math.round(confidence), 0, 100),
    metrics,
    reasons,
  };

  if (kind === "capitulation") {
    return {
      ...shared,
      windowType: "capitulation",
      title: "踩踏风险下线",
      summary: "快速下跌叠加合约压力，先退出进攻状态，等波动降温。",
      allowedPlaybook: "flat",
      riskBudgetPct: 5,
      directionBias: "risk_off",
      policy: basePolicy({
        maxStakeMultiplier: 0,
        notes: ["单日下跌速度极端时，不允许新开仓。"],
      }),
    };
  }

  if (kind === "downtrend") {
    return {
      ...shared,
      windowType: "downtrend",
      title: "下跌趋势做空窗口",
      summary: "下跌趋势叠加多头拥挤或主动卖压，优先趋势做空，避免震荡抄底。",
      allowedPlaybook: "trend_short",
      riskBudgetPct: 50,
      directionBias: "short",
      policy: basePolicy({
        allowTrendShort: true,
        maxStakeMultiplier: 0.5,
        notes: ["趋势压力缓解前，关闭震荡做多抄底。"],
      }),
    };
  }

  if (kind === "uptrend") {
    return {
      ...shared,
      windowType: "uptrend",
      title: "上涨趋势回调窗口",
      summary: "上涨趋势成立且杠杆数据可控，优先趋势做多和浅回调入场。",
      allowedPlaybook: "trend_long",
      riskBudgetPct: 60,
      directionBias: "long",
      policy: basePolicy({
        allowTrendLong: true,
        maxStakeMultiplier: 0.6,
        notes: ["除非合约风险转危险，不要逆着清晰上涨趋势做空。"],
      }),
    };
  }

  if (kind === "range") {
    return {
      ...shared,
      windowType: "range",
      title: "震荡区间边缘窗口",
      summary: "低波动双向震荡，只有靠近清晰边缘时才允许均值回归入场。",
      allowedPlaybook: "range_edge",
      riskBudgetPct: 60,
      directionBias: "neutral",
      policy: basePolicy({
        allowRangeLong: true,
        allowRangeShort: true,
        maxStakeMultiplier: 0.6,
        notes: ["目标要小；一旦有效突破，就停止按震荡区间交易。"],
      }),
    };
  }

  return {
    ...shared,
    windowType: "chop",
    title: "震荡过渡窗口",
    summary: "趋势、波动和合约数据没有形成一致方向，先降低暴露，等待更干净的窗口。",
    allowedPlaybook: "flat",
    riskBudgetPct: 25,
    directionBias: "neutral",
    policy: basePolicy({
      maxStakeMultiplier: 0.25,
      notes: ["趋势和合约数据一致前，保持观察模式。"],
    }),
  };
}

function classifyRegimeWindow({ pair = "BTC/USDT:USDT", candles15m = [], candles4h = [], alphaRisk = null, generatedAt = null } = {}) {
  const intraday = sortedCandles(candles15m);
  const higherTimeframe = sortedCandles(candles4h);
  const primary = higherTimeframe.length >= 30 ? higherTimeframe : intraday;
  const latest = intraday.at(-1) || primary.at(-1) || null;
  const flags = alphaFlagSet(alphaRisk);
  const alphaLevel = alphaRisk?.risk?.level || "unknown";
  const takerBuySellRatio = numeric(alphaRisk?.metrics?.takerFlow?.buySellRatio);
  const globalLongShortRatio = numeric(alphaRisk?.metrics?.globalLongShort?.ratio);
  const topTraderAccountRatio = numeric(alphaRisk?.metrics?.topTraderAccount?.ratio);
  const return4hPct = returnSince(intraday, 4);
  const return24hPct = returnSince(intraday, 24);
  const return7dPct = returnSince(primary, 24 * 7);
  const range24hPct = rangeSince(intraday, 24);
  const emaStack = latestEmaStack(primary);
  const takerSellPressure = hasAnyFlag(flags, ["takerSellPressure"])
    || (takerBuySellRatio !== null && takerBuySellRatio < 0.85);
  const takerBuyPressure = hasAnyFlag(flags, ["takerBuyPressure"])
    || (takerBuySellRatio !== null && takerBuySellRatio > 1.15);
  const longCrowding = hasAnyFlag(flags, ["longCrowding", "topTraderPositionLongCrowding", "topTraderAccountLongCrowding"]);
  const shortCrowding = hasAnyFlag(flags, ["shortCrowding", "topTraderPositionShortCrowding", "topTraderAccountShortCrowding"]);
  const sellPressure = takerSellPressure || (longCrowding && !takerBuyPressure);
  const buyPressure = takerBuyPressure || (shortCrowding && !takerSellPressure);
  const crowding = longCrowding || shortCrowding;

  const metrics = {
    latestClose: latest?._close ?? null,
    return4hPct,
    return24hPct,
    return7dPct,
    range24hPct,
    emaStack,
    alphaLevel,
    takerBuySellRatio,
    globalLongShortRatio,
    topTraderAccountRatio,
    flags: Array.from(flags),
  };
  const reasons = [];

  if (return24hPct !== null) {
    reasons.push(reason("return_24h", "24h return", Number(return24hPct.toFixed(2)), return24hPct < -2 ? "warning" : "info"));
  }
  if (return7dPct !== null) {
    reasons.push(reason("return_7d", "7d return", Number(return7dPct.toFixed(2)), Math.abs(return7dPct) > 6 ? "warning" : "info"));
  }
  if (range24hPct !== null) {
    reasons.push(reason("range_24h", "24h range", Number(range24hPct.toFixed(2)), range24hPct > 5 ? "warning" : "info"));
  }
  if (emaStack !== "unknown") {
    reasons.push(reason("ema_stack", "EMA stack", emaStack, emaStack === "mixed" ? "info" : "warning"));
  }
  if (sellPressure) {
    reasons.push(reason("alpha_sell_pressure", "Alpha sell pressure", "active", "warning"));
  }
  if (crowding) {
    reasons.push(reason("alpha_crowding", "Derivatives crowding", "active", "warning"));
  }

  const context = {
    pair,
    metrics,
    reasons,
    confidence: 45,
    generatedAt: generatedAt || new Date().toISOString(),
  };

  if (!latest) {
    return snapshotFor("chop", {
      ...context,
      confidence: 20,
      reasons: [
        ...reasons,
        reason("data_gap", "Candle data", "missing", "danger"),
      ],
    });
  }

  const severeDrop = (return4hPct !== null && return4hPct <= -3)
    || (alphaLevel === "danger" && return24hPct !== null && return24hPct <= -5);
  const dangerAlpha = alphaLevel === "danger" || (sellPressure && crowding);
  if (severeDrop && (dangerAlpha || (range24hPct !== null && range24hPct >= 5))) {
    return snapshotFor("capitulation", {
      ...context,
      confidence: 88,
      reasons: [
        ...reasons,
        reason("risk_off_velocity", "Downside velocity", "extreme", "danger"),
      ],
    });
  }

  const bearTrend = emaStack === "bear" || (return7dPct !== null && return7dPct <= -6);
  if (bearTrend && sellPressure && ((return24hPct !== null && return24hPct <= -1.2) || (return7dPct !== null && return7dPct <= -5))) {
    return snapshotFor("downtrend", {
      ...context,
      confidence: 76 + (crowding ? 8 : 0),
    });
  }

  const bullTrend = emaStack === "bull" || (return7dPct !== null && return7dPct >= 6);
  const alphaIsSafe = !["danger", "warning"].includes(alphaLevel) || buyPressure;
  if (bullTrend && alphaIsSafe && return24hPct !== null && return24hPct >= 0.5) {
    return snapshotFor("uptrend", {
      ...context,
      confidence: 72,
    });
  }

  const sideways = (return7dPct === null || Math.abs(return7dPct) <= 3)
    && (return24hPct === null || Math.abs(return24hPct) <= 2)
    && (range24hPct === null || range24hPct <= 4)
    && !["danger"].includes(alphaLevel);
  if (sideways) {
    return snapshotFor("range", {
      ...context,
      confidence: 70,
    });
  }

  return snapshotFor("chop", {
    ...context,
    confidence: 52,
  });
}

module.exports = {
  classifyRegimeWindow,
};
