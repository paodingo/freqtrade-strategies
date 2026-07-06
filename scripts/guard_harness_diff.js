#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const EXIT_PASS = 0;
const EXIT_BLOCKED = 1;
const EXIT_TOOL_ERROR = 2;

const HIGH_RISK_SURFACES = [
  { prefix: "strategies/", reason: "strategy code is outside the harness surface" },
  { prefix: "user_data/", reason: "bot config/runtime data is outside the harness surface" },
  { prefix: "configs/", reason: "bot config surface is outside the harness surface" },
  { prefix: "dashboard/", reason: "dashboard runtime surface is outside the harness surface" },
  { path: "scripts/start_bot.sh", reason: "bot start script is outside the harness surface" },
  { path: "scripts/ensure_dry_run_bots_started.sh", reason: "bot lifecycle script is outside the harness surface" },
  { path: "scripts/refresh_data.sh", reason: "market data refresh script is outside the harness surface" },
  { path: "scripts/check_system_health.sh", reason: "server/system health script is outside the harness surface" },
  { path: "scripts/check_trades.sh", reason: "trade monitor script is outside the harness surface" },
  { prefix: "deploy/", reason: "deployment surface is outside the harness surface" },
  { prefix: "reports/reliable_strategy_search_v1129/", reason: "V11.29 report surface is outside the harness surface" },
  { path: ".env", reason: "local secret environment file is outside the harness surface" },
  { path: "user_data/monitor.env", reason: "monitor secret environment file is outside the harness surface" },
];

const EXACT_TRADE_MONITOR_EXCEPTIONS = new Set([
  "scripts/check_trades.sh",
  "scripts/notify_trades.sh",
]);

const LOW_RISK_SURFACES = [
  { path: ".gitignore" },
  { path: "AGENTS.md" },
  { path: "README.md" },
  { path: "STRATEGY_GUIDE.md" },
  { path: "DEPLOY.md" },
  { path: "LIVE_TRADING.md" },
  { regex: /^\.github\/workflows\/[^/]+\.ya?ml$/ },
  { prefix: "docs/harness/" },
  { path: "docs/agent_operating_playbook.md" },
  { path: "docs/agent_operating_playbook.html" },
  { path: "docs/opensource_reference_audit.md" },
  { path: "docs/\u9a8c\u6536\u62a5\u544a\u683c\u5f0f.md" },
  { regex: /^reports\/audits\/.+\.md$/ },
  { regex: /^tasks\/.+\.md$/ },
  { path: "scripts/build_v1129_execution_empty_report.js" },
  { path: "reports/v1129_execution_validation/sample_empty_report.json" },
  { path: "reports/v1129_execution_validation/sample_empty_report.md" },
  { path: "scripts/build_v1129_snapshot_insufficient_report.js" },
  { path: "reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json" },
  { path: "reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md" },
  { path: "scripts/build_v1129_signal_decision_telemetry.js" },
  { path: "reports/v1129_execution_validation/signal_decision_telemetry_sample.json" },
  { path: "reports/v1129_execution_validation/signal_decision_telemetry_sample.md" },
  { path: "scripts/check_trades.sh" },
  { path: "scripts/notify_trades.sh" },
  { regex: /^scripts\/guard_[^/]+\.js$/ },
  { path: "scripts/run_agent_readiness_checks.sh" },
  { path: "scripts/run_agent_readiness_checks.ps1" },
];

function failTool(message, detail) {
  console.error(`guard_harness_diff: tool/config error: ${message}`);
  if (detail) {
    console.error(detail);
  }
  process.exit(EXIT_TOOL_ERROR);
}

function git(args, cwd) {
  try {
    return execFileSync("git", ["-c", "core.quotepath=false", ...args], {
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

function highRiskReason(repoPath) {
  if (EXACT_TRADE_MONITOR_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  for (const surface of HIGH_RISK_SURFACES) {
    if (surface.path && repoPath === surface.path) {
      return surface.reason;
    }
    if (surface.prefix && repoPath.startsWith(surface.prefix)) {
      return surface.reason;
    }
  }
  return null;
}

function isLowRiskSurface(repoPath) {
  return LOW_RISK_SURFACES.some((surface) => {
    if (surface.path && repoPath === surface.path) {
      return true;
    }
    if (surface.prefix && repoPath.startsWith(surface.prefix)) {
      return true;
    }
    return Boolean(surface.regex && surface.regex.test(repoPath));
  });
}

function surfaceReason(repoPath) {
  return highRiskReason(repoPath) || "path is not an authorized low-risk harness/documentation surface";
}

function main() {
  const root = repoRoot();
  if (!fs.existsSync(path.join(root, ".git")) && !fs.existsSync(path.join(root, ".git", "HEAD"))) {
    failTool("current directory is not a git worktree");
  }

  const changedPaths = collectChangedPaths(root);
  const blocked = changedPaths
    .filter((repoPath) => highRiskReason(repoPath) || !isLowRiskSurface(repoPath))
    .map((repoPath) => ({ path: repoPath, reason: surfaceReason(repoPath) }));

  if (blocked.length > 0) {
    console.error("guard_harness_diff: blocked high-risk diff");
    for (const item of blocked) {
      console.error(`- ${item.path}: ${item.reason}`);
    }
    process.exit(EXIT_BLOCKED);
  }

  console.log(`guard_harness_diff: pass (${changedPaths.length} changed path(s) checked)`);
  process.exit(EXIT_PASS);
}

main();
