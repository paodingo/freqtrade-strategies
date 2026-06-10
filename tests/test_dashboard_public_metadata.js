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
  assert.match(app, /\.\.\.strategySignalMarkers\(market\.markers, openMarkers\)/);
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

test("dashboard refreshes BTC price faster and prefers live trade current rates", () => {
  const config = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/lib/config.js"), "utf8");
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");

  assert.match(config, /REFRESH_HINT_SECONDS = Number\(process\.env\.REFRESH_HINT_SECONDS \|\| 5\)/);
  assert.match(app, /function currentBtcPrice\(\)/);
  assert.match(app, /function currentBtcPriceNote\(\)/);
  assert.match(app, /chartOpenTrades\(\)\.map\(\(trade\) => trade\.currentRate\)/);
  assert.match(app, /\["BTC 现价", fmtPrice\(latestPrice\)/);
  assert.match(app, /currentBtcPriceNote\(\)/);
  assert.match(app, /const latestPrice = currentBtcPrice\(\)/);
  assert.match(app, /title:\s*`现价 \$\{fmtPrice\(latestPrice\)\}`/);
  assert.doesNotMatch(app, /北京时间/);
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
