"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const PROJECT_DIR = path.resolve(__dirname, "..");
const PUBLIC_FILES = [
  "dashboard/public/index.html",
  "dashboard/public/app.js",
  "dashboard/lib/interpretation.js",
];

test("dashboard public UI does not hardcode strategy version labels", () => {
  const versionPattern = /\bV\d+(?:\.\d+)?\b/g;
  const violations = [];

  for (const relativePath of PUBLIC_FILES) {
    const absolutePath = path.join(PROJECT_DIR, relativePath);
    const content = fs.readFileSync(absolutePath, "utf8");
    const matches = content.match(versionPattern) || [];
    for (const match of matches) {
      violations.push(`${relativePath}: ${match}`);
    }
  }

  assert.deepEqual(
    violations,
    [],
    "Dashboard public assets must render strategy labels from /api/summary instead of hardcoding versions.",
  );
});

test("BTC main chart overlays closed trade entry and exit markers without signal arrows", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");

  assert.match(html, /legend-marker historical-entry/);
  assert.match(html, /legend-marker historical-exit/);
  assert.match(css, /\.legend-marker\.historical-entry/);
  assert.match(css, /\.legend-marker\.historical-exit/);
  assert.match(app, /function historicalTradeMarkers\(trades, candles\)/);
  assert.match(app, /state\.trades\?\.trades/);
  assert.match(app, /trade\.openTimestamp/);
  assert.match(app, /trade\.closeTimestamp/);
  assert.match(app, /position:\s*"atPriceMiddle"/);
  assert.match(app, /price:\s*trade\.openRate/);
  assert.match(app, /price:\s*trade\.closeRate/);
  assert.match(app, /shape:\s*"square"/);
  assert.match(app, /shape:\s*"circle"/);

  const markerFunction = app.slice(
    app.indexOf("function historicalTradeMarkers"),
    app.indexOf("function strategySignalMarkers"),
  );
  assert.doesNotMatch(markerFunction, /arrowUp|arrowDown/);
});

test("BTC real trade markers are anchored to trade prices, not candle high low positions", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const openTradeMarkerFunction = app.slice(
    app.indexOf("function openTradeMarkers"),
    app.indexOf("function historicalTradeMarkers"),
  );
  const historicalMarkerFunction = app.slice(
    app.indexOf("function historicalTradeMarkers"),
    app.indexOf("function strategySignalMarkers"),
  );

  assert.match(openTradeMarkerFunction, /position:\s*"atPriceMiddle"/);
  assert.match(openTradeMarkerFunction, /price:\s*trade\.openRate/);
  assert.doesNotMatch(openTradeMarkerFunction, /aboveBar|belowBar|arrowUp|arrowDown/);
  assert.match(historicalMarkerFunction, /position:\s*"atPriceMiddle"/);
  assert.match(historicalMarkerFunction, /price:\s*trade\.openRate/);
  assert.match(historicalMarkerFunction, /price:\s*trade\.closeRate/);
});

test("BTC chart crosshair does not snap real trade marker reads to candle close", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");

  assert.match(app, /crosshair:\s*\{/);
  assert.match(app, /mode:\s*window\.LightweightCharts\.CrosshairMode\?\.Normal/);
});

test("BTC trade marker legend explains shape and color meanings", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");

  assert.match(html, /方块=真实开仓/);
  assert.match(html, /圆点=真实平仓/);
  assert.match(html, /绿色=做多\/盈利/);
  assert.match(html, /红色=做空\/亏损/);
});

