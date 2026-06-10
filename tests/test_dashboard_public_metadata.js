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

  assert.match(html, /id="priceLineLegend"/);
  assert.match(css, /\.legend-line\.dashed/);
  for (const className of ["current-price", "entry-price", "take-profit", "stop-loss", "liquidation"]) {
    assert.match(html, new RegExp(`legend-line dashed ${className}`));
  }
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
