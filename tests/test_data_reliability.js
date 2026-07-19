"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  loadDataReliability,
  validateDataReliabilityReport,
} = require("../dashboard/lib/data_reliability");

function report(overrides = {}) {
  return {
    schema_version: "data-reliability-report-v1",
    checked_at: "2026-07-19T12:00:00Z",
    overall_status: "reliable",
    decision_allowed: true,
    summary: { check_count: 3, reliable_count: 3, issue_count: 0, blocking_count: 0 },
    checks: [],
    issues: [],
    repairs: [],
    ...overrides,
  };
}

test("valid reliability report is exposed without changing missing P&L", () => {
  assert.equal(validateDataReliabilityReport(report()).decision_allowed, true);
});

test("missing reliability report fails closed", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "data-reliability-"));
  const loaded = loadDataReliability(root, {
    DATA_RELIABILITY_REPORT_FILE: path.join(root, "missing.json"),
  });
  assert.equal(loaded.available, false);
  assert.equal(loaded.overall_status, "incomplete");
  assert.equal(loaded.decision_allowed, false);
});

test("invalid reliability status fails closed", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "data-reliability-"));
  const reportFile = path.join(root, "latest.json");
  fs.writeFileSync(reportFile, JSON.stringify(report({ overall_status: "unknown" })));
  const loaded = loadDataReliability(root, { DATA_RELIABILITY_REPORT_FILE: reportFile });
  assert.equal(loaded.available, false);
  assert.equal(loaded.decision_allowed, false);
  assert.match(loaded.status_reason, /overall_status/);
});

test("stale controller report opens the decision circuit breaker", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "data-reliability-"));
  const reportFile = path.join(root, "latest.json");
  fs.writeFileSync(reportFile, JSON.stringify(report()));
  const loaded = loadDataReliability(
    root,
    { DATA_RELIABILITY_REPORT_FILE: reportFile, DATA_RELIABILITY_MAX_AGE_SECONDS: "900" },
    new Date("2026-07-19T12:20:00Z"),
  );
  assert.equal(loaded.available, true);
  assert.equal(loaded.overall_status, "stale");
  assert.equal(loaded.decision_allowed, false);
  assert.equal(loaded.status_reason, "data_reliability_report_stale");
});
