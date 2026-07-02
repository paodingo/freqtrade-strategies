#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");

const EXIT_PASS = 0;
const EXIT_BLOCKED = 1;
const EXIT_TOOL_ERROR = 2;

const BLOCKED_SURFACES = [
  { prefix: "strategies/", reason: "strategy code is blocked by default" },
  { prefix: "user_data/", reason: "bot config/runtime data is blocked by default" },
  { path: "dashboard/lib/config.js", reason: "dashboard runtime config is blocked by default" },
  { path: "dashboard/server.js", reason: "dashboard server is blocked by default" },
  { prefix: "dashboard/public/", reason: "dashboard public UI is blocked by default" },
  { path: "scripts/start_bot.sh", reason: "bot start/stop surface is blocked by default" },
  { path: "scripts/ensure_dry_run_bots_started.sh", reason: "bot lifecycle surface is blocked by default" },
  { path: "scripts/refresh_data.sh", reason: "market-data refresh surface is blocked by default" },
  { path: "scripts/check_system_health.sh", reason: "server health surface is blocked by default" },
  { path: "scripts/check_trades.sh", reason: "trade monitor surface is blocked by default" },
  { prefix: "deploy/", reason: "server deployment surface is blocked by default" },
  { prefix: "reports/reliable_strategy_search_v1129/", reason: "V11.29 report surface is blocked by default" },
  { path: ".env", reason: "secret env file is blocked by default" },
  { path: "user_data/monitor.env", reason: "monitor secret env file is blocked by default" },
  { regex: /(^|\/)(RegimeAwareV1082|RegimeAwareV1129|v1082|v1129)(\.|_|-|\/|$)/i, reason: "V10.8.2/V11.29 versioned surface is blocked by default" },
];

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
