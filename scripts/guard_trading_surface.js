#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");

const EXIT_PASS = 0;
const EXIT_BLOCKED = 1;
const EXIT_TOOL_ERROR = 2;

const BLOCKED_SURFACES = [
  { prefix: "strategies/", reason: "strategy code is blocked by default" },
  { prefix: "user_data/", reason: "bot config/runtime data is blocked by default" },
  { prefix: "configs/", reason: "bot config surface is blocked by default" },
  { prefix: "dashboard/", reason: "dashboard runtime surface is blocked by default" },
  { path: "scripts/start_bot.sh", reason: "bot start/stop surface is blocked by default" },
  { path: "scripts/ensure_dry_run_bots_started.sh", reason: "bot lifecycle surface is blocked by default" },
  { path: "scripts/refresh_data.sh", reason: "market-data refresh surface is blocked by default" },
  { path: "scripts/check_system_health.sh", reason: "server health surface is blocked by default" },
  { path: "scripts/check_trades.sh", reason: "trade monitor surface is blocked by default" },
  { prefix: "deploy/", reason: "server deployment surface is blocked by default" },
  { prefix: "reports/reliable_strategy_search_v1129/", reason: "V11.29 report surface is blocked by default" },
  { path: ".env", reason: "secret env file is blocked by default" },
  { path: "user_data/monitor.env", reason: "monitor secret env file is blocked by default" },
  { regex: /^scripts\/build_v1130_/i, reason: "unapproved V11.30 report builder is blocked by default" },
  { prefix: "reports/v1130_observation/", reason: "unapproved V11.30 observation report surface is blocked by default" },
  { regex: /^scripts\/build_v1131_/i, reason: "unapproved V11.31 report builder is blocked by default" },
  { prefix: "reports/v1131_observation/", reason: "unapproved V11.31 observation report surface is blocked by default" },
  { regex: /(^|\/)(RegimeAwareV1082|RegimeAwareV1129|v1082|v1129)(\.|_|-|\/|$)/i, reason: "V10.8.2/V11.29 versioned surface is blocked by default" },
];

const EXACT_VERSIONED_DOC_EXCEPTIONS = new Set([
  "docs/harness/v1129_execution_report_schema.md",
  "reports/v1129_execution_validation/sample_empty_report.json",
  "reports/v1129_execution_validation/sample_empty_report.md",
  "reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json",
  "reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md",
  "scripts/build_v1129_signal_decision_telemetry.js",
  "reports/v1129_execution_validation/signal_decision_telemetry_sample.json",
  "reports/v1129_execution_validation/signal_decision_telemetry_sample.md",
  "scripts/build_v1129_pre_filter_signal_reconstruction.js",
  "reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json",
  "reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md",
  "scripts/build_v1129_ranging_short_offline_return_study.js",
  "reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.json",
  "reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.md",
  "scripts/build_v1129_feather_ranging_short_historical_return_study.js",
  "reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json",
  "reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md",
  "scripts/build_v1129_high_volatility_replay_harness.js",
  "reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json",
  "reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.md",
  "tests/test_v1129_high_volatility_replay_harness.js",
  "strategies/RegimeAwareV1129RangingShortShadow.py",
  "user_data/config_multi_futures_v1129_ranging_short_shadow.json",
  "strategies/RegimeAwareV1130CrashReboundShadow.py",
  "user_data/config_multi_futures_v1130_crash_rebound_shadow.json",
  "tests/test_regime_aware_v1130_crash_rebound_shadow.py",
  "strategies/RegimeAwareV1131LooseRangeWatchShadow.py",
  "user_data/config_multi_futures_v1131_loose_range_watch_shadow.json",
  "tests/test_regime_aware_v1131_loose_range_watch_shadow.py",
  "scripts/build_v1130_gate_telemetry_report.js",
  "reports/v1130_observation/v1130_gate_telemetry_report.json",
  "reports/v1130_observation/v1130_gate_telemetry_report.md",
  "scripts/build_v1130_loose_range_replay_report.js",
  "reports/v1130_observation/v1130_loose_range_replay_report.json",
  "reports/v1130_observation/v1130_loose_range_replay_report.md",
  "scripts/build_v1130_watch_only_telemetry_report.js",
  "reports/v1130_observation/v1130_watch_only_telemetry_report.json",
  "reports/v1130_observation/v1130_watch_only_telemetry_report.md",
  "scripts/build_v1130_decision_trace_report.js",
  "reports/v1130_observation/v1130_decision_trace_report.json",
  "reports/v1130_observation/v1130_decision_trace_report.md",
  "reports/v1130_observation/v1130_final_decision_telemetry.json",
  "reports/v1130_observation/v1130_final_decision_telemetry.md",
  "scripts/build_strategy_candidate_search_harness.js",
  "reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json",
  "reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md",
  "reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv",
  "scripts/build_v1131_loose_range_replay_report.js",
  "reports/v1131_observation/v1131_loose_range_replay_report.json",
  "reports/v1131_observation/v1131_loose_range_replay_report.md",
  "scripts/build_v1131_loose_range_replay_coverage_extension.js",
  "reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json",
  "reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md",
  "scripts/build_v1131_longer_replay_window_inventory.js",
  "reports/v1131_observation/v1131_longer_replay_window_inventory.json",
  "reports/v1131_observation/v1131_longer_replay_window_inventory.md",
  "scripts/build_v1131_longer_replay_data_source_inventory.js",
  "reports/v1131_observation/v1131_longer_replay_data_source_inventory.json",
  "reports/v1131_observation/v1131_longer_replay_data_source_inventory.md",
  "scripts/build_v1131_longer_replay_data_acquisition_plan.js",
  "reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json",
  "reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md",
  "scripts/build_v1131_longer_replay_data_acquisition_execution_report.js",
  "reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.json",
  "reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.md",
  "scripts/build_v1131_longer_replay_data_acquisition_actual_execution_report.js",
  "reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.json",
  "reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.md",
  "scripts/build_v1130_runtime_performance_audit.js",
  "reports/v1130_observation/v1130_runtime_performance_audit.json",
  "reports/v1130_observation/v1130_runtime_performance_audit.md",
  "scripts/build_v1130_live_telemetry_window_report.js",
  "reports/v1130_observation/v1130_live_telemetry_window_report.json",
  "reports/v1130_observation/v1130_live_telemetry_window_report.md",
  "scripts/build_v1130_live_telemetry_server_collection_plan.js",
  "reports/v1130_observation/v1130_live_telemetry_server_collection_plan.json",
  "reports/v1130_observation/v1130_live_telemetry_server_collection_plan.md",
  "scripts/build_v1130_live_telemetry_server_collection_execution_report.js",
  "reports/v1130_observation/v1130_live_telemetry_server_collection_execution_report.json",
  "reports/v1130_observation/v1130_live_telemetry_server_collection_execution_report.md",
  "dashboard/lib/config.js",
  "dashboard/server.js",
]);

