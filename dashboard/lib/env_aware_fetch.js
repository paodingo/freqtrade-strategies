"use strict";

const { execFile } = require("node:child_process");

const CURL_STATUS_MARKER = "\n__DASHBOARD_CURL_STATUS__:";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

function proxyUrlFor(targetUrl, env = process.env) {
  const protocol = new URL(targetUrl).protocol;
  if (protocol === "https:") {
    return env.HTTPS_PROXY || env.https_proxy || env.HTTP_PROXY || env.http_proxy || null;
  }
  if (protocol === "http:") {
    return env.HTTP_PROXY || env.http_proxy || null;
  }
  return null;
}

function noProxyMatches(targetUrl, env = process.env) {
  const url = new URL(targetUrl);
  const hostname = url.hostname.toLowerCase();
  if (LOCAL_HOSTS.has(hostname)) {
    return true;
  }

  const configured = env.NO_PROXY || env.no_proxy || "";
  return configured.split(",").some((rawEntry) => {
    let entry = rawEntry.trim().toLowerCase();
    if (!entry) {
      return false;
    }
    if (entry === "*") {
      return true;
    }
    if (entry.startsWith("[")) {
      const closing = entry.indexOf("]");
      entry = closing >= 0 ? entry.slice(1, closing) : entry;
    } else if (entry.includes(":")) {
      entry = entry.split(":", 1)[0];
    }
    entry = entry.replace(/^\./, "");
    return hostname === entry || hostname.endsWith(`.${entry}`);
  });
}

function shouldUseEnvProxy(targetUrl, env = process.env) {
  return Boolean(proxyUrlFor(targetUrl, env)) && !noProxyMatches(targetUrl, env);
}

function nodeSupportsNativeEnvProxy(nodeVersion = process.versions.node) {
  const [major, minor] = String(nodeVersion || "0.0").split(".").map(Number);
  return major > 24 || (major === 24 && minor >= 5);
}

function statusText(status) {
  if (status >= 200 && status < 300) return "OK";
  if (status === 400) return "Bad Request";
  if (status === 401) return "Unauthorized";
  if (status === 403) return "Forbidden";
  if (status === 404) return "Not Found";
  if (status === 429) return "Too Many Requests";
  if (status >= 500) return "Upstream Error";
  return "";
}

function parseCurlOutput(stdout) {
  const output = String(stdout || "");
  const markerIndex = output.lastIndexOf(CURL_STATUS_MARKER);
  if (markerIndex < 0) {
    throw new Error("curl response did not include an HTTP status");
  }
  const body = output.slice(0, markerIndex);
  const status = Number(output.slice(markerIndex + CURL_STATUS_MARKER.length).trim());
  if (!Number.isInteger(status) || status < 100 || status > 599) {
    throw new Error("curl returned an invalid HTTP status");
  }
  return { body, status };
}

function createCurlFetch({ execFileImpl = execFile, timeoutMs = 8_000 } = {}) {
  return function curlFetch(targetUrl, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    if (method !== "GET") {
      return Promise.reject(new Error("proxy fallback only supports public GET requests"));
    }
    if (options.signal?.aborted) {
      return Promise.reject(options.signal.reason || new Error("request aborted"));
    }

    const timeoutSeconds = Math.max(1, Math.ceil(timeoutMs / 1000));
    const args = [
      "--silent",
      "--show-error",
      "--location",
      "--max-time",
      String(timeoutSeconds),
      "--write-out",
      `${CURL_STATUS_MARKER}%{http_code}`,
      String(targetUrl),
    ];

    return new Promise((resolve, reject) => {
      let child;
      const onAbort = () => {
        child?.kill();
        reject(options.signal.reason || new Error("request aborted"));
      };
      if (options.signal) {
        options.signal.addEventListener("abort", onAbort, { once: true });
      }

      child = execFileImpl("curl", args, { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 }, (error, stdout, stderr) => {
        options.signal?.removeEventListener("abort", onAbort);
        if (error) {
          const detail = String(stderr || error.message || "curl request failed").trim().slice(0, 240);
          reject(new Error(`public market request failed: ${detail}`));
          return;
        }
        try {
          const parsed = parseCurlOutput(stdout);
          resolve({
            ok: parsed.status >= 200 && parsed.status < 300,
            status: parsed.status,
            statusText: statusText(parsed.status),
            text: async () => parsed.body,
            json: async () => JSON.parse(parsed.body),
          });
        } catch (parseError) {
          reject(parseError);
        }
      });
    });
  };
}

function createEnvAwareFetch({
  env = process.env,
  directFetch = global.fetch,
  proxyFetch = createCurlFetch(),
  nodeVersion = process.versions.node,
} = {}) {
  if (typeof directFetch !== "function") {
    throw new Error("A direct fetch implementation is required");
  }
  return function envAwareFetch(targetUrl, options = {}) {
    const nativeProxyEnabled = env.NODE_USE_ENV_PROXY === "1" && nodeSupportsNativeEnvProxy(nodeVersion);
    if (shouldUseEnvProxy(targetUrl, env) && !nativeProxyEnabled) {
      return proxyFetch(targetUrl, options);
    }
    return directFetch(targetUrl, options);
  };
}

module.exports = {
  CURL_STATUS_MARKER,
  createCurlFetch,
  createEnvAwareFetch,
  noProxyMatches,
  nodeSupportsNativeEnvProxy,
  parseCurlOutput,
  proxyUrlFor,
  shouldUseEnvProxy,
};