test("BTC chart draws risk price lines for every open trade", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const updateBtcChart = app.slice(app.indexOf("function updateBtcChart"), app.indexOf("function updateHistoryCharts"));

  assert.match(app, /function tradeRiskPriceLines\(trade\)/);
  assert.match(updateBtcChart, /const riskPriceLines = openTrades\.flatMap\(tradeRiskPriceLines\)/);
  assert.match(updateBtcChart, /\.\.\.riskPriceLines/);
  assert.doesNotMatch(updateBtcChart, /\{ price: trade\?\.takeProfit/);
  assert.doesNotMatch(updateBtcChart, /\{ price: trade\?\.stopLoss/);
  assert.doesNotMatch(updateBtcChart, /\{ price: trade\?\.liquidationPrice/);
});

test("BTC real trade markers keep chart labels concise", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const openTradeMarkerFunction = app.slice(
    app.indexOf("function openTradeMarkers"),
    app.indexOf("function historicalTradeMarkers"),
  );
  const historicalMarkerFunction = app.slice(
    app.indexOf("function historicalTradeMarkers"),
    app.indexOf("function strategySignalMarkers"),
  );
  const markerTextFunction = app.slice(
    app.indexOf("function tradeMarkerText"),
    app.indexOf("function openTradeMarkers"),
  );

  assert.match(app, /function tradeMarkerText\(trade, kind\)/);
  assert.match(app, /if \(kind === "平仓"\) return "平仓"/);
  assert.match(app, /return trade\?\.isShort \? "卖出" : "买入"/);
  assert.match(openTradeMarkerFunction, /text:\s*tradeMarkerText\(trade, "当前开仓"\)/);
  assert.match(historicalMarkerFunction, /text:\s*tradeMarkerText\(trade, "开仓"\)/);
  assert.match(historicalMarkerFunction, /text:\s*tradeMarkerText\(trade, "平仓"\)/);
  assert.doesNotMatch(markerTextFunction, /fmtPrice\(price\)/);
  assert.doesNotMatch(markerTextFunction, /fmtMarkerTime\(timestamp\)/);
});

test("BTC chart does not use a separate trade marker detail strip", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");

  assert.doesNotMatch(html, /id="tradeMarkerDetail"/);
  assert.doesNotMatch(css, /\.trade-marker-detail/);
  assert.doesNotMatch(app, /function openTradeEvents\(openTrades, candles\)/);
  assert.doesNotMatch(app, /function historicalTradeEvents\(trades, candles\)/);
  assert.doesNotMatch(app, /function renderTradeMarkerDetail\(events, activeTime/);
  assert.doesNotMatch(app, /function tradeMarkerEventLabel\(event\)/);
  assert.doesNotMatch(app, /state\.btcTradeEvents/);
});

test("BTC price lines stay visible across timeframe changes when values exist", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const updateBtcChart = app.slice(app.indexOf("function updateBtcChart"), app.indexOf("function updateHistoryCharts"));

  assert.match(updateBtcChart, /\]\.filter\(\(line\) => Number\.isFinite\(line\.price\)\)/);
  assert.doesNotMatch(updateBtcChart, /minVisiblePrice|maxVisiblePrice/);
});

test("BTC main chart includes dashed price line legend entries", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");

  assert.match(html, /id="priceLineLegend"/);
  assert.match(css, /\.legend-line\.dashed/);
  for (const className of ["current-price", "entry-price", "take-profit", "stop-loss", "liquidation"]) {
    assert.match(html, new RegExp(`legend-line dashed ${className}`));
  }
  assert.match(css, /--entry:\s*#ff8bd2/);
  assert.match(app, /entry:\s*"#ff8bd2"/);
  assert.match(app, /function chartOpenTrades\(\)/);
  assert.match(app, /const openTrades = chartOpenTrades\(\)/);
  assert.match(app, /const openMarkers = openTrades\.flatMap\(\(openTrade\) => openTradeMarkers\(openTrade, candles\)\)/);
  assert.match(app, /const historicalMarkers = historicalTradeMarkers\(state\.trades\?\.trades, candles\)/);
  assert.match(app, /\.\.\.strategySignalMarkers\(market\.markers, \[\.\.\.openMarkers, \.\.\.historicalMarkers\]\)/);
  assert.match(app, /\.\.\.historicalMarkers/);
  assert.match(app, /\.\.\.openMarkers/);
  assert.match(app, /const entryPriceLines = openTrades\.map/);
  assert.match(app, /color:\s*entryLineColor\(index\)/);
  assert.match(app, /title:\s*`\$\{chartTrade\.bot \|\| "策略"\} 开仓 \$\{fmtPrice\(chartTrade\.openRate\)\}`/);
  assert.match(app, /title:\s*`现价 \$\{fmtPrice\(latestPrice\)\}`/);
});

test("BTC strategy signal markers keep arrows but omit repeated text labels", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");

  assert.match(app, /function strategySignalMarkers\(markers, occupiedMarkers = \[\]\)/);
  assert.match(app, /text:\s*""/);
  assert.doesNotMatch(app, /做空信号|做多信号|辅助卖出观察|辅助买入观察/);
});

