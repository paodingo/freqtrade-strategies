"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  CURL_STATUS_MARKER,
  createCurlFetch,
  createEnvAwareFetch,
  noProxyMatches,
  nodeSupportsNativeEnvProxy,
  parseCurlOutput,
  shouldUseEnvProxy,
} = require("../dashboard/lib/env_aware_fetch");

test("proxy selection uses HTTPS proxy and always bypasses local Freqtrade", () => {
  const env = { HTTPS_PROXY: "http://proxy.test:8080" };
  assert.equal(shouldUseEnvProxy("https://fapi.binance.com/fapi/v1/ping", env), true);
  assert.equal(shouldUseEnvProxy("http://localhost:8122/api/v1/ping", env), false);
  assert.equal(shouldUseEnvProxy("http://127.0.0.1:8122/api/v1/ping", env), false);
});

test("NO_PROXY supports exact and suffix matches", () => {
  const env = { NO_PROXY: "localhost,.binance.com,example.test:8443" };
  assert.equal(noProxyMatches("https://fapi.binance.com/fapi/v1/ping", env), true);
  assert.equal(noProxyMatches("https://binance.com/fapi/v1/ping", env), true);
  assert.equal(noProxyMatches("https://example.test:8443/ping", env), true);
  assert.equal(noProxyMatches("https://notbinance.com/ping", env), false);
});

test("env-aware fetch routes only proxied public requests through fallback", async () => {
  const calls = [];
  const directFetch = async (url) => {
    calls.push(["direct", url]);
    return { ok: true };
  };
  const proxyFetch = async (url) => {
    calls.push(["proxy", url]);
    return { ok: true };
  };
  const fetchImpl = createEnvAwareFetch({
    env: { HTTPS_PROXY: "http://proxy.test:8080" },
    directFetch,
    proxyFetch,
  });

  await fetchImpl("https://fapi.binance.com/fapi/v1/ping");
  await fetchImpl("http://localhost:8122/api/v1/ping");

  assert.deepEqual(calls.map(([route]) => route), ["proxy", "direct"]);
});

test("Node 24.5 and newer can use native proxy support when explicitly enabled", async () => {
  assert.equal(nodeSupportsNativeEnvProxy("24.4.0"), false);
  assert.equal(nodeSupportsNativeEnvProxy("24.5.0"), true);
  assert.equal(nodeSupportsNativeEnvProxy("25.0.0"), true);

  const routes = [];
  const fetchImpl = createEnvAwareFetch({
    env: { HTTPS_PROXY: "http://proxy.test:8080", NODE_USE_ENV_PROXY: "1" },
    nodeVersion: "24.5.0",
    directFetch: async () => routes.push("native"),
    proxyFetch: async () => routes.push("curl"),
  });
  await fetchImpl("https://fapi.binance.com/fapi/v1/ping");
  assert.deepEqual(routes, ["native"]);
});

test("curl response adapter exposes fetch-compatible status and body", async () => {
  const seen = {};
  const execFileImpl = (command, args, options, callback) => {
    seen.command = command;
    seen.args = args;
    seen.options = options;
    queueMicrotask(() => callback(null, `{"price":"64000"}${CURL_STATUS_MARKER}200`, ""));
    return { kill() {} };
  };
  const fetchImpl = createCurlFetch({ execFileImpl, timeoutMs: 7_500 });
  const response = await fetchImpl("https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT");

  assert.equal(seen.command, "curl");
  assert.ok(seen.args.includes("8"));
  assert.ok(seen.args.every((arg) => !arg.includes("proxy.test")));
  assert.equal(response.ok, true);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { price: "64000" });
});

test("curl output parser rejects missing or invalid status markers", () => {
  assert.deepEqual(parseCurlOutput(`[]${CURL_STATUS_MARKER}429`), { body: "[]", status: 429 });
  assert.throws(() => parseCurlOutput("[]"), /did not include/);
  assert.throws(() => parseCurlOutput(`[]${CURL_STATUS_MARKER}oops`), /invalid/);
});
