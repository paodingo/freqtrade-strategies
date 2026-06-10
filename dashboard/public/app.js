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
  rightPriceScale: { visible: true, borderColor: "rgba(255, 255, 255, 0.10)" },
  timeScale: { borderColor: "rgba(255, 255, 255, 0.10)", timeVisible: true },
};

const colors = {
  green: "#42d27d",
  red: "#ff6b6b",
  amber: "#f4c35d",
  cyan: "#55c8e8",
  blue: "#78a8ff",
  entry: "#ff8bd2",
  violet: "#b49aff",
  muted: "#7f8a96",
};

const entryLineColors = [colors.entry, colors.violet, colors.blue];

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
  chartTimeframe: "15m",
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
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
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
  return beijingTickTime.format(date);
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

function chartOpenTrades() {
  const marketTrades = state.market?.openTrades;
  if (Array.isArray(marketTrades) && marketTrades.length) {
    return marketTrades.map((trade) => normalizeTrade(trade, trade.bot)).filter(Boolean);
  }

  return (state.summary?.bots || []).flatMap((bot) => (
    Array.isArray(bot.openTrades)
      ? bot.openTrades.map((trade) => normalizeTrade(trade, bot.label))
      : []
  )).filter(Boolean);
}

function entryLineColor(index) {
  return entryLineColors[index % entryLineColors.length];
}

function pctDistance(fromPrice, toPrice) {
  const from = numeric(fromPrice);
  const to = numeric(toPrice);
  if (!from || !to) return null;
  return Math.abs((to - from) / from) * 100;
}

function directionSentence(trade) {
  if (!trade) return "当前没有持仓，机器人在等待下一次入场信号。";
  return trade.isShort ? "当前做空" : "当前做多";
}

function directionLabel(trade) {
  return trade?.isShort ? "做空" : "做多";
}

