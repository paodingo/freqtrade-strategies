"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const PROJECT_DIR = path.resolve(__dirname, "..");
const SCRIPT = path.join(PROJECT_DIR, "scripts", "notify_trades.sh");

test("trade notification script records delivery audit for Telegram and OpenClaw", () => {
  const content = fs.readFileSync(SCRIPT, "utf8");

  assert.match(content, /DELIVERY_LOG=/);
  assert.match(content, /log_delivery\(\)/);
  assert.match(content, /telegram\s+ok/);
  assert.match(content, /telegram\s+failed/);
  assert.match(content, /openclaw\s+ok/);
  assert.match(content, /openclaw\s+failed/);
  assert.match(content, /openclaw_output=/);
  assert.match(content, /Message ID/);
});
