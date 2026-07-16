import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import { compareStrategies } from "../lib/compare";
import { formatMoney, formatPercent, roleLabel } from "../lib/format";

interface StrategyComparisonPanelProps {
  data: StrategyRegistryResponse;
}

export function StrategyComparisonPanel({ data }: StrategyComparisonPanelProps) {
  const analysis = compareStrategies(data.strategies);
  const nameById = new Map(data.strategies.map((strategy) => [strategy.strategy_id, strategy.display_name]));
  const leaderName = (id: string | null) => id ? nameById.get(id) || id : "证据不足";
  return (
    <section className="comparison-panel" aria-labelledby="comparison-title">
      <div className="section-copy horizontal">
        <div>
          <p className="eyebrow">STRATEGY COMPARISON</p>
          <h2 id="comparison-title">当前策略优劣，不只看收益</h2>
        </div>
        <p>{analysis.comparableCount >= 2
          ? `${analysis.comparableCount} 个策略具备可比收益证据；结论仍受模拟盘样本限制。`
          : `仅 ${analysis.comparableCount}/${analysis.totalCount} 个策略具备完整收益证据，暂不能判断总体优劣。`}</p>
      </div>
      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <thead><tr><th>策略</th><th>角色</th><th>总收益</th><th>浮盈亏</th><th>最大回撤</th><th>胜率</th><th>利润因子</th><th>平仓样本</th></tr></thead>
          <tbody>{data.strategies.map((strategy) => (
            <tr key={strategy.strategy_id}>
              <td><strong>{strategy.display_name}</strong><small>{strategy.strategy_id}</small></td>
              <td>{roleLabel(strategy.role)}</td>
              <td>{formatMoney(strategy.performance.total_profit_abs, strategy.performance.currency)}</td>
              <td>{formatMoney(strategy.performance.unrealized_profit_abs, strategy.performance.currency)}</td>
              <td>{formatMoney(strategy.performance.max_drawdown_abs, strategy.performance.currency)}</td>
              <td>{strategy.performance.win_rate === null ? "—" : formatPercent(strategy.performance.win_rate * 100)}</td>
              <td>{strategy.performance.profit_factor?.toFixed(2) ?? "—"}</td>
              <td>{strategy.performance.closed_trade_count ?? "—"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="comparison-insights">
        <article><span>收益领先</span><strong>{leaderName(analysis.profitLeaderId)}</strong></article>
        <article><span>回撤较低</span><strong>{leaderName(analysis.drawdownLeaderId)}</strong></article>
        <article><span>胜率较高</span><strong>{leaderName(analysis.winRateLeaderId)}</strong></article>
        <article className={analysis.sampleWarning ? "warning" : ""}><span>样本判断</span><strong>{analysis.sampleWarning ? "至少一个策略不足 30 笔" : "样本门槛已满足"}</strong></article>
      </div>
    </section>
  );
}