function positionsSentence(trades) {
  if (!trades.length) return "当前没有持仓，机器人在等待下一次入场信号。";
  return trades.map((trade) => `${trade.bot || "策略"} ${directionLabel(trade)}`).join("；");
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

function markerCollisionKey(marker) {
  return `${marker.time}:${marker.position}`;
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

function strategySignalMarkers(markers, occupiedMarkers = []) {
  if (!state.showStrategySignals) return [];
  const occupiedKeys = new Set(occupiedMarkers.map(markerCollisionKey));
  return (markers || [])
    .map((marker) => ({
      ...marker,
      text: marker.kind === "auxiliary"
        ? (marker.shape === "arrowDown" ? "辅助卖出观察" : "辅助买入观察")
        : (marker.shape === "arrowDown" ? "做空信号" : "做多信号"),
    }))
    .filter((marker) => !occupiedKeys.has(markerCollisionKey(marker)))
    .slice(-12);
}

function currentSignalMode() {
  return state.market?.signalInfo?.mode || state.market?.signalMode || "none";
}

function signalButtonText() {
  const mode = currentSignalMode();
  if (mode === "none") return "当前周期无信号";
  if (state.showStrategySignals) return mode === "auxiliary" ? "隐藏辅助信号" : "隐藏策略信号";
  return mode === "auxiliary" ? "显示辅助信号" : "显示策略信号";
}

function signalHintText() {
  const mode = currentSignalMode();
  if (mode === "strategy") {
    return state.showStrategySignals
      ? `${state.market?.timeframe || ""} 显示最近 12 个真实策略信号；做多/做空都支持，但不等于每次都会成交。`
      : `${state.market?.timeframe || ""} 当前有真实策略信号；默认隐藏，打开后显示最近 12 个。`;
  }
  if (mode === "auxiliary") {
    return state.showStrategySignals
      ? "当前显示 5m/15m 辅助买入/卖出观察信号；它只是看盘参考，不会直接触发 bot 下单。"
      : "5m 可显示辅助观察信号；真实下单仍以进攻策略的 15m 策略信号和风控为准。";
  }
  return "当前周期不显示入场信号；切到 15m 看进攻策略真实信号，切到 5m 看辅助观察信号。";
}

function updateSignalControls() {
  const signalButton = qs("toggleSignalsButton");
  const mode = currentSignalMode();
  if (signalButton) {
    signalButton.textContent = signalButtonText();
    signalButton.disabled = mode === "none";
    signalButton.setAttribute("aria-disabled", mode === "none" ? "true" : "false");
  }
  const hint = qs("signalHint");
  if (hint && !state.btcUserViewLocked) {
    hint.textContent = signalHintText();
  }
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
      lastValueVisible: false,
    });
    const ema21 = addSeries(chart, "line", { color: colors.cyan, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    const ema55 = addSeries(chart, "line", { color: colors.amber, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    const ema200 = addSeries(chart, "line", { color: colors.violet, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
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

  const source = market.fallback ? `${market.sourceBot} 行情` : `${market.sourceBot} 策略数据`;
  qs("marketTitle").textContent = `${market.pair} · ${market.timeframe} · 北京时间 · ${source}`;
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
  const openTrades = chartOpenTrades();
  const openMarkers = openTrades.flatMap((openTrade) => openTradeMarkers(openTrade, candles));
  setMarkers(chartPack.candles, [
    ...strategySignalMarkers(market.markers, openMarkers),
    ...openMarkers,
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
  const entryPriceLines = openTrades.map((chartTrade, index) => ({
    price: chartTrade.openRate,
    color: entryLineColor(index),
    title: `${chartTrade.bot || "策略"} 开仓 ${fmtPrice(chartTrade.openRate)}`,
  }));
  const priceLines = [
    { price: latest?.close, color: colors.cyan, title: `现价 ${fmtPrice(latest?.close)}` },
    ...entryPriceLines,
    { price: trade?.takeProfit, color: colors.green, title: `${trade?.bot || "策略"} 止盈 ${fmtPrice(trade?.takeProfit)}` },
    { price: trade?.stopLoss, color: colors.amber, title: `${trade?.bot || "策略"} 止损 ${fmtPrice(trade?.stopLoss)}` },
    { price: trade?.liquidationPrice, color: colors.red, title: `${trade?.bot || "策略"} 强平 ${fmtPrice(trade?.liquidationPrice)}` },
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
  const trades = chartOpenTrades();
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

  qs("nowMode").textContent = trades.length ? `${trades.length} 笔持仓` : "空仓等待";
}

function renderNowPanel() {
  const bots = state.summary?.bots || [];
  const trades = chartOpenTrades();
  const latestPrice = state.market?.candles?.at(-1)?.close;
  const notices = bots.map(legacyNotice).filter(Boolean);
  const rows = [
    ["当前价格", fmtPrice(latestPrice), "BTC 最新读取价"],
    ...trades.flatMap((trade) => {
      const current = trade.currentRate || latestPrice;
      const stopDistance = pctDistance(current, trade.stopLoss);
      const liqDistance = pctDistance(current, trade.liquidationPrice);
      return [
        [`${trade.bot || "策略"} ${directionLabel(trade)}`, `开仓 ${fmtPrice(trade.openRate)} / 现价 ${fmtPrice(current)}`, `${trade.signalText} / 收益 ${fmtMoney(trade.profitAbs)} / ${fmtPct(trade.profitPct)}`],
        [`${trade.bot || "策略"} 风险线`, `止损 ${fmtPct(stopDistance)} / 强平 ${fmtPct(liqDistance)}`, `止盈 ${fmtPrice(trade.takeProfit)} / ${trade.takeProfitReason || "按策略目标计算"}`],
      ];
    }),
    notices.length ? ["旧仓提示", notices.join("；"), "下一笔新仓会按新的单笔投入执行"] : null,
  ].filter(Boolean);

  qs("plainState").textContent = positionsSentence(trades);
  qs("nowStack").innerHTML = rows.map(([label, value, note]) => `
    <div class="now-item">
      <span class="label">${escapeHtml(label)}</span>
      <strong class="${valueClass(label.endsWith("做多") || label.endsWith("做空") ? trades.find((item) => `${item.bot || "策略"} ${directionLabel(item)}` === label)?.profitAbs : 0)}">${escapeHtml(value)}</strong>
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
  const trades = chartOpenTrades();
  const bots = state.summary?.bots || [];
  const latestPrice = state.market?.candles?.at(-1)?.close;
  const rows = trades.flatMap((trade) => {
    const bot = bots.find((item) => item.label === trade.bot);
    const current = trade.currentRate || latestPrice;
    const stopDistance = pctDistance(current, trade.stopLoss);
    const liqDistance = pctDistance(current, trade.liquidationPrice);
    const planStake = plannedStake(bot);
    const usedPct = planStake ? (numeric(trade.stakeAmount, 0) / planStake) * 100 : null;

    return [
      [`${trade.bot || "策略"} 止损`, fmtPct(stopDistance), `${directionLabel(trade)} / 开仓 ${fmtPrice(trade.openRate)} / 收益 ${fmtMoney(trade.profitAbs)}`, riskLevel(stopDistance, 8)],
      [`${trade.bot || "策略"} 强平`, fmtPct(liqDistance), `${directionLabel(trade)} / 当前仓位 ${fmtMoney(trade.stakeAmount)}`, riskLevel(liqDistance, 25)],
      [`${trade.bot || "策略"} 仓位`, fmtMoney(trade.stakeAmount), `计划单笔 ${fmtMoney(planStake)} / 使用 ${fmtPct(usedPct)}`, { width: Math.min(100, numeric(usedPct, 0)), klass: usedPct > 90 ? "warn" : "" }],
    ];
  });

  if (!rows.length) {
    rows.push(["当前仓位", "空仓", "没有检测到未平仓。", { width: 100, klass: "" }]);
  }

  for (const bot of bots) {
    const notice = legacyNotice(bot);
    if (notice) rows.push([`${bot.label} 旧仓`, notice, "下一笔新仓会按新的单笔投入执行。", { width: 40, klass: "warn" }]);
  }

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

function levelClass(level) {
  return {
    good: "positive",
    warning: "warn-text",
    danger: "negative",
  }[level] || "neutral";
}

function levelText(level) {
  return {
    good: "健康",
    warning: "观察",
    danger: "警惕",
    neutral: "中性",
  }[level] || "中性";
}

function levelDotClass(level) {
  return {
    good: "good",
    warning: "warn",
    danger: "",
    neutral: "neutral",
  }[level] || "neutral";
}

function renderInsightMetrics(items = []) {
  if (!items.length) return "";
  return `
    <div class="insight-metrics">
      ${items.map((item) => `
        <div class="insight-metric">
          <span>${escapeHtml(item.label)}</span>
          <strong class="${levelClass(item.level)}">${escapeHtml(item.value)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderInsightList(entries = [], type = "summary") {
  if (!entries.length) return '<div class="empty-state">等待更多样本。</div>';
  return `
    <div class="insight-list">
      ${entries.map((entry) => {
        const level = entry.level || entry.severity || "neutral";
        const secondary = type === "position"
          ? `${entry.direction || "-"} / ${fmtMoney(entry.stakeAmount)} / 止损 ${fmtPct(entry.stopDistancePct)} / 强平 ${fmtPct(entry.liquidationDistancePct)}`
          : `资金费 ${fmtMoney(entry.fundingFees)} / 资金费占浮盈亏 ${fmtPct(entry.fundingToPnlPct)} / ${entry.tradesPerDay === null || entry.tradesPerDay === undefined ? entry.frequencyText : `${fmtNumber(entry.tradesPerDay, 2)} 笔/天`}`;
        return `
          <div class="insight-row">
            <span class="status-dot ${levelDotClass(level)}"></span>
            <div>
              <strong>${escapeHtml(entry.label)}</strong>
              <span>${escapeHtml(secondary)}</span>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderInterpretation() {
  const interpretation = state.summary?.interpretation;
  const target = qs("interpretationGrid");
  if (!target) return;

  const timeframeHint = qs("timeframeHint");
  if (timeframeHint) {
    timeframeHint.textContent = interpretation?.timeframes?.summary || "当前策略以 1h 为主交易周期，4h 用于趋势和市场状态过滤。";
  }

  if (!interpretation) {
    target.innerHTML = '<article class="insight-card"><div class="empty-state">正在整理交易解读。</div></article>';
    return;
  }

  const cards = [
    {
      label: "当前持仓",
      title: interpretation.position?.title,
      level: interpretation.position?.level,
      body: interpretation.position?.body,
      content: renderInsightList(interpretation.position?.entries || [], "position"),
    },
    {
      label: "成本视角",
      title: interpretation.cost?.title,
      level: interpretation.cost?.level,
      body: interpretation.cost?.body,
      content: renderInsightList(interpretation.cost?.entries || [], "cost"),
    },
    {
      label: "整体判断",
      title: interpretation.comparison?.title,
      level: interpretation.comparison?.level,
      body: interpretation.comparison?.body,
      content: renderInsightMetrics(interpretation.comparison?.items || []),
    },
  ];

  target.innerHTML = cards.map((card) => `
    <article class="insight-card ${card.level || "neutral"}">
      <div class="insight-topline">
        <span class="section-label">${escapeHtml(card.label)}</span>
        <span class="insight-badge ${levelClass(card.level)}">${escapeHtml(levelText(card.level))}</span>
      </div>
      <h3>${escapeHtml(card.title || "-")}</h3>
      <p>${escapeHtml(card.body || "-")}</p>
      ${card.content}
    </article>
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
            <div class="trade-row"><div class="label">当前方向</div><div>${trade.isShort ? "做空" : "做多"}</div></div>
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
  renderInterpretation();
  renderComparison();
  renderBots();
  renderTimeline();
  updateChartSeriesLabels();
  updateBtcChart();
  updateHistoryCharts();
  resizeCharts();
  const signalButton = qs("toggleSignalsButton");
  if (signalButton) signalButton.textContent = state.showStrategySignals ? "隐藏策略信号" : "显示最近信号";
  updateTimeframeButtons();
  const hint = qs("signalHint");
  if (hint && !state.btcUserViewLocked) {
    hint.textContent = state.showStrategySignals
      ? "当前只显示最近 12 个策略信号；“趋势做空”代表条件成立，不等于每次都开仓。"
      : "默认隐藏密集策略信号；“趋势做空”只代表条件成立，不等于每次都开仓。";
  }
  updateSignalControls();
}

function updateTimeframeButtons() {
  for (const button of document.querySelectorAll(".timeframe-button")) {
    const active = button.dataset.timeframe === state.chartTimeframe;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} ${response.status} ${response.statusText}`);
  return response.json();
}

async function refreshRealtime() {
  try {
    const marketParams = new URLSearchParams({ timeframe: state.chartTimeframe, limit: "240" });
    const [summary, market] = await Promise.all([
      fetchJson("/api/summary"),
      fetchJson(`/api/market?${marketParams.toString()}`),
    ]);
    state.summary = summary;
    state.market = market;
    if (summary.chart?.defaultTimeframe && !state.chartTimeframe) {
      state.chartTimeframe = summary.chart.defaultTimeframe;
    }
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
    if (currentSignalMode() === "none") return;
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
    updateSignalControls();
  });
  for (const button of document.querySelectorAll(".timeframe-button")) {
    button.addEventListener("click", () => {
      const next = button.dataset.timeframe;
      if (!next || next === state.chartTimeframe) return;
      state.chartTimeframe = next;
      state.btcUserViewLocked = false;
      updateTimeframeButtons();
      refreshRealtime();
    });
  }
  updateTimeframeButtons();
  ensureCharts();
  refreshRealtime();
  refreshHistory();
  window.addEventListener("resize", resizeCharts);
}

document.addEventListener("DOMContentLoaded", init);
