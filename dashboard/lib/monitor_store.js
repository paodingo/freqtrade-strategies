"use strict";

const fs = require("fs");
const path = require("path");
const { DatabaseSync } = require("node:sqlite");

function numeric(value, fallback = null) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function latestOpenTrade(bot) {
  return Array.isArray(bot?.openTrades) && bot.openTrades.length > 0 ? bot.openTrades[0] : null;
}

function tradeSnapshot(trade) {
  return {
    tradeId: trade.trade_id ?? trade.id ?? null,
    pair: trade.pair,
    isShort: Boolean(trade.is_short),
    enterTag: trade.enter_tag || null,
    stakeAmount: numeric(trade.stake_amount),
    amount: numeric(trade.amount),
    openRate: numeric(trade.open_rate),
    currentRate: numeric(trade.current_rate),
    stopLoss: numeric(trade.stop_loss_abs),
    liquidationPrice: numeric(trade.liquidation_price),
    profitAbs: numeric(trade.profit_abs ?? trade.total_profit_abs),
    profitPct: numeric(trade.profit_pct),
    fundingFees: numeric(trade.funding_fees, 0),
    openTimestamp: trade.open_timestamp ?? null,
    openDate: trade.open_date ?? null,
  };
}

class MonitorStore {
  constructor({ dbFile, retentionDays }) {
    this.dbFile = dbFile;
    this.retentionDays = Number(retentionDays || 30);
    fs.mkdirSync(path.dirname(dbFile), { recursive: true });
    this.db = new DatabaseSync(dbFile);
    this.init();
  }

  init() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS history_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sampled_at TEXT NOT NULL,
        generated_at TEXT,
        payload TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_history_samples_sampled_at
        ON history_samples(sampled_at);

      CREATE TABLE IF NOT EXISTS monitor_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info',
        bot_key TEXT,
        label TEXT,
        message TEXT,
        payload TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_monitor_events_timestamp
        ON monitor_events(timestamp);
      CREATE INDEX IF NOT EXISTS idx_monitor_events_type
        ON monitor_events(type);

      CREATE TABLE IF NOT EXISTS alpha_risk_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sampled_at TEXT NOT NULL,
        generated_at TEXT,
        symbol TEXT,
        period TEXT,
        status TEXT,
        risk_level TEXT,
        risk_score REAL,
        risk_summary TEXT,
        payload TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_alpha_risk_samples_sampled_at
        ON alpha_risk_samples(sampled_at);
      CREATE INDEX IF NOT EXISTS idx_alpha_risk_samples_symbol
        ON alpha_risk_samples(symbol);

