"use strict";

const chartTheme = {
  layout: {
    background: { color: "transparent" },
    textColor: "#aab4bf",
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Microsoft YaHei, sans-serif",
  },
  grid: {
    vertLines: { color: "rgba(255, 255, 255, 0.05)" },
    horzLines: { color: "rgba(255, 255, 255, 0.05)" },
  },
  rightPriceScale: { borderColor: "rgba(255, 255, 255, 0.10)" },
  timeScale: { borderColor: "rgba(255, 255, 255, 0.10)", timeVisible: true },
};

const colors = {
  green: "#42d27d",
  red: "#ff6b6b",
  amber: "#f4c35d",
  cyan: "#55c8e8",
  blue: "#78a8ff",
  violet: "#b49aff",
  muted: "#7f8a96",
};

const BEIJING_TIME_ZONE = "Asia/Shanghai";
const beijingDateTime = new Intl.DateTimeFormat("zh-CN", {
  timeZone: BEIJING_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const beijingTickTime = new Intl.DateTimeFormat("zh-CN", {
  timeZone: BEIJING_TIME_ZONE,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const state = {
  refreshSeconds: 15,
  summary: null,
  market: null,
  history: null,
  summaryTimer: null,
  historyTimer: null,
  charts: {},
  showStrategySignals: false,
  btcUserViewLocked: false,
};

const moneyFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function qs(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numeric(value, fallback = null) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function valueClass(value) {
  const number = numeric(value, 0);
  if (number > 0) return "positive";
  if (number < 0) return "negative";
  return "neutral";
}

function fmtNumber(value, digits = 2) {
  const number = numeric(value);
  if (number === null) return "-";
  return number.toLocaleString("en-US", { maximumFractionDigits: digits });
}

function fmtMoney(value, suffix = "USDT") {
  const number = numeric(value);
  if (number === null) return "-";
  return `${moneyFormatter.format(number)} ${suffix}`;
}

function fmtPrice(value) {
  return fmtNumber(value, 2);
}

function fmtPct(value, digits = 2) {
  const number = numeric(value);
  if (number === null) return "-";
  return `${fmtNumber(number, digits)}%`;
}

function fmtDate(value) {
  if (!value) return "-";
  return `${beijingDateTime.format(new Date(value))} 北京时间`;
}

function chartTimeToDate(time) {
  if (typeof time === "number") {
    return new Date(time * 1000);
  }
  if (typeof time === "string") {
    return new Date(time);
  }
  if (time && typeof time === "object" && "year" in time) {
    return new Date(Date.UTC(time.year, time.month - 1, time.day));
  }
  return new Date(NaN);
}

function fmtChartTime(time) {
  const date = chartTimeToDate(time);
  if (Number.isNaN(date.getTime())) return "";
  return `${beijingTickTime.format(date)} 京`;
}

function runmodeText(runmode, dryRun) {
  if (dryRun || runmode === "dry_run") return "模拟盘";
  if (runmode === "live") return "实盘";
  if (runmode === "backtest") return "回测";
  return runmode || "-";
}

function stateText(raw) {
  return {
    running: "运行中",
    stopped: "已停止",
    paused: "暂停中",
    reload_config: "重载配置中",
  }[raw] || raw || "-";
}

function signalText(raw) {
  return {
    trending_long: "趋势做多",
    trending_short: "趋势做空",
    ranging_long: "震荡做多",
    ranging_short: "震荡做空",
  }[raw] || raw || "-";
}

function normalizeTrade(trade, botLabel = "") {
  if (!trade) return null;
  return {
    bot: trade.bot || botLabel,
    pair: trade.pair,
    isShort: Boolean(trade.isShort ?? trade.is_short),
    enterTag: trade.enterTag ?? trade.enter_tag,
    signalText: trade.signalText || signalText(trade.enterTag ?? trade.enter_tag),
    openRate: numeric(trade.openRate ?? trade.open_rate),
    currentRate: numeric(trade.currentRate ?? trade.current_rate),
    stopLoss: numeric(trade.stopLoss ?? trade.stop_loss_abs),
    liquidationPrice: numeric(trade.liquidationPrice ?? trade.liquidation_price),
    takeProfit: numeric(trade.takeProfit ?? trade.take_profit),
    takeProfitReason: trade.takeProfitReason ?? trade.take_profit_reason ?? "",
    takeProfitRoi: numeric(trade.takeProfitRoi ?? trade.take_profit_roi),
    stakeAmount: numeric(trade.stakeAmount ?? trade.stake_amount),
    amount: numeric(trade.amount),
    leverage: numeric(trade.leverage),
    profitAbs: numeric(trade.profitAbs ?? trade.profit_abs ?? trade.total_profit_abs, 0),
    profitPct: numeric(trade.profitPct ?? trade.profit_pct ?? (numeric(trade.profit_ratio) !== null ? Number(trade.profit_ratio) * 100 : null)),
    fundingFees: numeric(trade.fundingFees ?? trade.funding_fees, 0),
    openTimestamp: trade.openTimestamp ?? trade.open_timestamp,
    openDate: trade.openDate ?? trade.open_date,
  };
}

function primaryTrade() {
  const marketTrade = state.market?.openTrades?.[0];
  if (marketTrade) return normalizeTrade(marketTrade, marketTrade.bot);

  const bots = state.summary?.bots || [];
  const preferredKey = state.summary?.comparison?.challengerKey;
  const preferred = bots.find((bot) => bot.key === preferredKey && bot.openTrades?.length);
  const fallback = bots.find((bot) => bot.openTrades?.length);
  if (!preferred && !fallback) return null;
  return normalizeTrade((preferred || fallback).openTrades[0], (preferred || fallback).label);
}

function pctDistance(fromPrice, toPrice) {
  const from = numeric(fromPrice);
  const to = numeric(toPrice);
  if (!from || !to) return null;
  return Math.abs((to - from) / from) * 100;
}

function directionSentence(trade) {
  if (!trade) return "当前没有持仓，机器人在等待下一次入场信号。";
  return trade.isShort
    ? "当前做空，BTC 下跌时盈利；如果 BTC 上涨，仓位会亏损。"
    : "当前做多，BTC 上涨时盈利；如果 BTC 下跌，仓位会亏损。";
}

function comparisonNames() {
  const bots = state.summary?.bots || [];
  const comparison = state.summary?.comparison || {};
  return {
    base: comparison.baseLabel || bots[0]?.label || "基线",
    challenger: comparison.challengerLabel || bots[1]?.label || "对照",
    baseKey: comparison.baseKey || bots[0]?.key || "base",
    challengerKey: comparison.challengerKey || bots[1]?.key || "challenger",
  };
}

function plannedStake(bot) {
  return numeric(bot?.stakeAmount, 0);
}

function legacyNotice(bot) {
  const stake = plannedStake(bot);
  const trade = normalizeTrade(bot?.openTrades?.[0], bot?.label);
  if (!trade || !stake || !trade.stakeAmount || trade.stakeAmount >= stake * 0.5) return "";
  return `当前旧仓约 ${fmtMoney(trade.stakeAmount)}，这笔平仓后，下一笔才按 ${fmtMoney(stake)} 执行。`;
}

function addSeries(chart, type, options) {
  const lib = window.LightweightCharts;
  const constructors = {
    candlestick: lib?.CandlestickSeries,
    line: lib?.LineSeries,
    area: lib?.AreaSeries,
  };

  if (chart.addSeries && constructors[type]) {
    return chart.addSeries(constructors[type], options);
  }
  if (type === "candlestick" && chart.addCandlestickSeries) return chart.addCandlestickSeries(options);
  if (type === "line" && chart.addLineSeries) return chart.addLineSeries(options);
  if (type === "area" && chart.addAreaSeries) return chart.addAreaSeries(options);
  throw new Error("当前图表库不支持需要的图表类型。");
}

function setMarkers(series, markers) {
  const lib = window.LightweightCharts;
  if (series.setMarkers) {
    series.setMarkers(markers);
    return;
  }
  if (lib?.createSeriesMarkers) {
    if (series.__markers?.setMarkers) {
      series.__markers.setMarkers(markers);
    } else {
      series.__markers = lib.createSeriesMarkers(series, markers);
    }
  }
}

function openTradeMarkers(trade, candles) {
  if (!trade?.openTimestamp || !candles.length) return [];
  const openTime = Math.floor(Number(trade.openTimestamp) / 1000);
  const nearest = candles.reduce((best, candle) => (
    Math.abs(candle.time - openTime) < Math.abs(best.time - openTime) ? candle : best
  ), candles[0]);

  if (Math.abs(nearest.time - openTime) > 3 * 60 * 60) {
    return [];
  }

  return [{
    time: nearest.time,
    position: trade.isShort ? "aboveBar" : "belowBar",
    color: trade.isShort ? colors.red : colors.green,
    shape: trade.isShort ? "arrowDown" : "arrowUp",
    text: `${trade.bot || "当前"} 开仓`,
  }];
}

function strategySignalMarkers(markers) {
  if (!state.showStrategySignals) return [];
  return (markers || []).slice(-12).map((marker) => ({
    ...marker,
    text: marker.shape === "arrowDown" ? "做空信号" : "做多信号",
  }));
}

function createChart(container, height) {
  const chart = window.LightweightCharts.createChart(container, {
    ...chartTheme,
    width: container.clientWidth,
    height,
    localization: {
      locale: "zh-CN",
      priceFormatter: (price) => fmtNumber(price, 2),
      timeFormatter: fmtChartTime,
    },
    timeScale: {
      ...chartTheme.timeScale,
      tickMarkFormatter: fmtChartTime,
    },
  });

  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: Math.max(1, Math.floor(container.clientWidth)) });
  });
  observer.observe(container);
  return { chart, observer };
}

function resizeCharts() {
  for (const [id, pack] of Object.entries(state.charts)) {
    const container = id === "btc" ? qs("btcChart") : qs(id);
    if (!container || !pack?.chart) continue;
    const height = container.clientHeight || (id === "btc" ? 468 : 235);
    pack.chart.applyOptions({
      width: Math.max(1, Math.floor(container.clientWidth)),
      height: Math.max(1, Math.floor(height)),
    });
  }
}

function chartData(points, key, field) {
  return (points || [])
    .map((point) => ({ time: point.time, value: numeric(point[key]?.[field]) }))
    .filter((point) => point.time && Number.isFinite(point.value));
}

function initLineChart(id, field, title, options = {}) {
  if (state.charts[id]) return state.charts[id];
  const container = qs(id);
  if (!container || !window.LightweightCharts) return null;
  container.textContent = "";
  const { chart } = createChart(container, 235);
  const names = comparisonNames();
  const base = addSeries(chart, "line", {
    color: options.baseColor || colors.blue,
    lineWidth: 2,
    title: names.base,
    priceLineVisible: false,
  });
  const challenger = addSeries(chart, "line", {
    color: options.challengerColor || colors.green,
    lineWidth: 2,
    title: names.challenger,
    priceLineVisible: false,
  });
  state.charts[id] = { chart, base, challenger, field, title };
  return state.charts[id];
}

function updateChartSeriesLabels() {
  const names = comparisonNames();
  for (const id of ["equityChart", "pnlChart", "drawdownChart", "fundingChart"]) {
    const pack = state.charts[id];
    if (!pack) continue;
    pack.base.applyOptions?.({ title: names.base });
    pack.challenger.applyOptions?.({ title: names.challenger });
  }
}

function ensureCharts() {
  if (!window.LightweightCharts) {
    qs("btcChart").innerHTML = '<div class="empty-state">本地图表库加载失败，请检查 vendor 文件。</div>';
    return;
  }

  if (!state.charts.btc) {
    const container = qs("btcChart");
    const { chart } = createChart(container, container.clientHeight || 468);
    const candles = addSeries(chart, "candlestick", {
      upColor: colors.green,
      downColor: colors.red,
      borderUpColor: colors.green,
      borderDownColor: colors.red,
      wickUpColor: colors.green,
      wickDownColor: colors.red,
      priceLineVisible: false,
    });
    const ema21 = addSeries(chart, "line", { color: colors.cyan, lineWidth: 2, priceLineVisible: false });
    const ema55 = addSeries(chart, "line", { color: colors.amber, lineWidth: 2, priceLineVisible: false });
    const ema200 = addSeries(chart, "line", { color: colors.violet, lineWidth: 2, priceLineVisible: false });
    state.charts.btc = { chart, candles, ema21, ema55, ema200, priceLines: [] };

    const lockView = () => {
      state.btcUserViewLocked = true;
      const button = qs("resetChartButton");
      if (button) button.textContent = "重置视图";
      const hint = qs("signalHint");
      if (hint) hint.textContent = state.showStrategySignals
        ? "正在观察局部走势：自动刷新不会重置缩放；当前只显示最近 12 个策略信号。"
        : "正在观察局部走势：自动刷新不会重置缩放；历史策略信号默认隐藏。";
    };
    container.addEventListener("wheel", lockView, { passive: true });
    container.addEventListener("pointerdown", lockView);
  }

  initLineChart("equityChart", "equity", "策略权益曲线", { baseColor: colors.blue, challengerColor: colors.green });
  initLineChart("pnlChart", "pnl", "浮盈亏曲线", { baseColor: colors.cyan, challengerColor: colors.amber });
  initLineChart("drawdownChart", "drawdown", "回撤曲线", { baseColor: colors.violet, challengerColor: colors.red });
  initLineChart("fundingChart", "fundingFees", "资金费曲线", { baseColor: colors.blue, challengerColor: colors.amber });
}

function updateBtcChart() {
  const market = state.market;
  const chartPack = state.charts.btc;
  if (!market || !chartPack) return;

  qs("marketTitle").textContent = `${market.pair} · ${market.timeframe} · 北京时间 · 数据源 ${market.sourceBot}`;
  const candles = (market.candles || []).filter((row) => (
    row.time
    && Number.isFinite(row.open)
    && Number.isFinite(row.high)
    && Number.isFinite(row.low)
    && Number.isFinite(row.close)
  ));
  chartPack.candles.setData(candles.map((row) => ({
    time: row.time,
    open: row.open,
    high: row.high,
    low: row.low,
    close: row.close,
  })));
  chartPack.ema21.setData(candles.filter((row) => Number.isFinite(row.ema21)).map((row) => ({ time: row.time, value: row.ema21 })));
  chartPack.ema55.setData(candles.filter((row) => Number.isFinite(row.ema55)).map((row) => ({ time: row.time, value: row.ema55 })));
  chartPack.ema200.setData(candles.filter((row) => Number.isFinite(row.ema200)).map((row) => ({ time: row.time, value: row.ema200 })));
  const trade = primaryTrade();
  setMarkers(chartPack.candles, [
    ...strategySignalMarkers(market.markers),
    ...openTradeMarkers(trade, candles),
  ]);

  for (const line of chartPack.priceLines) {
    chartPack.candles.removePriceLine?.(line);
  }
  chartPack.priceLines = [];

  const latest = candles.at(-1);
  const lows = candles.map((row) => row.low).filter(Number.isFinite);
  const highs = candles.map((row) => row.high).filter(Number.isFinite);
  const minVisiblePrice = lows.length ? Math.min(...lows) * 0.95 : null;
  const maxVisiblePrice = highs.length ? Math.max(...highs) * 1.05 : null;
  const priceLines = [
    { price: latest?.close, color: colors.cyan, title: "现价" },
    { price: trade?.openRate, color: colors.blue, title: `${trade?.bot || ""} 开仓` },
    { price: trade?.takeProfit, color: colors.green, title: "预期止盈" },
    { price: trade?.stopLoss, color: colors.amber, title: "止损" },
    { price: trade?.liquidationPrice, color: colors.red, title: "预估强平" },
  ].filter((line) => (
    Number.isFinite(line.price)
    && (minVisiblePrice === null || line.price >= minVisiblePrice)
    && (maxVisiblePrice === null || line.price <= maxVisiblePrice)
  ));

  for (const line of priceLines) {
    const created = chartPack.candles.createPriceLine?.({
      price: line.price,
      color: line.color,
      lineWidth: 1,
      lineStyle: window.LightweightCharts.LineStyle?.Dashed ?? 2,
      axisLabelVisible: true,
      title: line.title,
    });
    if (created) chartPack.priceLines.push(created);
  }

  if (!state.btcUserViewLocked) {
    chartPack.chart.timeScale().fitContent();
  }
}

function updateHistoryCharts() {
  const points = state.history?.points || [];
  for (const id of ["equityChart", "pnlChart", "drawdownChart", "fundingChart"]) {
    const pack = state.charts[id];
    if (!pack) continue;
    pack.base.setData(chartData(points, "base", pack.field));
    pack.challenger.setData(chartData(points, "challenger", pack.field));
    pack.chart.timeScale().fitContent();
  }
}

function renderStatusStrip() {
  const summary = state.summary;
  const bots = summary?.bots || [];
  const allOk = bots.length && bots.every((bot) => bot.ok);
  const modes = bots.map((bot) => `${bot.label} ${stateText(bot.state)} / ${runmodeText(bot.runmode, bot.dryRun)}`).join("，");
  const trade = primaryTrade();
  const latestPrice = state.market?.candles?.at(-1)?.close;
  const history = summary?.history || {};

  qs("statusStrip").innerHTML = [
    ["运行状态", allOk ? "双策略在线" : "有 API 异常", allOk ? "positive" : "negative", modes || "-"],
    ["盘面模式", bots.every((bot) => bot.dryRun) ? "模拟盘" : "包含实盘", bots.every((bot) => bot.dryRun) ? "neutral" : "warn-text", "当前页面只观察，不会启动实盘 bot。"],
    ["BTC 现价", fmtPrice(latestPrice), "neutral", state.market?.lastAnalyzed ? `K线更新时间 ${fmtDate(state.market.lastAnalyzed)}` : "等待 K 线数据"],
    ["历史采样", history.lastSampleAt ? "正常记录中" : "等待第一条", history.lastSampleError ? "negative" : "positive", history.lastSampleError || `${history.sampleIntervalSeconds || 60}s 一次，保留 ${history.retentionDays || 30} 天`],
  ].map(([label, value, klass, note]) => `
    <div class="status-card">
      <div>
        <div class="label">${escapeHtml(label)}</div>
        <div class="status-value ${klass}">${escapeHtml(value)}</div>
        <div class="hint">${escapeHtml(note)}</div>
      </div>
      <span class="status-dot ${klass === "negative" ? "" : klass === "warn-text" ? "warn" : "good"}"></span>
    </div>
  `).join("");

  qs("nowMode").textContent = trade ? (trade.isShort ? "持仓做空" : "持仓做多") : "空仓等待";
}

function renderNowPanel() {
  const bots = state.summary?.bots || [];
  const trade = primaryTrade();
  const current = trade?.currentRate || state.market?.candles?.at(-1)?.close;
  const stopDistance = pctDistance(current, trade?.stopLoss);
  const liqDistance = pctDistance(current, trade?.liquidationPrice);
  const notices = bots.map(legacyNotice).filter(Boolean);

  qs("plainState").textContent = directionSentence(trade);
  qs("nowStack").innerHTML = [
    ["当前价格", fmtPrice(current), "BTC 最新读取价"],
    ["开仓价格", fmtPrice(trade?.openRate), trade ? `${trade.bot} / ${trade.signalText}` : "当前没有持仓"],
    ["预期止盈", fmtPrice(trade?.takeProfit), trade?.takeProfitReason || "趋势单按 ROI 目标，震荡单按布林带目标"],
    ["仓位收益", `${fmtMoney(trade?.profitAbs)} / ${fmtPct(trade?.profitPct)}`, "正数表示这笔仓位当前赚钱"],
    ["止损距离", fmtPct(stopDistance), "离止损越近，风险越高"],
    ["强平距离", fmtPct(liqDistance), "合约风险底线，越远越安全"],
    notices.length ? ["旧仓提示", notices.join("；"), "下一笔新仓会按新的单笔投入执行"] : null,
  ].filter(Boolean).map(([label, value, note]) => `
    <div class="now-item">
      <span class="label">${escapeHtml(label)}</span>
      <strong class="${valueClass(label === "仓位收益" ? trade?.profitAbs : 0)}">${escapeHtml(value)}</strong>
      <span class="hint">${escapeHtml(note)}</span>
    </div>
  `).join("");
}

function riskLevel(distance, goodAt) {
  const number = numeric(distance);
  if (number === null) return { width: 0, klass: "danger" };
  const width = Math.max(0, Math.min(100, (number / goodAt) * 100));
  if (number < goodAt * 0.25) return { width, klass: "danger" };
  if (number < goodAt * 0.55) return { width, klass: "warn" };
  return { width, klass: "" };
}

function renderRiskPanel() {
  const trade = primaryTrade();
  const names = comparisonNames();
  const bot = state.summary?.bots?.find((item) => item.label === trade?.bot) || state.summary?.bots?.find((item) => item.key === names.challengerKey) || state.summary?.bots?.[0];
  const current = trade?.currentRate || state.market?.candles?.at(-1)?.close;
  const stopDistance = pctDistance(current, trade?.stopLoss);
  const liqDistance = pctDistance(current, trade?.liquidationPrice);
  const stake = trade?.stakeAmount;
  const planStake = plannedStake(bot);
  const usedPct = planStake ? (numeric(stake, 0) / planStake) * 100 : null;
  const stopRisk = riskLevel(stopDistance, 8);
  const liqRisk = riskLevel(liqDistance, 25);

  const rows = [
    ["距止损", fmtPct(stopDistance), "止损是策略退出线，越近越需要留意。", stopRisk],
    ["距强平", fmtPct(liqDistance), "强平是合约最坏风险线，应长期保持较远。", liqRisk],
    ["当前仓位", fmtMoney(stake), trade ? `${trade.bot} ${trade.isShort ? "做空" : "做多"}` : "当前没有持仓", { width: Math.min(100, numeric(usedPct, 0)), klass: usedPct > 90 ? "warn" : "" }],
    ["计划单笔投入", fmtMoney(planStake), "当前配置为单策略最多 1 手。", { width: planStake ? 100 : 0, klass: "" }],
    ["旧仓提示", legacyNotice(bot) || "没有检测到小额旧仓。", "如果旧仓存在，下一笔才会使用新资金配置。", { width: legacyNotice(bot) ? 40 : 100, klass: legacyNotice(bot) ? "warn" : "" }],
  ];

  qs("riskList").innerHTML = rows.map(([label, value, note, risk]) => `
    <div class="risk-item">
      <span class="risk-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <span class="hint">${escapeHtml(note)}</span>
      <div class="risk-bar"><div class="risk-fill ${risk.klass}" style="width:${risk.width}%"></div></div>
    </div>
  `).join("");
}

function renderComparison() {
  const comparison = state.summary?.comparison;
  const target = qs("comparisonGrid");
  const names = comparisonNames();
  qs("comparisonLabel").textContent = `${names.challenger} 相对 ${names.base}`;
  qs("comparisonTitle").textContent = `对比条不是求和，是 ${names.challenger} 减去 ${names.base}`;
  const hint = qs("comparisonHint");
  if (hint) hint.textContent = `正数代表 ${names.challenger} 当前读数更高，负数代表更低。`;
  if (!comparison?.ready) {
    target.innerHTML = '<div class="metric-card"><div class="label">对比状态</div><div class="metric-value neutral">等待两边数据</div></div>';
    return;
  }

  const rows = [
    ["总收益差", comparison.profitAllCoinDelta, "USDT", `${names.challenger} 当前总收益减 ${names.base}。`],
    ["策略权益差", comparison.totalBotDelta ?? comparison.valueBotDelta, "USDT", `${names.challenger} bot 管理权益减 ${names.base}。`],
    ["占用资金差", comparison.usedStakeDelta, "USDT", "谁占用资金更多。"],
    ["总交易数差", comparison.tradeCountDelta, "笔", "包含开仓和平仓统计。"],
    ["开仓数差", comparison.openTradesDelta, "手", "当前同时持仓数量差。"],
    ["已平仓差", comparison.closedTradeCountDelta, "笔", "已完成交易数量差。"],
  ];

  target.innerHTML = rows.map(([label, value, suffix, note]) => `
    <div class="metric-card">
      <div class="label">${escapeHtml(label)}</div>
      <div class="metric-value ${valueClass(value)}">${suffix === "USDT" ? fmtMoney(value) : `${fmtNumber(value, 0)} ${suffix}`}</div>
      <div class="hint">${escapeHtml(note)}</div>
    </div>
  `).join("");
}

function renderBotCard(bot) {
  if (!bot.ok) {
    return `
      <article class="bot-card">
        <div class="bot-header">
          <div>
            <div class="bot-title"><span class="status-dot"></span>${escapeHtml(bot.label)}</div>
            <div class="bot-meta">API 不可用</div>
          </div>
        </div>
        <div class="bot-body"><div class="empty-state">${escapeHtml(bot.error || "未知错误")}</div></div>
      </article>
    `;
  }

  const marketTrade = state.market?.openTrades?.find((item) => item.bot === bot.label);
  const trade = normalizeTrade(marketTrade || bot.openTrades?.[0], bot.label);
  const mode = runmodeText(bot.runmode, bot.dryRun);
  const readableState = stateText(bot.state);
  const notice = legacyNotice(bot);
  return `
    <article class="bot-card">
      <div class="bot-header">
        <div>
          <div class="bot-title"><span class="status-dot good"></span>${escapeHtml(bot.label)}</div>
          <div class="bot-meta">${escapeHtml(bot.botName)} / ${escapeHtml(bot.strategy)} / ${readableState} / ${mode}</div>
        </div>
        <div class="bot-meta">${fmtNumber(bot.latencyMs, 0)} ms</div>
      </div>
      <div class="bot-body">
        ${notice ? `<div class="now-item"><span class="label">旧仓提示</span><strong class="warn-text">${escapeHtml(notice)}</strong></div>` : ""}
        <div class="bot-stats">
          ${[
            ["策略权益", fmtMoney(bot.balance?.totalBot)],
            ["总收益", fmtMoney(bot.profitAllCoin), valueClass(bot.profitAllCoin)],
            ["钱包可用", fmtMoney(bot.balance?.freeStake)],
            ["占用资金", fmtMoney(bot.balance?.usedStake ?? bot.totalStake)],
            ["计划单笔", fmtMoney(bot.stakeAmount)],
            ["开仓数量", `${fmtNumber(bot.currentOpenTrades, 0)} / ${fmtNumber(bot.maxOpenTrades, 0)}`],
            ["回撤", `${fmtNumber(bot.currentDrawdown, 3)} / ${fmtMoney(bot.currentDrawdownAbs)}`],
            ["胜率", fmtPct(bot.winrate)],
          ].map(([label, value, klass = ""]) => `
            <div class="mini-stat"><span class="mini-label">${escapeHtml(label)}</span><strong class="${klass}">${escapeHtml(value)}</strong></div>
          `).join("")}
        </div>
        ${trade ? `
          <div class="trade-table">
            <div class="trade-row"><div class="label">当前方向</div><div>${trade.isShort ? "做空，BTC 下跌时盈利" : "做多，BTC 上涨时盈利"}</div></div>
            <div class="trade-row"><div class="label">信号</div><div>${escapeHtml(trade.signalText)}</div></div>
            <div class="trade-row"><div class="label">仓位收益</div><div class="${valueClass(trade.profitAbs)}">${fmtMoney(trade.profitAbs)} / ${fmtPct(trade.profitPct)}</div></div>
          </div>
          <div class="price-grid">
            ${[
              ["开仓价", fmtPrice(trade.openRate)],
              ["现价", fmtPrice(trade.currentRate)],
              ["预期止盈", fmtPrice(trade.takeProfit)],
              ["止损价", fmtPrice(trade.stopLoss)],
              ["预估强平", fmtPrice(trade.liquidationPrice)],
              ["占用资金", fmtMoney(trade.stakeAmount)],
              ["杠杆", trade.leverage ? `${fmtNumber(trade.leverage, 2)}x` : "-"],
              ["资金费", fmtMoney(trade.fundingFees)],
              ["开仓时间", trade.openDate || "-"],
            ].map(([label, value]) => `<div class="price-cell"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
          </div>
        ` : '<div class="empty-state">当前没有持仓，资金处于等待信号状态。</div>'}
      </div>
    </article>
  `;
}

function renderBots() {
  qs("botGrid").innerHTML = (state.summary?.bots || []).map(renderBotCard).join("");
}

function renderTimeline() {
  const items = [];
  const summary = state.summary;
  const trade = primaryTrade();
  const history = summary?.history || {};

  if (trade) {
    items.push(["当前持仓", `${trade.bot} ${trade.isShort ? "做空" : "做多"}，开仓价 ${fmtPrice(trade.openRate)}，现价 ${fmtPrice(trade.currentRate)}。`, ""]);
  } else {
    items.push(["空仓等待", "当前没有持仓，有新交易时脚本会继续通过 Telegram 通知。", ""]);
  }

  for (const bot of summary?.bots || []) {
    const notice = legacyNotice(bot);
    if (notice) items.push([`${bot.label} 旧仓`, notice, "warn"]);
    if (!bot.ok) items.push([`${bot.label} API 异常`, bot.error || "无法读取", "bad"]);
  }

  if (history.lastSampleError) {
    items.push(["历史采样失败", history.lastSampleError, "bad"]);
  } else if (history.lastSampleAt) {
    items.push(["历史采样正常", `最近一次采样 ${fmtDate(history.lastSampleAt)}。`, ""]);
  }

  qs("timeline").innerHTML = items.map(([title, body, klass]) => `
    <div class="timeline-item ${klass}">
      <span class="timeline-marker"></span>
      <div>
        <div class="timeline-title">${escapeHtml(title)}</div>
        <div class="timeline-time">${escapeHtml(body)}</div>
      </div>
    </div>
  `).join("");
}

function renderAll() {
  const generatedAt = state.summary?.generatedAt;
  const bots = state.summary?.bots || [];
  const names = comparisonNames();
  const dashboardTitle = `${names.base} / ${names.challenger} 交易监控`;
  document.title = `${dashboardTitle}面板`;
  const title = qs("dashboardTitle");
  if (title) title.textContent = dashboardTitle;
  const allOk = bots.length > 0 && bots.every((bot) => bot.ok);
  qs("headline").textContent = generatedAt
    ? `更新时间 ${fmtDate(generatedAt)}，当前页面只读取 dry-run 状态，不会改变交易。`
    : "正在读取模拟盘数据...";
  qs("dataHealth").className = `health ${allOk ? "good" : "warn"}`;
  qs("dataHealth").innerHTML = `<span class="health-dot"></span><span>${allOk ? "数据健康" : "部分数据异常"}</span>`;

  renderStatusStrip();
  renderNowPanel();
  renderRiskPanel();
  renderComparison();
  renderBots();
  renderTimeline();
  updateChartSeriesLabels();
  updateBtcChart();
  updateHistoryCharts();
  resizeCharts();
  const signalButton = qs("toggleSignalsButton");
  if (signalButton) signalButton.textContent = state.showStrategySignals ? "隐藏策略信号" : "显示最近信号";
  const hint = qs("signalHint");
  if (hint && !state.btcUserViewLocked) {
    hint.textContent = state.showStrategySignals
      ? "当前只显示最近 12 个策略信号；“趋势做空”代表条件成立，不等于每次都开仓。"
      : "默认隐藏密集策略信号；“趋势做空”只代表条件成立，不等于每次都开仓。";
  }
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} ${response.status} ${response.statusText}`);
  return response.json();
}

async function refreshRealtime() {
  try {
    const [summary, market] = await Promise.all([
      fetchJson("/api/summary"),
      fetchJson("/api/market?timeframe=1h&limit=240"),
    ]);
    state.summary = summary;
    state.market = market;
    state.refreshSeconds = summary.refreshHintSeconds || 15;
    ensureCharts();
    renderAll();
  } catch (error) {
    qs("dataHealth").className = "health warn";
    qs("dataHealth").innerHTML = `<span class="health-dot"></span><span>${escapeHtml(error.message)}</span>`;
  } finally {
    clearTimeout(state.summaryTimer);
    state.summaryTimer = setTimeout(refreshRealtime, state.refreshSeconds * 1000);
  }
}

async function refreshHistory() {
  try {
    state.history = await fetchJson("/api/history?range=30d");
    ensureCharts();
    updateHistoryCharts();
  } catch (error) {
    console.warn("history refresh failed", error);
  } finally {
    clearTimeout(state.historyTimer);
    state.historyTimer = setTimeout(refreshHistory, 60_000);
  }
}

function init() {
  qs("refreshButton").addEventListener("click", () => {
    refreshRealtime();
    refreshHistory();
  });
  qs("toggleSignalsButton").addEventListener("click", () => {
    state.showStrategySignals = !state.showStrategySignals;
    updateBtcChart();
    renderAll();
  });
  qs("resetChartButton").addEventListener("click", () => {
    state.btcUserViewLocked = false;
    state.charts.btc?.chart?.timeScale().fitContent();
    const hint = qs("signalHint");
    if (hint) hint.textContent = state.showStrategySignals
      ? "当前只显示最近 12 个策略信号；“趋势做空”代表条件成立，不等于每次都开仓。"
      : "默认隐藏密集策略信号；“趋势做空”只代表条件成立，不等于每次都开仓。";
  });
  ensureCharts();
  refreshRealtime();
  refreshHistory();
  window.addEventListener("resize", resizeCharts);
}

document.addEventListener("DOMContentLoaded", init);
