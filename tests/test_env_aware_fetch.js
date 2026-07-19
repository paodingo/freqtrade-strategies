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

test("proxy selection always bypasses local Freqtrade", () => {
  const env = { HTTPS_PROXY: "http://proxy.test:8080", HTTP_PROXY: "http://proxy.test:8080" };
  assert.equal(shouldUseEnvProxy("https://fapi.binance.com/fapi/v1/ping", env), true);
  assert.equal(shouldUseEnvProxy("http://localhost:8122/api/v1/ping", env), false);
  assert.equal(noProxyMatches("https://fapi.binance.com/ping", { NO_PROXY: ".binance.com" }), true);
});

test("Node 22 uses curl while Node 24 native proxy mode stays on fetch", async () => {
  const routes = [];
  const options = {
    env: { HTTPS_PROXY: "http://proxy.test:8080" },
    directFetch: async () => routes.push("native"),
    proxyFetch: async () => routes.push("curl"),
  };
  await createEnvAwareFetch({ ...options, nodeVersion: "22.22.2", execArgv: [] })("https://fapi.binance.com");
  await createEnvAwareFetch({ ...options, nodeVersion: "24.5.0", execArgv: ["--use-env-proxy"] })("https://fapi.binance.com");
  assert.deepEqual(routes, ["curl", "native"]);
  assert.equal(nodeSupportsNativeEnvProxy("24.4.0"), false);
  assert.equal(nodeSupportsNativeEnvProxy("24.5.0"), true);
});

test("curl adapter returns a fetch-compatible response without exposing proxy arguments", async () => {
  const seen = {};
  const execFileImpl = (command, args, options, callback) => {
    Object.assign(seen, { command, args, options });
    queueMicrotask(() => callback(null, `{"price":"64000"}${CURL_STATUS_MARKER}200`, ""));
    return { kill() {} };
  };
  const response = await createCurlFetch({ execFileImpl })("https://fapi.binance.com/ticker");
  assert.equal(seen.command, "curl");
  assert.ok(seen.args.every((arg) => !arg.includes("proxy.test")));
  assert.equal(response.ok, true);
  assert.deepEqual(await response.json(), { price: "64000" });
});

test("curl parser rejects malformed response metadata", () => {
  assert.deepEqual(parseCurlOutput(`[]${CURL_STATUS_MARKER}429`), { body: "[]", status: 429 });
  assert.throws(() => parseCurlOutput("[]"), /did not include/);
  assert.throws(() => parseCurlOutput(`[]${CURL_STATUS_MARKER}oops`), /invalid/);
});
