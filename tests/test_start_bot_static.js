"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const PROJECT_DIR = path.resolve(__dirname, "..");
const SCRIPT = path.join(PROJECT_DIR, "scripts", "start_bot.sh");

test("start bot script passes optional alpha risk environment variables", () => {
  const content = fs.readFileSync(SCRIPT, "utf8");

  assert.match(content, /ALPHA_FILTER_MODE/);
  assert.match(content, /ALPHA_RISK_DB_FILE/);
  assert.match(content, /ALPHA_FILTER_MAX_AGE_MINUTES/);
  assert.match(content, /docker_args=/);
  assert.match(content, /-e "ALPHA_FILTER_MODE=\$ALPHA_FILTER_MODE"/);
});

test("start bot script passes optional trade supervisor environment variables", () => {
  const content = fs.readFileSync(SCRIPT, "utf8");

  assert.match(content, /TRADE_SUPERVISOR_ENABLED/);
  assert.match(content, /TRADE_SUPERVISOR_DB_FILE/);
  assert.match(content, /TRADE_SUPERVISOR_FILTER_MODE/);
  assert.match(content, /TRADE_SUPERVISOR_MAX_AGE_MINUTES/);
  assert.match(content, /TRADE_SUPERVISOR_FAIL_CLOSED/);
  assert.match(content, /-e "TRADE_SUPERVISOR_ENABLED=\$TRADE_SUPERVISOR_ENABLED"/);
});