const EXACT_TRADE_MONITOR_EXCEPTIONS = new Set([
  "scripts/check_trades.sh",
  "scripts/notify_trades.sh",
]);

function failTool(message, detail) {
  console.error(`guard_trading_surface: tool/config error: ${message}`);
  if (detail) {
    console.error(detail);
  }
  process.exit(EXIT_TOOL_ERROR);
}

function git(args, cwd) {
  try {
    return execFileSync("git", args, {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    const stderr = error.stderr ? String(error.stderr).trim() : "";
    const stdout = error.stdout ? String(error.stdout).trim() : "";
    failTool(`git ${args.join(" ")} failed`, stderr || stdout || error.message);
  }
}

function repoRoot() {
  return git(["rev-parse", "--show-toplevel"], process.cwd()).trim();
}

function normalizePath(value, root) {
  let normalized = String(value || "").trim().replace(/\\/g, "/");
  if (!normalized) {
    return "";
  }
  const normalizedRoot = root.replace(/\\/g, "/").replace(/\/+$/, "");
  if (normalized.toLowerCase().startsWith(`${normalizedRoot.toLowerCase()}/`)) {
    normalized = normalized.slice(normalizedRoot.length + 1);
  }
  return normalized.replace(/^\.\/+/, "").replace(/\/+$/, "");
}

function splitPathList(output, root) {
  return output
    .split(/\r?\n/)
    .map((line) => normalizePath(line, root))
    .filter(Boolean);
}

function collectChangedPaths(root) {
  const argPaths = process.argv.slice(2).filter((arg) => arg !== "--");
  if (argPaths.length > 0) {
    return [...new Set(argPaths.map((arg) => normalizePath(arg, root)).filter(Boolean))].sort();
  }

  if (process.env.GUARD_DIFF_FILES) {
    return [
      ...new Set(
        process.env.GUARD_DIFF_FILES
          .split(/[\r\n,]+/)
          .map((entry) => normalizePath(entry, root))
          .filter(Boolean),
      ),
    ].sort();
  }

  if (process.env.GUARD_DIFF_BASE) {
    const output = git(
      ["diff", "--name-only", "--diff-filter=ACDMRTUXB", `${process.env.GUARD_DIFF_BASE}...HEAD`],
      root,
    );
    return [...new Set(splitPathList(output, root))].sort();
  }

  const outputs = [
    git(["diff", "--name-only", "--diff-filter=ACDMRTUXB"], root),
    git(["diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB"], root),
    git(["ls-files", "--others", "--exclude-standard"], root),
  ];
  return [...new Set(outputs.flatMap((output) => splitPathList(output, root)))].sort();
}

function blockedReason(repoPath) {
  if (EXACT_TRADE_MONITOR_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  if (EXACT_VERSIONED_DOC_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  for (const surface of BLOCKED_SURFACES) {
    if (surface.path && repoPath === surface.path) {
      return surface.reason;
    }
    if (surface.prefix && repoPath.startsWith(surface.prefix)) {
      return surface.reason;
    }
    if (surface.regex && surface.regex.test(repoPath)) {
      return surface.reason;
    }
  }
  return null;
}

function main() {
  const root = repoRoot();
  const changedPaths = collectChangedPaths(root);
  const blocked = changedPaths
    .map((repoPath) => ({ path: repoPath, reason: blockedReason(repoPath) }))
    .filter((item) => item.reason);

  if (blocked.length > 0) {
    console.error("guard_trading_surface: blocked high-risk diff");
    for (const item of blocked) {
      console.error(`- ${item.path}: ${item.reason}`);
    }
    process.exit(EXIT_BLOCKED);
  }

  console.log(`guard_trading_surface: pass (${changedPaths.length} changed path(s) checked)`);
  process.exit(EXIT_PASS);
}

main();
