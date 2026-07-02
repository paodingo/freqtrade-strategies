#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const EXIT_PASS = 0;
const EXIT_BLOCKED = 1;
const EXIT_TOOL_ERROR = 2;
const MAX_SCAN_BYTES = 1024 * 1024;

const SECRET_PATH_RULES = [
  { test: (repoPath) => repoPath === ".env", reason: "local env file must not be changed or read" },
  { test: (repoPath) => repoPath.endsWith("/.env"), reason: "env file must not be changed or read" },
  { test: (repoPath) => repoPath === "user_data/monitor.env", reason: "monitor env file must not be changed or read" },
  { test: (repoPath) => /(^|\/)id_(rsa|dsa|ecdsa|ed25519)$/.test(repoPath), reason: "private SSH key path" },
  { test: (repoPath) => /\.(pem|p12|pfx|key)$/i.test(repoPath), reason: "key material path" },
];

const SECRET_CONTENT_RULES = [
  { name: "private_key_block", regex: /-----BEGIN [A-Z ]{0,32}PRIVATE KEY-----/ },
  { name: "aws_access_key_id", regex: /\bA[SK]IA[0-9A-Z]{16}\b/ },
  { name: "github_token", regex: /\bgh[pousr]_[A-Za-z0-9_]{30,}\b/ },
  { name: "openai_or_similar_key", regex: /\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b/ },
  { name: "stripe_secret_key", regex: /\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b/ },
  { name: "slack_token", regex: /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/ },
  { name: "credential_assignment", regex: /\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|refresh[_-]?token|password|passwd|exchange[_-]?(?:key|secret))\b\s*[:=]\s*["']?[A-Za-z0-9_./+=:@-]{16,}/i },
  { name: "basic_auth_url", regex: /https?:\/\/[^/\s:@]{3,}:[^/\s:@]{8,}@/i },
];

function failTool(message, detail) {
  console.error(`guard_no_secret_material: tool/config error: ${message}`);
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

function secretPathReason(repoPath) {
  const rule = SECRET_PATH_RULES.find((entry) => entry.test(repoPath));
  return rule ? rule.reason : null;
}

function isBinary(buffer) {
  return buffer.includes(0);
}

function lineNumberForIndex(text, index) {
  return text.slice(0, index).split(/\r\n|\r|\n/).length;
}

function scanFile(root, repoPath) {
  const fullPath = path.join(root, repoPath);
  if (!fs.existsSync(fullPath)) {
    return [];
  }

  let stats;
  try {
    stats = fs.statSync(fullPath);
  } catch (error) {
    failTool(`cannot stat ${repoPath}`, error.message);
  }

  if (!stats.isFile() || stats.size > MAX_SCAN_BYTES) {
    return [];
  }

  let buffer;
  try {
    buffer = fs.readFileSync(fullPath);
  } catch (error) {
    failTool(`cannot read ${repoPath}`, error.message);
  }

  if (isBinary(buffer)) {
    return [];
  }

  const text = buffer.toString("utf8");
  const findings = [];
  for (const rule of SECRET_CONTENT_RULES) {
    const match = rule.regex.exec(text);
    if (match) {
      findings.push({
        path: repoPath,
        rule: rule.name,
        line: lineNumberForIndex(text, match.index),
      });
    }
  }
  return findings;
}

function main() {
  const root = repoRoot();
  const changedPaths = collectChangedPaths(root);

  const blockedPaths = changedPaths
    .map((repoPath) => ({ path: repoPath, reason: secretPathReason(repoPath) }))
    .filter((item) => item.reason);

  const scannedFindings = changedPaths
    .filter((repoPath) => !secretPathReason(repoPath))
    .flatMap((repoPath) => scanFile(root, repoPath));

  if (blockedPaths.length > 0 || scannedFindings.length > 0) {
    console.error("guard_no_secret_material: blocked high-risk diff");
    for (const item of blockedPaths) {
      console.error(`- ${item.path}: ${item.reason}`);
    }
    for (const finding of scannedFindings) {
      console.error(`- ${finding.path}:${finding.line}: possible secret material (${finding.rule})`);
    }
    process.exit(EXIT_BLOCKED);
  }

  console.log(`guard_no_secret_material: pass (${changedPaths.length} changed path(s) checked)`);
  process.exit(EXIT_PASS);
}

main();
