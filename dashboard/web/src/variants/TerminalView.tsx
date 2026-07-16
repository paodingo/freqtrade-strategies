import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import type { ExpertiseMode } from "../hooks/useDashboardPreferences";
import { EvidencePanel } from "../components/EvidencePanel";
import { FreshnessPanel } from "../components/FreshnessPanel";
import { MarketPanel } from "../components/MarketPanel";
import { StrategyComparisonPanel } from "../components/StrategyComparisonPanel";
import { formatMoney, roleLabel, runtimeStateLabel, stageLabel } from "../lib/format";

interface TerminalViewProps {
  data: StrategyRegistryResponse;
  expertise: ExpertiseMode;
}

export function TerminalView({ data, expertise }: TerminalViewProps) {
  return (
    <main className="variant-view terminal-view">
      <section className="terminal-shell" aria-labelledby="terminal-title">
        <div className="terminal-titlebar">
          <div><span /><span /><span /></div>
          <p id="terminal-title">runtime.registry / {data.registry.registry_id}</p>
          <span>LIVE READ</span>
        </div>
        <div className="terminal-command">
          <span>$</span>
          <code>observe strategies --roles --runtime --freshness</code>
        </div>
        <div className="terminal-table-wrap">
          <table className="terminal-table">
            <thead>
              <tr>
                <th>ROLE</th>
                <th>STRATEGY</th>
                <th>STAGE</th>
                <th>RUNTIME</th>
                <th>TOTAL P&amp;L</th>
                <th>OPEN P&amp;L</th>
                <th>TRADES</th>
                <th>SOURCE</th>
                <th>CLASS</th>
              </tr>
            </thead>
            <tbody>
              {data.strategies.map((strategy) => (
                <tr key={strategy.strategy_id}>
                  <td><span className={`terminal-role role-${strategy.role}`}>{roleLabel(strategy.role)}</span></td>
                  <td><strong>{strategy.display_name}</strong><small>{strategy.strategy_id}</small></td>
                  <td>{stageLabel(strategy.stage)}</td>
                  <td className={strategy.runtime.ok ? "terminal-good" : "terminal-warn"}>
                    {runtimeStateLabel(strategy.runtime.ok, strategy.runtime.state)}
                  </td>
                  <td>{formatMoney(strategy.performance.total_profit_abs, strategy.performance.currency)}</td>
                  <td>{formatMoney(strategy.performance.unrealized_profit_abs, strategy.performance.currency)}</td>
                  <td>{strategy.performance.trade_count ?? "—"}</td>
                  <td>{strategy.runtime.source}</td>
                  <td><code>{strategy.strategy_class || "runtime-resolved"}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="terminal-footer">
          <code>refresh={data.freshness.refresh_hint_seconds}s</code>
          <code>strategies={data.strategies.length}</code>
          <code>research={data.research.available ? "available" : "unavailable"}</code>
          <code>mode={expertise}</code>
        </div>
      </section>
      <MarketPanel />
      <StrategyComparisonPanel data={data} />
      <FreshnessPanel data={data} />
      <EvidencePanel data={data} />
    </main>
  );
}
