import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import type { ExpertiseMode } from "../hooks/useDashboardPreferences";
import { EvidencePanel } from "../components/EvidencePanel";
import { FreshnessPanel } from "../components/FreshnessPanel";
import { PerformancePanel } from "../components/PerformancePanel";
import { MarketPanel } from "../components/MarketPanel";
import { StrategyComparisonPanel } from "../components/StrategyComparisonPanel";
import { StrategyCard } from "../components/StrategyCard";
import { runtimeStateLabel, stageLabel } from "../lib/format";

interface CockpitViewProps {
  data: StrategyRegistryResponse;
  expertise: ExpertiseMode;
}

export function CockpitView({ data, expertise }: CockpitViewProps) {
  const current = data.strategies.find((strategy) => strategy.role === "current");
  const supporting = data.strategies.filter((strategy) => strategy.strategy_id !== current?.strategy_id);
  return (
    <main className="variant-view cockpit-view">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">CURRENT RUNTIME IDENTITY</p>
          <h2>{current?.display_name || "未声明当前策略"}</h2>
          <p className="hero-summary">
            {current
              ? `当前处于${stageLabel(current.stage)}；页面身份来自部署清单，运行状态来自 ${current.runtime.source === "freqtrade" ? "Freqtrade API" : "SQLite"}。`
              : "Strategy Registry 没有声明当前运行通道。"}
          </p>
          <div className="hero-actions">
            <a className="primary-button" href="#strategy-lanes">查看运行通道</a>
            <a className="secondary-button" href="#evidence-boundary">理解证据边界</a>
          </div>
        </div>
        <div className="hero-status" aria-label="当前运行摘要">
          <span className="hero-status-label">SYSTEM READ</span>
          <strong>{current ? runtimeStateLabel(current.runtime.ok, current.runtime.state) : "未声明"}</strong>
          {current ? <PerformancePanel performance={current.performance} compact /> : null}
          <dl>
            <div><dt>刷新节奏</dt><dd>{data.freshness.refresh_hint_seconds}s</dd></div>
            <div><dt>运行模式</dt><dd>{current?.runtime.dry_run ? "DRY RUN" : current?.runtime.runmode || "—"}</dd></div>
            <div><dt>持仓数</dt><dd>{current?.runtime.open_trade_count ?? "—"}</dd></div>
          </dl>
        </div>
      </section>

      <MarketPanel />

      <section className="strategy-section" id="strategy-lanes" aria-labelledby="strategy-lanes-title">
        <div className="section-copy horizontal">
          <div>
            <p className="eyebrow">RUNTIME LANES</p>
            <h2 id="strategy-lanes-title">谁在运行，谁只是在观察？</h2>
          </div>
          <p>角色由 Registry 明确声明，不再依赖数组顺序或版本号大小。</p>
        </div>
        <div className="strategy-grid">
          {current ? <StrategyCard strategy={current} expertise={expertise} featured /> : null}
          {supporting.map((strategy) => (
            <StrategyCard key={strategy.strategy_id} strategy={strategy} expertise={expertise} />
          ))}
        </div>
      </section>

      <StrategyComparisonPanel data={data} />

      <FreshnessPanel data={data} />
      <div id="evidence-boundary">
        {expertise === "professional" ? (
          <EvidencePanel data={data} />
        ) : (
          <details className="guided-disclosure">
            <summary>为什么“当前运行策略”和“正式研究策略”可能不同？</summary>
            <EvidencePanel data={data} />
          </details>
        )}
      </div>
    </main>
  );
}
