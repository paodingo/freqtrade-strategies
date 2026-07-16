#!/usr/bin/env node
"use strict";

const { spawn } = require("node:child_process");
const path = require("node:path");

const LOCAL_NO_PROXY_HOSTS = ["127.0.0.1", "localhost", "::1"];

function hasProxy(env) {
  return Boolean(env.HTTPS_PROXY || env.HTTP_PROXY || env.https_proxy || env.http_proxy);
}

function proxyEnabled(env) {
  return !new Set(["0", "false", "off"]).has(
    String(env.DASHBOARD_USE_ENV_PROXY || "1").trim().toLowerCase(),
  );
}

function appendLocalNoProxy(env) {
  const current = String(env.NO_PROXY || env.no_proxy || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const merged = [...new Set([...current, ...LOCAL_NO_PROXY_HOSTS])].join(",");
  return { ...env, NO_PROXY: merged, no_proxy: merged };
}

function buildDashboardNodeArgs({
  env = process.env,
  execArgv = process.execArgv,
  serverPath = path.join(__dirname, "server.js"),
  argv = process.argv.slice(2),
  supportsEnvProxy = process.allowedNodeEnvironmentFlags.has("--use-env-proxy"),
} = {}) {
  const args = [...execArgv];
  if (hasProxy(env) && proxyEnabled(env) && !args.includes("--use-env-proxy")) {
    if (!supportsEnvProxy) {
      throw new Error("This Node.js runtime does not support --use-env-proxy; use Node.js 24 or newer.");
    }
    args.push("--use-env-proxy");
  }
  return [...args, serverPath, ...argv];
}

function startDashboard() {
  const env = appendLocalNoProxy(process.env);
  const child = spawn(process.execPath, buildDashboardNodeArgs({ env }), {
    env,
    stdio: "inherit",
  });

  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.on(signal, () => child.kill(signal));
  }
  child.on("error", (error) => {
    console.error(`dashboard launcher failed: ${error.message}`);
    process.exitCode = 1;
  });
  child.on("exit", (code, signal) => {
    process.exitCode = code ?? (signal ? 1 : 0);
  });
}

if (require.main === module) {
  startDashboard();
}

module.exports = {
  appendLocalNoProxy,
  buildDashboardNodeArgs,
  hasProxy,
  proxyEnabled,
};
