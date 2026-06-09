"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { MonitorStore } = require("../dashboard/lib/monitor_store");

function tempDbPath() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "freqtrade-monitor-"));
  return {
    dir,
    dbFile: path.join(dir, "monitor.sqlite"),
  };
}

function summaryFixture(overrides = {}) {
  return {
    generatedAt: "2026-06-10T00:00:00.000Z",
    bots: [
      {
        key: "v62",
        label: "V6.2",
        ok: true,
        latencyMs: 42,
        state: "running",
        runmode: "dry_run",
        balance: { totalBot: 10000, freeStake: 6200, usedStake: 1500 },
        profitAllCoin: 12.5,
        currentDrawdown: 0,
        currentDrawdownAbs: 0,
        currentOpenTrades: 1,
        closedTradeCount: 0,
        openTrades: [
          {
            trade_id: 123,
            pair: "BTC/USDT:USDT",
            is_short: true,
            stake_amount: 1500,
            open_rate: 100,
            current_rate: 99,
            stop_loss_abs: 104,
            liquidation_price: 120,
            funding_fees: 0,
          },
        ],
      },
    ],
    comparison: null,
    ...overrides,
  };
}

test("MonitorStore persists history samples and monitoring event types in SQLite", () => {
  const { dir, dbFile } = tempDbPath();
  let store;
  try {
    store = new MonitorStore({ dbFile, retentionDays: 30 });

    const snapshot = store.historySnapshot(summaryFixture());
    store.appendHistorySnapshot(snapshot);
    store.recordTradeEvent({
      timestamp: snapshot.sampledAt,
      botKey: "v62",
      label: "V6.2",
      message: "opened BTC/USDT:USDT",
      payload: { tradeId: 123 },
    });
    store.recordAlert({
      severity: "warning",
      botKey: "v62",
      label: "V6.2",
      message: "API latency high",
      payload: { latencyMs: 4500 },
    });
    store.recordApiLatency({
      botKey: "v62",
      label: "V6.2",
      ok: true,
      latencyMs: 42,
    });
    store.recordDataFreshness({
      source: "V6.2",
      pair: "BTC/USDT:USDT",
      timeframe: "1h",
      lastAnalyzed: "2026-06-10T00:00:00.000Z",
      ageSeconds: 30,
    });

    const history = store.readHistory();
    assert.equal(history.length, 1);
    assert.equal(history[0].bots[0].latencyMs, 42);
    assert.equal(history[0].bots[0].openTrades[0].tradeId, 123);

    const eventTypes = store.readEvents({ limit: 10 }).map((event) => event.type).sort();
    assert.deepEqual(eventTypes, [
      "alert",
      "api_latency",
      "data_freshness",
      "trade_event",
    ]);
  } finally {
    store?.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("MonitorStore trims history samples outside retention window", () => {
  const { dir, dbFile } = tempDbPath();
  let store;
  try {
    store = new MonitorStore({ dbFile, retentionDays: 1 });
    store.appendHistorySnapshot({
      generatedAt: "2026-06-08T00:00:00.000Z",
      sampledAt: "2026-06-08T00:00:00.000Z",
      bots: [],
      comparison: null,
    }, Date.parse("2026-06-10T00:00:00.000Z"));
    store.appendHistorySnapshot({
      generatedAt: "2026-06-10T00:00:00.000Z",
      sampledAt: "2026-06-10T00:00:00.000Z",
      bots: [],
      comparison: null,
    }, Date.parse("2026-06-10T00:00:00.000Z"));

    const history = store.readHistory(Date.parse("2026-06-10T00:00:00.000Z"));
    assert.equal(history.length, 1);
    assert.equal(history[0].sampledAt, "2026-06-10T00:00:00.000Z");
  } finally {
    store?.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
