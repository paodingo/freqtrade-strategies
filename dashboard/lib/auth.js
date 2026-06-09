"use strict";

const { DASHBOARD_PASSWORD, DASHBOARD_USER } = require("./config");

function unauthorized(res) {
  res.writeHead(401, {
    "WWW-Authenticate": 'Basic realm="Freqtrade Monitor"',
    "Content-Type": "text/plain; charset=utf-8",
  });
  res.end("Authentication required\n");
}

function isAuthorized(req) {
  if (!DASHBOARD_PASSWORD) {
    return false;
  }

  const header = req.headers.authorization || "";
  if (!header.startsWith("Basic ")) {
    return false;
  }

  const decoded = Buffer.from(header.slice(6), "base64").toString("utf8");
  const separator = decoded.indexOf(":");
  if (separator < 0) {
    return false;
  }

  const username = decoded.slice(0, separator);
  const password = decoded.slice(separator + 1);
  return username === DASHBOARD_USER && password === DASHBOARD_PASSWORD;
}

module.exports = {
  isAuthorized,
  unauthorized,
};
