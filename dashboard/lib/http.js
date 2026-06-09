"use strict";

const fs = require("fs");
const path = require("path");

const { PUBLIC_DIR, STATIC_TYPES } = require("./config");

function send(res, status, body, headers = {}) {
  const payload = Buffer.isBuffer(body) ? body : Buffer.from(String(body));
  res.writeHead(status, {
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
    ...headers,
  });
  res.end(payload);
}

function sendJson(res, status, body) {
  send(res, status, JSON.stringify(body), {
    "Content-Type": "application/json; charset=utf-8",
  });
}

function serveStatic(requestUrl, res) {
  const requestPath = requestUrl === "/" ? "/index.html" : decodeURIComponent(requestUrl);
  const normalized = path.normalize(requestPath).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(PUBLIC_DIR, normalized);

  if (!filePath.startsWith(PUBLIC_DIR)) {
    send(res, 403, "Forbidden\n", { "Content-Type": "text/plain; charset=utf-8" });
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      send(res, 404, "Not found\n", { "Content-Type": "text/plain; charset=utf-8" });
      return;
    }

    const ext = path.extname(filePath);
    send(res, 200, data, {
      "Content-Type": STATIC_TYPES[ext] || "application/octet-stream",
    });
  });
}

module.exports = {
  send,
  sendJson,
  serveStatic,
};