      CREATE TABLE IF NOT EXISTS regime_router_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sampled_at TEXT NOT NULL,
        generated_at TEXT,
        pair TEXT,
        window_type TEXT,
        confidence REAL,
        allowed_playbook TEXT,
        risk_budget_pct REAL,
        payload TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_regime_router_samples_sampled_at
        ON regime_router_samples(sampled_at);
      CREATE INDEX IF NOT EXISTS idx_regime_router_samples_window_type
        ON regime_router_samples(window_type);
    `);
  }

  close() {
    this.db.close();
  }

  historySnapshot(summary) {
    const sampledAt = new Date().toISOString();
    return {
      generatedAt: summary.generatedAt,
      sampledAt,
      bots: summary.bots.map((bot) => {
        const trade = latestOpenTrade(bot);
        return {
          key: bot.key,
          label: bot.label,
          ok: bot.ok,
          latencyMs: numeric(bot.latencyMs),
          error: bot.error || null,
          state: bot.state,
          runmode: bot.runmode,
          totalBot: numeric(bot.balance?.totalBot),
          freeStake: numeric(bot.balance?.freeStake),
          usedStake: numeric(bot.balance?.usedStake ?? bot.totalStake),
          profitAllCoin: numeric(bot.profitAllCoin),
          currentDrawdown: numeric(bot.currentDrawdown, 0),
          currentDrawdownAbs: numeric(bot.currentDrawdownAbs, 0),
          currentOpenTrades: numeric(bot.currentOpenTrades, 0),
          closedTradeCount: numeric(bot.closedTradeCount, 0),
          fundingFees: numeric(trade?.funding_fees, 0),
          currentRate: numeric(trade?.current_rate),
          openRate: numeric(trade?.open_rate),
          stopLoss: numeric(trade?.stop_loss_abs),
          liquidationPrice: numeric(trade?.liquidation_price),
          openTrades: Array.isArray(bot.openTrades) ? bot.openTrades.map(tradeSnapshot) : [],
        };
      }),
      comparison: summary.comparison,
    };
  }

  appendHistorySnapshot(snapshot, now = Date.now()) {
    this.db.prepare(`
      INSERT INTO history_samples (sampled_at, generated_at, payload)
      VALUES (?, ?, ?)
    `).run(
      snapshot.sampledAt || snapshot.generatedAt,
      snapshot.generatedAt || null,
      JSON.stringify(snapshot),
    );
    this.trimHistory(now);
  }

  readLatestHistory() {
    const row = this.db.prepare(`
      SELECT payload FROM history_samples
      ORDER BY sampled_at DESC
      LIMIT 1
    `).get();
    if (!row) {
      return null;
    }
    return JSON.parse(row.payload);
  }

  readHistory(now = Date.now()) {
    this.trimHistory(now);
    const rows = this.db.prepare(`
      SELECT payload FROM history_samples
      ORDER BY sampled_at ASC
    `).all();
    return rows.map((row) => JSON.parse(row.payload));
  }

  trimHistory(now = Date.now()) {
    const cutoff = new Date(now - this.retentionDays * 24 * 60 * 60 * 1000).toISOString();
    this.db.prepare("DELETE FROM history_samples WHERE sampled_at < ?").run(cutoff);
  }

  recordAlphaRiskSample(sample, now = Date.now()) {
    const sampledAt = sample.sampledAt || new Date().toISOString();
    const payload = {
      ...sample,
      sampledAt,
    };
    this.db.prepare(`
      INSERT INTO alpha_risk_samples (
        sampled_at,
        generated_at,
        symbol,
        period,
        status,
        risk_level,
        risk_score,
        risk_summary,
        payload
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      sampledAt,
      sample.generatedAt || null,
      sample.symbol || null,
      sample.period || null,
      sample.status || null,
      sample.risk?.level || null,
      numeric(sample.risk?.score),
      sample.risk?.summary || null,
      JSON.stringify(payload),
    );
    this.trimAlphaRiskSamples(now);
  }

  readAlphaRiskSamples({ limit = 1000, now = Date.now() } = {}) {
    this.trimAlphaRiskSamples(now);
    const safeLimit = Math.max(1, Math.min(5000, Math.floor(Number(limit) || 1000)));
    const rows = this.db.prepare(`
      SELECT sampled_at, generated_at, payload FROM alpha_risk_samples
      ORDER BY sampled_at ASC, id ASC
      LIMIT ${safeLimit}
    `).all();
    return rows.map((row) => {
      const payload = JSON.parse(row.payload);
      return {
        ...payload,
        sampledAt: payload.sampledAt || row.sampled_at,
        generatedAt: payload.generatedAt || row.generated_at,
      };
    });
  }

  trimAlphaRiskSamples(now = Date.now()) {
    const cutoff = new Date(now - this.retentionDays * 24 * 60 * 60 * 1000).toISOString();
    this.db.prepare("DELETE FROM alpha_risk_samples WHERE sampled_at < ?").run(cutoff);
  }

  recordRegimeRouterSample(sample, now = Date.now()) {
    const sampledAt = sample.sampledAt || new Date().toISOString();
    const payload = {
      ...sample,
      sampledAt,
    };
    this.db.prepare(`
      INSERT INTO regime_router_samples (
        sampled_at,
        generated_at,
        pair,
        window_type,
        confidence,
        allowed_playbook,
        risk_budget_pct,
        payload
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      sampledAt,
      sample.generatedAt || null,
      sample.pair || null,
      sample.windowType || null,
      numeric(sample.confidence),
      sample.allowedPlaybook || null,
      numeric(sample.riskBudgetPct),
      JSON.stringify(payload),
    );
    this.trimRegimeRouterSamples(now);
  }

  readRegimeRouterSamples({ limit = 1000, now = Date.now() } = {}) {
    this.trimRegimeRouterSamples(now);
    const safeLimit = Math.max(1, Math.min(5000, Math.floor(Number(limit) || 1000)));
    const rows = this.db.prepare(`
      SELECT sampled_at, generated_at, payload FROM regime_router_samples
      ORDER BY sampled_at ASC, id ASC
      LIMIT ${safeLimit}
    `).all();
    return rows.map((row) => {
      const payload = JSON.parse(row.payload);
      return {
        ...payload,
        sampledAt: payload.sampledAt || row.sampled_at,
        generatedAt: payload.generatedAt || row.generated_at,
      };
    });
  }

  trimRegimeRouterSamples(now = Date.now()) {
    const cutoff = new Date(now - this.retentionDays * 24 * 60 * 60 * 1000).toISOString();
    this.db.prepare("DELETE FROM regime_router_samples WHERE sampled_at < ?").run(cutoff);
  }

  recordTradeEvent(event) {
    this.recordEvent("trade_event", {
      severity: event.severity || "info",
      timestamp: event.timestamp,
      botKey: event.botKey,
      label: event.label,
      message: event.message,
      payload: event.payload,
    });
  }

  recordAlert(event) {
    this.recordEvent("alert", {
      severity: event.severity || "warning",
      timestamp: event.timestamp,
      botKey: event.botKey,
      label: event.label,
      message: event.message,
      payload: event.payload,
    });
  }

  recordApiLatency(event) {
    this.recordEvent("api_latency", {
      severity: event.ok ? "info" : "error",
      timestamp: event.timestamp,
      botKey: event.botKey,
      label: event.label,
      message: event.ok
        ? `API latency ${event.latencyMs} ms`
        : "API unavailable",
      payload: {
        ok: Boolean(event.ok),
        latencyMs: numeric(event.latencyMs),
        error: event.error || null,
      },
    });
  }

  recordDataFreshness(event) {
    this.recordEvent("data_freshness", {
      severity: event.severity || "info",
      timestamp: event.timestamp,
      botKey: event.botKey,
      label: event.source || event.label,
      message: event.message || `Data freshness ${event.ageSeconds ?? "-"} seconds`,
      payload: {
        source: event.source,
        pair: event.pair,
        timeframe: event.timeframe,
        lastAnalyzed: event.lastAnalyzed,
        ageSeconds: numeric(event.ageSeconds),
      },
    });
  }

  recordEvent(type, event) {
    const payload = event.payload || {};
    this.db.prepare(`
      INSERT INTO monitor_events (timestamp, type, severity, bot_key, label, message, payload)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      event.timestamp || new Date().toISOString(),
      type,
      event.severity || "info",
      event.botKey || null,
      event.label || null,
      event.message || null,
      JSON.stringify(payload),
    );
  }

  readEvents({ limit = 100, type = null } = {}) {
    const safeLimit = Math.max(1, Math.min(500, Math.floor(Number(limit) || 100)));
    const sql = type
      ? `SELECT * FROM monitor_events WHERE type = ? ORDER BY timestamp DESC, id DESC LIMIT ${safeLimit}`
      : `SELECT * FROM monitor_events ORDER BY timestamp DESC, id DESC LIMIT ${safeLimit}`;
    const rows = type ? this.db.prepare(sql).all(type) : this.db.prepare(sql).all();
    return rows.map((row) => ({
      id: row.id,
      timestamp: row.timestamp,
      type: row.type,
      severity: row.severity,
      botKey: row.bot_key,
      label: row.label,
      message: row.message,
      payload: JSON.parse(row.payload || "{}"),
    }));
  }
}

module.exports = {
  MonitorStore,
  numeric,
};
