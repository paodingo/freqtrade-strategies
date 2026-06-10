"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const PROJECT_DIR = path.resolve(__dirname, "..");

test("dashboard exposes trade supervisor decision layer", () => {
  const app = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/app.js"), "utf8");
  const css = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/public/styles.css"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");
  const store = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/lib/monitor_store.js"), "utf8");

  assert.match(server, /buildTradeSupervisorDecision/);
  assert.match(server, /async function handleApiTradeSupervisor\(res\)/);
  assert.match(server, /function handleApiTradeSupervisorHistory\(res, url\)/);
  assert.match(server, /url\.pathname === "\/api\/trade-supervisor"/);
  assert.match(server, /url\.pathname === "\/api\/trade-supervisor\/history"/);
  assert.match(server, /monitorStore\.recordTradeSupervisorDecision/);
  assert.match(store, /CREATE TABLE IF NOT EXISTS trade_supervisor_decisions/);
  assert.match(store, /recordTradeSupervisorDecision/);
  assert.match(store, /readTradeSupervisorDecisions/);
  assert.match(app, /tradeSupervisor:\s*null/);
  assert.match(app, /tradeSupervisorHistory:\s*null/);
  assert.match(app, /function supervisorModeText/);
  assert.match(app, /function renderSupervisorCards/);
  assert.match(app, /fetchJson\("\/api\/trade-supervisor"\)/);
  assert.match(app, /fetchJson\("\/api\/trade-supervisor\/history\?range=30d"\)/);
  assert.match(app, /state\.tradeSupervisor = tradeSupervisor/);
  assert.match(app, /state\.tradeSupervisorHistory = tradeSupervisorHistory/);
  assert.match(css, /\.supervisor-action-list/);
  assert.match(css, /\.supervisor-tag-list/);
});
