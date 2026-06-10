"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { safeLimit } = require("../dashboard/lib/limits");

test("safeLimit uses fallback for missing query values", () => {
  assert.equal(safeLimit(null, 1000, 1, 5000), 1000);
  assert.equal(safeLimit(undefined, 1000, 1, 5000), 1000);
  assert.equal(safeLimit("", 1000, 1, 5000), 1000);
});

test("safeLimit clamps explicit numeric query values", () => {
  assert.equal(safeLimit("20", 1000, 1, 5000), 20);
  assert.equal(safeLimit("0", 1000, 1, 5000), 1);
  assert.equal(safeLimit("9999", 1000, 1, 5000), 5000);
  assert.equal(safeLimit("bad", 1000, 1, 5000), 1000);
});
