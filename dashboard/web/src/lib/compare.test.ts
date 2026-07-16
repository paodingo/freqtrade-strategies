import { describe, expect, it } from "vitest";

import type { StrategyRecord } from "../api/strategyRegistry";
import { compareStrategies } from "./compare";

function strategy(id: string, total: number, drawdown: number, winRate: number, closed = 40): StrategyRecord {
  return {
    strategy_id: id,
    display_name: id,
    version: null,
    role: id === "a" ? "current" : "shadow",
    stage: "dry_run",
    strategy_class: null,
    description: "fixture",
    capabilities: { live_status: true, positions: true, performance: true, research_evidence: true },
    runtime: {
      bot_key: id,
      source: "freqtrade",
      observed_at: "2026-01-01T00:00:00Z",
      ok: true,
      state: "running",
      runmode: "dry_run",
      dry_run: true,
      bot_name: id,
      latency_ms: 1,
      open_trade_count: 0,
      status_reason: null,
    },
    performance: {
      available: true,
      currency: "USDT",
      realized_profit_abs: total,
      unrealized_profit_abs: 0,
      total_profit_abs: total,
      total_profit_pct: total,
      trade_count: closed,
      closed_trade_count: closed,
      win_rate: winRate,
      profit_factor: 1,
      current_drawdown_abs: 0,
      max_drawdown_abs: drawdown,
      status_reason: null,
    },
  };
}

describe("compareStrategies", () => {
  it("separates profit, risk and win-rate leaders", () => {
    const analysis = compareStrategies([strategy("a", 12, 8, 0.55), strategy("b", 9, 4, 0.7)]);
    expect(analysis.profitLeaderId).toBe("a");
    expect(analysis.drawdownLeaderId).toBe("b");
    expect(analysis.winRateLeaderId).toBe("b");
  });

  it("withholds rankings when fewer than two strategies have evidence", () => {
    const analysis = compareStrategies([strategy("a", 12, 8, 0.55)]);
    expect(analysis.profitLeaderId).toBeNull();
    expect(analysis.comparableCount).toBe(1);
  });
});
