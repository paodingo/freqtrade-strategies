#!/usr/bin/env node
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.MONITOR_PORT || 8090);
const HOST = process.env.MONITOR_HOST || "0.0.0.0";
const DASHBOARD_USER = process.env.DASHBOARD_USER || "paodingo";
const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD;
const FREQTRADE_AUTH = process.env.FREQTRADE_API_AUTH || "freqtrader:freqtrade";
const REFRESH_HINT_SECONDS = Number(process.env.REFRESH_HINT_SECONDS || 15);

const BOTS = [
  {
    key: "v6",
    label: "V6",
    url: process.env.BOT_V6_URL || "http://localhost:8080",
  },
  {
    key: "v61",
    label: "V6.1",
    url: process.env.BOT_V61_URL || "http://localhost:8081",
  },
];

const PUBLIC_DIR = path.join(__dirname, "public");
const STATIC_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

function send(res, status, body, headers = {}) {
  const payload = Buffer.isBuffer(body) ? body : Buffer.from(String(body));
  res.writeHead(status, {
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
    ...headers,
  });
  res.end(payload);
}

function sendJson(res, status, body) {
  send(res, status, JSON.stringify(body), {
    "Content-Type": "application/json; charset=utf-8",
  });
}

function unauthorized(res) {
  res.writeHead(401, {
    "WWW-Authenticate": 'Basic realm="Freqtrade Monitor"',
    "Content-Type": "text/plain; charset=utf-8",
  });
  res.end("Authentication required\n");
}

function isAuthorized(req) {
  if (!DASHBOARD_PASSWORD) {
    return false;
  }

  const header = req.headers.authorization || "";
  if (!header.startsWith("Basic ")) {
    return false;
  }

  const decoded = Buffer.from(header.slice(6), "base64").toString("utf8");
  const separator = decoded.indexOf(":");
  if (separator < 0) {
    return false;
  }

  const username = decoded.slice(0, separator);
  const password = decoded.slice(separator + 1);
  return username === DASHBOARD_USER && password === DASHBOARD_PASSWORD;
}

function freqtradeHeaders() {
  return {
    Authorization: `Basic ${Buffer.from(FREQTRADE_AUTH).toString("base64")}`,
  };
}

async function fetchJson(baseUrl, endpoint) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(`${baseUrl}${endpoint}`, {
      headers: freqtradeHeaders(),
      signal: controller.signal,
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 120)}`);
    }
    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

async function loadBot(bot) {
  const startedAt = Date.now();
  try {
    const [ping, config, count, profit, status] = await Promise.all([
      fetchJson(bot.url, "/api/v1/ping"),
      fetchJson(bot.url, "/api/v1/show_config"),
      fetchJson(bot.url, "/api/v1/count"),
      fetchJson(bot.url, "/api/v1/profit"),
      fetchJson(bot.url, "/api/v1/status").catch(() => []),
    ]);

    return {
      key: bot.key,
      label: bot.label,
      ok: true,
      latencyMs: Date.now() - startedAt,
      ping: ping.status,
      botName: config.bot_name,
      strategy: config.strategy,
      state: config.state,
      runmode: config.runmode,
      dryRun: config.dry_run,
      maxOpenTrades: config.max_open_trades,
      currentOpenTrades: count.current,
      totalStake: count.total_stake,
      profitAllCoin: profit.profit_all_coin,
      profitAllPercentMean: profit.profit_all_percent_mean,
      profitClosedCoin: profit.profit_closed_coin,
      profitClosedPercent: profit.profit_closed_percent,
      tradeCount: profit.trade_count,
      closedTradeCount: profit.closed_trade_count,
      firstTradeDate: profit.first_trade_date,
      latestTradeDate: profit.latest_trade_date,
      winrate: profit.winrate,
      maxDrawdown: profit.max_drawdown,
      openTrades: Array.isArray(status) ? status : [],
      error: null,
    };
  } catch (error) {
    return {
      key: bot.key,
      label: bot.label,
      ok: false,
      latencyMs: Date.now() - startedAt,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function buildComparison(results) {
  const v6 = results.find((bot) => bot.key === "v6");
  const v61 = results.find((bot) => bot.key === "v61");
  if (!v6?.ok || !v61?.ok) {
    return null;
  }
  return {
    profitAllCoinDelta: Number(v61.profitAllCoin || 0) - Number(v6.profitAllCoin || 0),
    tradeCountDelta: Number(v61.tradeCount || 0) - Number(v6.tradeCount || 0),
    openTradesDelta: Number(v61.currentOpenTrades || 0) - Number(v6.currentOpenTrades || 0),
    closedTradeCountDelta: Number(v61.closedTradeCount || 0) - Number(v6.closedTradeCount || 0),
  };
}

async function handleApiSummary(res) {
  const bots = await Promise.all(BOTS.map(loadBot));
  sendJson(res, 200, {
    generatedAt: new Date().toISOString(),
    refreshHintSeconds: REFRESH_HINT_SECONDS,
    bots,
    comparison: buildComparison(bots),
  });
}

function serveStatic(req, res) {
  const requestPath = req.url === "/" ? "/index.html" : decodeURIComponent(req.url);
  const normalized = path.normalize(requestPath).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(PUBLIC_DIR, normalized);

  if (!filePath.startsWith(PUBLIC_DIR)) {
    send(res, 403, "Forbidden\n", { "Content-Type": "text/plain; charset=utf-8" });
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      send(res, 404, "Not found\n", { "Content-Type": "text/plain; charset=utf-8" });
      return;
    }

    const ext = path.extname(filePath);
    send(res, 200, data, {
      "Content-Type": STATIC_TYPES[ext] || "application/octet-stream",
    });
  });
}

const server = http.createServer(async (req, res) => {
  if (!isAuthorized(req)) {
    unauthorized(res);
    return;
  }

  try {
    const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
    if (url.pathname === "/api/summary") {
      await handleApiSummary(res);
      return;
    }
    serveStatic({ ...req, url: url.pathname }, res);
  } catch (error) {
    sendJson(res, 500, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

if (!DASHBOARD_PASSWORD) {
  console.error("DASHBOARD_PASSWORD is required.");
  process.exit(1);
}

server.listen(PORT, HOST, () => {
  console.log(`freqtrade monitor listening on http://${HOST}:${PORT}`);
});
