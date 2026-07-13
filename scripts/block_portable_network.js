"use strict";

const net = require("node:net");
const http = require("node:http");
const https = require("node:https");

function blocked() {
  throw new Error("portable_baseline_network_forbidden");
}

net.Socket.prototype.connect = blocked;
http.request = blocked;
http.get = blocked;
https.request = blocked;
https.get = blocked;
globalThis.fetch = blocked;