test("dashboard keeps position direction labels concise", () => {
  const files = [
    "dashboard/public/app.js",
    "dashboard/server.js",
  ];

  for (const relativePath of files) {
    const content = fs.readFileSync(path.join(PROJECT_DIR, relativePath), "utf8");
    assert.doesNotMatch(content, /下跌时盈利|上涨时盈利|仓位会亏损/);
  }
});

test("dashboard formats trade open time from timestamp instead of raw UTC date", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");

  assert.match(app, /function fmtTradeOpenTime\(trade\)/);
  assert.match(app, /trade\?\.openTimestamp/);
  assert.match(app, /openDate\.replace\(" ", "T"\)/);
  assert.match(app, /\["开仓时间", fmtTradeOpenTime\(trade\)\]/);
  assert.doesNotMatch(app, /\["开仓时间", trade\.openDate \|\| "-"\]/);
});

test("dashboard now and risk panels render all open strategy positions", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const nowPanel = app.slice(app.indexOf("function renderNowPanel"), app.indexOf("function riskLevel"));
  const riskPanel = app.slice(app.indexOf("function renderRiskPanel"), app.indexOf("function renderComparison"));

  assert.match(app, /function chartOpenTrades\(\)/);
  assert.match(app, /function positionsSentence\(trades\)/);
  assert.match(app, /function renderPositionComparison\(\)/);
  assert.match(app, /function renderRiskComparison\(\)/);
  assert.match(app, /qs\("plainState"\)\.textContent = positionsSentence\(trades\)/);
  assert.match(app, /renderPositionComparison\(\)/);
  assert.match(app, /renderRiskComparison\(\)/);
  assert.match(css, /\.comparison-mini-grid/);
  assert.match(css, /\.comparison-text-row/);
  assert.doesNotMatch(nowPanel, /primaryTrade\(\)/);
  assert.doesNotMatch(riskPanel, /primaryTrade\(\)/);
});

test("dashboard now panel explains each strategy's latest trade after it closes", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");
  const nowPanel = app.slice(app.indexOf("function renderNowPanel"), app.indexOf("function riskLevel"));
  const realtime = app.slice(app.indexOf("async function refreshRealtime"), app.indexOf("async function refreshHistory"));

  assert.match(server, /function formatExitReason\(reason\)/);
  assert.match(server, /exitReason:\s*trade\.exit_reason/);
  assert.match(server, /exitReasonText:\s*formatExitReason\(trade\.exit_reason/);
  assert.match(app, /recentTrades:\s*null/);
  assert.match(app, /function latestTradeNarrativeForBot\(bot\)/);
  assert.match(app, /function latestTradeNarratives\(\)/);
  assert.match(app, /function renderLatestTradeNarratives\(\)/);
  assert.match(app, /state\.summary\?\.bots \|\| \[\]/);
  assert.match(app, /latestTradeNarrativeForBot\(bot\)/);
  assert.match(app, /function tradeEntryReason\(trade\)/);
  assert.match(app, /function tradeExitReason\(trade\)/);
  assert.match(nowPanel, /renderLatestTradeNarratives\(\)/);
  assert.match(realtime, /fetchJson\("\/api\/trades\?limit=20"\)/);
  assert.match(realtime, /state\.recentTrades = recentTrades/);
  assert.match(css, /\.trade-narrative/);
  assert.match(css, /\.trade-narrative-grid/);
});

