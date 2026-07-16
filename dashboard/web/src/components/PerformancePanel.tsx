import type { PerformanceObservation } from "../api/strategyRegistry";
import { formatMoney, formatPercent, valueTone } from "../lib/format";

interface PerformancePanelProps {
  performance: PerformanceObservation;
  compact?: boolean;
}

export function PerformancePanel({ performance, compact = false }: PerformancePanelProps) {
  if (!performance.available) {
    return (
      <section className={`performance-panel unavailable ${compact ? "compact" : ""}`} aria-label="模拟盘收益">
        <div>
          <span className="performance-label">SIMULATED P&amp;L</span>
          <strong>收益数据不可用</strong>
        </div>
        <p>运行 API 恢复后显示；当前不以 0 代替未知收益。</p>
      </section>
    );
  }

  return (
    <section className={`performance-panel ${compact ? "compact" : ""}`} aria-label="模拟盘收益">
      <div className="performance-total">
        <span className="performance-label">模拟盘总收益</span>
        <strong className={`value-${valueTone(performance.total_profit_abs)}`}>
          {formatMoney(performance.total_profit_abs, performance.currency)}
        </strong>
        <small>{formatPercent(performance.total_profit_pct)}</small>
      </div>
      <dl>
        <div><dt>已实现</dt><dd>{formatMoney(performance.realized_profit_abs, performance.currency)}</dd></div>
        <div><dt>当前浮盈亏</dt><dd>{formatMoney(performance.unrealized_profit_abs, performance.currency)}</dd></div>
        <div><dt>交易数</dt><dd>{performance.trade_count ?? "—"}</dd></div>
      </dl>
    </section>
  );
}
