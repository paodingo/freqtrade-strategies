"use strict";

const assert = require("node:assert/strict");
const { DatabaseSync } = require("node:sqlite");
const test = require("node:test");

const { readSqlitePerformance } = require("../dashboard/lib/sqlite_performance");

test("SQLite performance aggregates Freqtrade realized P&L and dates", () => {
  const db = new DatabaseSync(":memory:");
  db.exec(`
    CREATE TABLE trades (
      id INTEGER PRIMARY KEY,
      is_open BOOLEAN NOT NULL,
      open_date TEXT,
      close_date TEXT,
      stake_amount REAL,
      realized_profit REAL,
      close_profit REAL
    );
    CREATE TABLE orders (id INTEGER PRIMARY KEY);
    INSERT INTO trades VALUES
      (1, 0, '2026-07-17 14:01:00', '2026-07-17 16:01:00', 250, -5, -0.02),
      (2, 0, '2026-07-18 01:00:00', '2026-07-18 03:00:00', 250, 2, 0.008),
      (3, 1, '2026-07-18 04:00:00', NULL, 250, NULL, NULL);
    INSERT INTO orders VALUES (1), (2), (3), (4);
  `);

  const snapshot = readSqlitePerformance(db);
  assert.equal(snapshot.totalTrades, 3);
  assert.equal(snapshot.openTrades, 1);
  assert.equal(snapshot.closedTrades, 2);
  assert.equal(snapshot.orders, 4);
  assert.equal(snapshot.realizedProfit, -3);
  assert.equal(snapshot.totalProfitPercent, -0.6);
  assert.equal(snapshot.winrate, 0.5);
  assert.equal(snapshot.profitFactor, 0.4);
  assert.equal(snapshot.firstTradeDate, "2026-07-17 14:01:00");
  assert.equal(snapshot.latestTradeDate, "2026-07-18 04:00:00");
  assert.equal(snapshot.latestCloseDate, "2026-07-18 03:00:00");
  db.close();
});

test("SQLite performance preserves unavailable P&L when schema has no profit column", () => {
  const db = new DatabaseSync(":memory:");
  db.exec("CREATE TABLE trades (id INTEGER PRIMARY KEY, is_open BOOLEAN NOT NULL);");
  const snapshot = readSqlitePerformance(db);
  assert.equal(snapshot.totalTrades, 0);
  assert.equal(snapshot.realizedProfit, null);
  assert.equal(snapshot.totalProfit, null);
  db.close();
});