test("strategy comparison shows current metric bars and moves trend charts to the bottom", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");

  assert.match(html, /id="comparisonSnapshotGrid"/);
  assert.match(css, /\.comparison-snapshot-grid/);
  assert.match(css, /\.comparison-bar-card/);
  assert.match(css, /\.comparison-bar-track\s*\{[\s\S]*?display:\s*block/);
  assert.match(css, /\.comparison-bar-fill\s*\{[\s\S]*?display:\s*block/);
  assert.match(css, /\.comparison-axis-track/);
  assert.match(css, /\.comparison-axis-zero/);
  assert.match(app, /function renderSignedAxisRows/);
  assert.match(app, /function comparisonSnapshotRows\(\)/);
  assert.match(app, /function renderComparisonBarCard/);
  assert.match(app, /axis:\s*"signed"/);
  assert.match(app, /qs\("comparisonSnapshotGrid"\)\.innerHTML/);

  assert.match(html, /id="comparisonChartGrid"/);
  for (const id of ["equityChart", "pnlChart", "drawdownChart", "fundingChart"]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.ok(
    html.indexOf('id="comparisonSnapshotGrid"') < html.indexOf('id="comparisonGrid"'),
    "Current snapshot charts should render before numeric delta cards.",
  );
  assert.ok(
    html.indexOf('id="comparisonChartGrid"') > html.indexOf('id="botGrid"'),
    "Historical trend charts should sit below the bot detail cards.",
  );
  assert.match(html, /class="chart-grid comparison-chart-grid"/);
  assert.match(css, /\.comparison-chart-grid/);
  assert.match(app, /function renderComparisonChartTitles\(\)/);
  assert.match(app, /renderComparisonChartTitles\(\)/);
});

test("dashboard exposes and renders closed trade result chart", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");

  assert.match(html, /id="tradeResultChart"/);
  assert.match(html, /id="tradeResultChartTitle"/);
  assert.match(css, /\.trade-result-tile/);
  assert.match(app, /trades:\s*null/);
  assert.match(app, /function updateTradeResultChart\(\)/);
  assert.match(app, /function tradeResultData\(trades, key\)/);
  assert.match(app, /fetchJson\("\/api\/trades\?limit=200"\)/);
  assert.match(app, /for \(const id of \["equityChart", "pnlChart", "drawdownChart", "fundingChart", "tradeResultChart"\]/);
  assert.match(server, /async function handleApiTrades\(res, url\)/);
  assert.match(server, /url\.pathname === "\/api\/trades"/);
});

test("dashboard refreshes BTC price faster and prefers live trade current rates", () => {
  const config = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/lib/config.js"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");

  assert.match(config, /REFRESH_HINT_SECONDS = Number\(process\.env\.REFRESH_HINT_SECONDS \|\| 5\)/);
  assert.match(server, /async function fetchBinanceFuturesTicker\(pair\)/);
  assert.match(server, /ticker:\s*tickerPrice/);
  assert.match(app, /function currentBtcPrice\(\)/);
  assert.match(app, /function currentBtcPriceNote\(\)/);
  assert.match(app, /state\.market\?\.ticker\?\.price/);
  assert.match(app, /state\.market\?\.ticker\?\.updatedAt/);
  assert.match(app, /chartOpenTrades\(\)\.map\(\(trade\) => trade\.currentRate\)/);
  assert.match(app, /\["BTC 现价", fmtPrice\(latestPrice\)/);
  assert.match(app, /currentBtcPriceNote\(\)/);
  assert.match(app, /const latestPrice = currentBtcPrice\(\)/);
  assert.match(app, /title:\s*`现价 \$\{fmtPrice\(latestPrice\)\}`/);
  assert.doesNotMatch(app, /北京时间/);
});

test("timeline header absorbs live price and history sampling status", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const timelineMeta = app.slice(app.indexOf("function renderTimelineMeta"), app.indexOf("function renderMetricRow"));

  assert.doesNotMatch(html, /id="statusStrip"/);
  assert.match(html, /id="timelineMeta"/);
  assert.match(timelineMeta, /\["BTC 现价", fmtPrice\(latestPrice\)/);
  assert.match(timelineMeta, /\["历史采样", history\.lastSampleAt/);
  assert.match(timelineMeta, /记录权益\/收益\/回撤\/持仓/);
  assert.doesNotMatch(timelineMeta, /运行状态|盘面模式|allOk|modes|runmodeText/);
  assert.match(css, /\.timeline-meta/);
  assert.doesNotMatch(css, /\.status-strip/);
});

test("dashboard exposes Binance futures alpha risk layer", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");

  assert.match(server, /createBinanceFuturesAlphaFetcher/);
  assert.match(server, /async function handleApiAlphaRisk\(res\)/);
  assert.match(server, /function handleApiAlphaRiskHistory\(res, url\)/);
  assert.match(server, /url\.pathname === "\/api\/alpha-risk"/);
  assert.match(server, /url\.pathname === "\/api\/alpha-risk\/history"/);
  assert.match(server, /monitorStore\.recordAlphaRiskSample/);
  assert.match(server, /fetchAlphaRisk\(\{ pair: DEFAULT_PAIR \}\)/);
  assert.match(html, /id="contractIntelPanel"/);
  assert.match(html, /id="alphaRiskTitle"/);
  assert.match(html, /id="alphaRiskSummary"/);
  assert.match(html, /id="alphaRiskGrid"/);
  assert.match(css, /\.contract-intel-panel/);
  assert.match(css, /\.alpha-risk-grid/);
  assert.match(app, /alphaRisk:\s*null/);
  assert.match(app, /function renderAlphaRiskPanel\(\)/);
  assert.match(app, /fetchJson\("\/api\/alpha-risk"\)/);
  assert.match(app, /state\.alphaRisk = alphaRisk/);
  assert.match(app, /renderAlphaRiskPanel\(\)/);
  assert.match(app, /Funding Rate/);
  assert.match(app, /Open Interest/);
  assert.match(app, /Top Trader/);
  assert.match(app, /Taker Flow/);
});

test("dashboard exposes regime router observation layer", () => {
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");
  const store = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/lib/monitor_store.js"), "utf8");

  assert.match(server, /classifyRegimeWindow/);
  assert.match(server, /async function handleApiRegimeRouter\(res\)/);
  assert.match(server, /function handleApiRegimeRouterHistory\(res, url\)/);
  assert.match(server, /url\.pathname === "\/api\/regime-router"/);
  assert.match(server, /url\.pathname === "\/api\/regime-router\/history"/);
  assert.match(server, /monitorStore\.recordRegimeRouterSample/);
  assert.match(store, /CREATE TABLE IF NOT EXISTS regime_router_samples/);
  assert.match(store, /recordRegimeRouterSample/);
  assert.match(store, /readRegimeRouterSamples/);
  assert.match(html, /id="regimeRouterPanel"/);
  assert.match(html, /id="regimeRouterTitle"/);
  assert.match(html, /id="regimeRouterSummary"/);
  assert.match(html, /id="regimeRouterGrid"/);
  assert.match(css, /\.regime-router-panel/);
  assert.match(css, /\.regime-router-grid/);
  assert.match(css, /\.regime-router-card/);
  assert.match(app, /regimeRouter:\s*null/);
  assert.match(app, /regimeRouterHistory:\s*null/);
  assert.match(app, /function renderRegimeRouterPanel\(\)/);
  assert.match(app, /fetchJson\("\/api\/regime-router"\)/);
  assert.match(app, /fetchJson\("\/api\/regime-router\/history\?range=30d"\)/);
  assert.match(app, /state\.regimeRouter = regimeRouter/);
  assert.match(app, /renderRegimeRouterPanel\(\)/);
});

test("bot cards promote direction signal and position pnl into key cards", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");

  assert.match(app, /function renderTradeKeyCards\(trade\)/);
  assert.match(app, /class="trade-key-grid"/);
  assert.match(app, /class="trade-key-card/);
  assert.match(css, /\.trade-key-grid/);
  assert.match(css, /\.trade-key-card/);
  assert.match(app, /当前方向/);
  assert.match(app, /信号/);
  assert.match(app, /仓位收益/);
});

test("BTC chart hides ambiguous default axis labels and de-overlaps entry markers", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const html = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/index.html"), "utf8");

  assert.match(app, /rightPriceScale:\s*\{\s*visible:\s*true,\s*borderColor:\s*"rgba\(255, 255, 255, 0\.10\)"\s*\}/);
  assert.match(app, /axisLabelVisible:\s*true/);
  assert.match(app, /priceLineVisible:\s*false,\s*lastValueVisible:\s*false/);
  assert.match(app, /const ema21 = addSeries\(chart, "line", \{[^}]*lastValueVisible:\s*false/);
  assert.match(app, /function markerCollisionKey\(marker\)/);
  assert.match(app, /function strategySignalMarkers\(markers, occupiedMarkers = \[\]\)/);
  assert.match(app, /const occupiedKeys = new Set\(occupiedMarkers\.map\(markerCollisionKey\)\)/);
  assert.match(app, /\.filter\(\(marker\) => !occupiedKeys\.has\(markerCollisionKey\(marker\)\)\)/);
  assert.doesNotMatch(html, /EMA21|EMA55|EMA200/);
  assert.match(html, /短期均线/);
  assert.match(html, /中期均线/);
  assert.match(html, /长期均线/);
});
