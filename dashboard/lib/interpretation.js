"use strict";

function numeric(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function pctDistance(fromPrice, toPrice) {
  const from = numeric(fromPrice);
  const to = numeric(toPrice);
  if (!from || !to) return null;
  return Math.abs((to - from) / from) * 100;
}

function fmtNumber(value, digits = 2) {
  const number = numeric(value);
  if (number === null) return "-";
  return number.toLocaleString("en-US", { maximumFractionDigits: digits });
}

function fmtMoney(value) {
  const number = numeric(value);
  if (number === null) return "-";
  return `${number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT`;
}

function fmtPct(value, digits = 2) {
  const number = numeric(value);
  if (number === null) return "-";
  return `${fmtNumber(number, digits)}%`;
}

function normalizeTrade(trade) {
  if (!trade) return null;
  return {
    pair: trade.pair || "-",
    isShort: Boolean(trade.is_short ?? trade.isShort),
    enterTag: trade.enter_tag ?? trade.enterTag ?? "",
    stakeAmount: numeric(trade.stake_amount ?? trade.stakeAmount, 0),
    openRate: numeric(trade.open_rate ?? trade.openRate),
    currentRate: numeric(trade.current_rate ?? trade.currentRate),
    stopLoss: numeric(trade.stop_loss_abs ?? trade.stopLoss),
    liquidationPrice: numeric(trade.liquidation_price ?? trade.liquidationPrice),
    profitAbs: numeric(trade.profit_abs ?? trade.total_profit_abs ?? trade.profitAbs, 0),
    profitPct: numeric(trade.profit_pct ?? trade.profitPct),
    fundingFees: numeric(trade.funding_fees ?? trade.fundingFees, 0),
  };
}

function botTrade(bot) {
  return normalizeTrade(Array.isArray(bot?.openTrades) ? bot.openTrades[0] : null);
}

function riskSeverity(trade) {
  if (!trade) return "neutral";
  const stopDistance = pctDistance(trade.currentRate, trade.stopLoss);
  const liqDistance = pctDistance(trade.currentRate, trade.liquidationPrice);
  if ((stopDistance !== null && stopDistance < 1.5) || (liqDistance !== null && liqDistance < 10)) {
    return "danger";
  }
  if ((stopDistance !== null && stopDistance < 3.5) || (liqDistance !== null && liqDistance < 18)) {
    return "warning";
  }
  return "good";
}

function directionText(trade) {
  if (!trade) return "空仓";
  return trade.isShort ? "做空" : "做多";
}

function tradeFrequency(bot) {
  const tradeCount = numeric(bot?.tradeCount, 0);
  const firstTradeDate = bot?.firstTradeDate;
  const firstMs = Date.parse(firstTradeDate || "");
  if (!tradeCount || !Number.isFinite(firstMs)) {
    return { tradesPerDay: null, level: "neutral", text: "样本不足" };
  }

  const days = Math.max(1, (Date.now() - firstMs) / 86_400_000);
  const tradesPerDay = tradeCount / days;
  if (tradesPerDay > 10) {
    return { tradesPerDay, level: "danger", text: "交易偏密" };
  }
  if (tradesPerDay > 5) {
    return { tradesPerDay, level: "warning", text: "交易较密" };
  }
  return { tradesPerDay, level: "good", text: "频率正常" };
}

function costPressure(bot) {
  const trade = botTrade(bot);
  const frequency = tradeFrequency(bot);
  const profitAbs = Math.abs(numeric(trade?.profitAbs, 0));
  const fundingAbs = Math.abs(numeric(trade?.fundingFees, 0));
  const fundingToPnlPct = profitAbs > 0 ? (fundingAbs / profitAbs) * 100 : null;

  let level = "neutral";
  let title = "成本样本不足";
  if (trade) {
    if ((fundingToPnlPct !== null && fundingToPnlPct >= 30) || frequency.level === "danger") {
      level = "danger";
      title = "成本压力偏高";
    } else if ((fundingToPnlPct !== null && fundingToPnlPct >= 10) || frequency.level === "warning") {
      level = "warning";
      title = "成本需要观察";
    } else {
      level = "good";
      title = "成本压力较低";
    }
  } else if (frequency.level === "warning" || frequency.level === "danger") {
    level = frequency.level;
    title = "交易频率需要观察";
  }

  return {
    level,
    title,
    fundingFees: numeric(trade?.fundingFees, 0),
    fundingToPnlPct,
    profitPct: numeric(trade?.profitPct),
    tradesPerDay: frequency.tradesPerDay,
    frequencyText: frequency.text,
    avgProfitPerTrade: numeric(bot?.tradeCount, 0) > 0
      ? numeric(bot?.profitAllCoin, 0) / numeric(bot?.tradeCount, 1)
      : null,
  };
}

function buildPositionInterpretation(bots) {
  const okBots = bots.filter((bot) => bot?.ok);
  const entries = okBots.map((bot) => {
    const trade = botTrade(bot);
    const stopDistance = pctDistance(trade?.currentRate, trade?.stopLoss);
    const liqDistance = pctDistance(trade?.currentRate, trade?.liquidationPrice);
    return {
      key: bot.key,
      label: bot.label,
      state: trade ? "open" : "flat",
      direction: directionText(trade),
      pair: trade?.pair || null,
      stakeAmount: numeric(trade?.stakeAmount),
      profitAbs: numeric(trade?.profitAbs, 0),
      profitPct: numeric(trade?.profitPct),
      fundingFees: numeric(trade?.fundingFees, 0),
      stopDistancePct: stopDistance,
      liquidationDistancePct: liqDistance,
      severity: riskSeverity(trade),
      summary: trade
        ? `${bot.label} 当前${directionText(trade)}，浮盈亏 ${fmtMoney(trade.profitAbs)}，止损距离 ${fmtPct(stopDistance)}，强平距离 ${fmtPct(liqDistance)}。`
        : `${bot.label} 当前空仓，等待下一次策略信号。`,
    };
  });

  const openEntries = entries.filter((entry) => entry.state === "open");
  let title = "当前空仓等待";
  let level = "neutral";
  let body = "两个策略当前都没有持仓，先观察下一次信号质量和触发频率。";
  if (openEntries.length === 1) {
    title = `${openEntries[0].label} 单边持仓`;
    level = openEntries[0].severity;
    body = `${openEntries[0].label} 已经${openEntries[0].direction}，另一侧还在等待信号；这通常说明两个版本的风险/入场节奏出现差异。`;
  } else if (openEntries.length >= 2) {
    const sameDirection = openEntries.every((entry) => entry.direction === openEntries[0].direction);
    title = sameDirection ? `双策略同向${openEntries[0].direction}` : "双策略方向分歧";
    level = openEntries.some((entry) => entry.severity === "danger")
      ? "danger"
      : openEntries.some((entry) => entry.severity === "warning") ? "warning" : "good";
    body = sameDirection
      ? "两个策略方向一致，重点看谁的仓位更克制、止损/强平距离更健康。"
      : "两个策略方向不一致，需要优先确认信号来源和风险暴露，不宜只看短期浮盈亏。";
  }

  return { title, level, body, entries };
}

function buildCostInterpretation(bots) {
  const entries = bots.filter((bot) => bot?.ok).map((bot) => {
    const cost = costPressure(bot);
    return {
      key: bot.key,
      label: bot.label,
      ...cost,
      summary: `${bot.label}: ${cost.title}，资金费 ${fmtMoney(cost.fundingFees)}，资金费/浮盈亏 ${fmtPct(cost.fundingToPnlPct)}，交易频率 ${cost.tradesPerDay === null ? cost.frequencyText : `${fmtNumber(cost.tradesPerDay, 2)} 笔/天`}。`,
    };
  });
  const worst = entries.find((entry) => entry.level === "danger")
    || entries.find((entry) => entry.level === "warning")
    || entries.find((entry) => entry.level === "good")
    || entries[0];

  return {
    title: worst?.title || "成本样本不足",
    level: worst?.level || "neutral",
    body: "当前成本视角先用资金费、浮盈亏空间和交易频率判断；手续费/滑点需要实盘成交明细后再精确拆分。",
    entries,
  };
}

function buildComparisonInterpretation(bots, comparison) {
  if (!comparison?.ready) {
    return {
      title: "对比样本不足",
      level: "neutral",
      body: "至少需要两个 bot 都能读到 API 数据后，才能给出版本对比结论。",
      items: [],
    };
  }

  const base = bots.find((bot) => bot.key === comparison.baseKey);
  const challenger = bots.find((bot) => bot.key === comparison.challengerKey);
  const baseTrade = botTrade(base);
  const challengerTrade = botTrade(challenger);
  const usedDelta = numeric(comparison.usedStakeDelta, 0);
  const profitDelta = numeric(comparison.profitAllCoinDelta, 0);
  const openDelta = numeric(comparison.openTradesDelta, 0);

  let title = "继续观察";
  let level = "neutral";
  let body = "当前差异还不足以单独判断版本优劣，需要继续积累交易样本。";

  if (baseTrade && !challengerTrade) {
    title = `${comparison.challengerLabel} 更克制`;
    level = "good";
    body = `${comparison.baseLabel} 已持仓而 ${comparison.challengerLabel} 空仓，当前更像是对照策略的风险预算在减少不必要暴露。`;
  } else if (!baseTrade && challengerTrade) {
    title = `${comparison.challengerLabel} 更主动`;
    level = riskSeverity(challengerTrade);
    body = `${comparison.challengerLabel} 已持仓而 ${comparison.baseLabel} 空仓，需要看这笔交易是否有足够收益空间覆盖成本。`;
  } else if (baseTrade && challengerTrade) {
    if (usedDelta < -100 && profitDelta >= 0) {
      title = `${comparison.challengerLabel} 暂时更有效率`;
      level = "good";
      body = `${comparison.challengerLabel} 当前占用资金更少且收益不低于 ${comparison.baseLabel}，这是更好的风险效率信号。`;
    } else if (usedDelta > 100 && profitDelta <= 0) {
      title = `${comparison.challengerLabel} 暴露偏高`;
      level = "warning";
      body = `${comparison.challengerLabel} 当前占用资金更多但收益没有领先，需要重点观察加仓是否带来额外风险。`;
    } else {
      title = "双策略都在持仓";
      level = "neutral";
      body = "两个版本都在场内，短期看浮盈亏，长期要看回撤和成本占比。";
    }
  }

  return {
    title,
    level,
    body,
    items: [
      { label: "收益差", value: fmtMoney(profitDelta), level: profitDelta > 0 ? "good" : profitDelta < 0 ? "warning" : "neutral" },
      { label: "占用资金差", value: fmtMoney(usedDelta), level: usedDelta > 0 ? "warning" : usedDelta < 0 ? "good" : "neutral" },
      { label: "开仓数差", value: `${fmtNumber(openDelta, 0)} 手`, level: openDelta > 0 ? "warning" : openDelta < 0 ? "good" : "neutral" },
    ],
  };
}

function buildDashboardInterpretation({ bots = [], comparison = null, mainTimeframe = "1h", informativeTimeframe = "4h" } = {}) {
  return {
    timeframes: {
      main: mainTimeframe,
      informative: informativeTimeframe,
      summary: `当前策略以 ${mainTimeframe} 为主交易周期，${informativeTimeframe} 用于趋势和市场状态过滤。`,
    },
    position: buildPositionInterpretation(bots),
    cost: buildCostInterpretation(bots),
    comparison: buildComparisonInterpretation(bots, comparison),
  };
}

module.exports = {
  buildDashboardInterpretation,
  costPressure,
  normalizeTrade,
  pctDistance,
  tradeFrequency,
};
