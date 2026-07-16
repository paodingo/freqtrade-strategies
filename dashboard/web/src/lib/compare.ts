import type { StrategyRecord } from "../api/strategyRegistry";

export interface ComparisonAnalysis {
  comparableCount: number;
  totalCount: number;
  profitLeaderId: string | null;
  drawdownLeaderId: string | null;
  winRateLeaderId: string | null;
  sampleWarning: boolean;
}

function leader(
  strategies: StrategyRecord[],
  value: (strategy: StrategyRecord) => number | null,
  direction: "high" | "low",
): string | null {
  const candidates = strategies
    .map((strategy) => ({ strategy, value: value(strategy) }))
    .filter((entry): entry is { strategy: StrategyRecord; value: number } => entry.value !== null);
  if (candidates.length < 2) return null;
  candidates.sort((left, right) => direction === "high" ? right.value - left.value : left.value - right.value);
  return candidates[0].strategy.strategy_id;
}

export function compareStrategies(strategies: StrategyRecord[]): ComparisonAnalysis {
  const comparable = strategies.filter((strategy) => strategy.performance.available);
  return {
    comparableCount: comparable.length,
    totalCount: strategies.length,
    profitLeaderId: leader(comparable, (strategy) => strategy.performance.total_profit_abs, "high"),
    drawdownLeaderId: leader(comparable, (strategy) => strategy.performance.max_drawdown_abs, "low"),
    winRateLeaderId: leader(comparable, (strategy) => strategy.performance.win_rate, "high"),
    sampleWarning: comparable.length < 2
      || comparable.some((strategy) => (strategy.performance.closed_trade_count ?? 0) < 30),
  };
}
