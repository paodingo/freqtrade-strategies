"use strict";

const fs = require("fs");
const path = require("path");

const SCHEMA_VERSION = "data-reliability-report-v1";
const STATUSES = new Set(["reliable", "degraded", "stale", "incomplete", "blocked"]);

function unavailable(reportFile, reason = "data_reliability_report_missing") {
  return {
    available: false,
    schema_version: SCHEMA_VERSION,
    checked_at: null,
    overall_status: "incomplete",
    decision_allowed: false,
    summary: {
      check_count: 0,
      reliable_count: 0,
      issue_count: 1,
      blocking_count: 1,
    },
    checks: [],
    issues: [],
    repairs: [],
    status_reason: reason,
    report_file: reportFile,
  };
}

function validateDataReliabilityReport(document) {
  if (!document || document.schema_version !== SCHEMA_VERSION) {
    throw new Error("data_reliability_report_invalid:schema_version");
  }
  if (!STATUSES.has(document.overall_status)) {
    throw new Error("data_reliability_report_invalid:overall_status");
  }
  if (typeof document.decision_allowed !== "boolean") {
    throw new Error("data_reliability_report_invalid:decision_allowed");
  }
  if (!Array.isArray(document.checks) || !Array.isArray(document.issues) || !Array.isArray(document.repairs)) {
    throw new Error("data_reliability_report_invalid:collections");
  }
  return document;
}

function loadDataReliability(projectDir, env = process.env, now = new Date()) {
  const reportFile = path.resolve(
    env.DATA_RELIABILITY_REPORT_FILE
      || "/home/ubuntu/freqtrade-runtime/data-reliability/latest.json",
  );
  if (!fs.existsSync(reportFile)) {
    return unavailable(reportFile);
  }
  try {
    const document = validateDataReliabilityReport(JSON.parse(fs.readFileSync(reportFile, "utf8")));
    const checkedAtMs = Date.parse(document.checked_at || "");
    const maxAgeSeconds = Number(env.DATA_RELIABILITY_MAX_AGE_SECONDS || 900);
    const ageSeconds = Number.isFinite(checkedAtMs)
      ? Math.max(0, Math.round((now.getTime() - checkedAtMs) / 1000))
      : null;
    const reportIsStale = ageSeconds === null || ageSeconds > maxAgeSeconds;
    const staleCheck = reportIsStale ? {
      id: "controller.report",
      status: "stale",
      severity: "critical",
      message: "Data reliability controller report is stale.",
      blocks_decisions: true,
      observed_value: { age_seconds: ageSeconds, maximum_age_seconds: maxAgeSeconds },
    } : null;
    return {
      available: true,
      schema_version: document.schema_version,
      checked_at: document.checked_at || null,
      overall_status: reportIsStale ? "stale" : document.overall_status,
      decision_allowed: reportIsStale ? false : document.decision_allowed,
      summary: reportIsStale ? {
        ...document.summary,
        check_count: Number(document.summary?.check_count || 0) + 1,
        issue_count: Number(document.summary?.issue_count || 0) + 1,
        blocking_count: Number(document.summary?.blocking_count || 0) + 1,
      } : document.summary,
      checks: staleCheck ? [...document.checks, staleCheck] : document.checks,
      issues: staleCheck ? [...document.issues, staleCheck] : document.issues,
      repairs: document.repairs,
      status_reason: reportIsStale ? "data_reliability_report_stale" : null,
      report_file: reportFile,
    };
  } catch (error) {
    return unavailable(
      reportFile,
      error instanceof Error ? error.message : "data_reliability_report_invalid",
    );
  }
}

module.exports = {
  SCHEMA_VERSION,
  loadDataReliability,
  validateDataReliabilityReport,
};
