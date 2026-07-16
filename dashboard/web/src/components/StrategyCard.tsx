import type { ExpertiseMode } from "../hooks/useDashboardPreferences";
import type { StrategyRecord } from "../api/strategyRegistry";
import { roleLabel, runtimeStateLabel, stageLabel } from "../lib/format";
import { PerformancePanel } from "./PerformancePanel";

interface StrategyCardProps {
  strategy: StrategyRecord;
  expertise: ExpertiseMode;
  featured?: boolean;
}

export function StrategyCard({ strategy, expertise, featured = false }: StrategyCardProps) {
  const stateLabel = runtimeStateLabel(strategy.runtime.ok, strategy.runtime.state);
  return (
    <article className={`strategy-card ${featured ? "featured" : ""}`}>
      <div className="strategy-card-head">
        <div>
          <div className="badge-row">
            <span className={`role-badge role-${strategy.role}`}>{roleLabel(strategy.role)}</span>
            <span className="stage-badge">{stageLabel(strategy.stage)}</span>
          </div>
          <h3>{strategy.display_name}</h3>
          <p>{strategy.description}</p>
        </div>
        <div className={`runtime-orb ${strategy.runtime.ok ? "good" : "warn"}`} aria-label={stateLabel}>
          <span aria-hidden="true" />
          {stateLabel}
        </div>
      </div>
      {strategy.role === "current" ? <PerformancePanel performance={strategy.performance} /> : null}
      <dl className="strategy-metrics">
        <div>
          <dt>运行模式</dt>
          <dd>{strategy.runtime.dry_run ? "模拟运行" : strategy.runtime.runmode || "未知"}</dd>
        </div>
        <div>
          <dt>当前持仓</dt>
          <dd>{strategy.runtime.open_trade_count ?? "—"}</dd>
        </div>
        <div>
          <dt>数据来源</dt>
          <dd>{strategy.runtime.source === "freqtrade" ? "Freqtrade API" : "SQLite 观察"}</dd>
        </div>
      </dl>
      {expertise === "professional" ? (
        <dl className="technical-grid">
          <div><dt>strategy_id</dt><dd>{strategy.strategy_id}</dd></div>
          <div><dt>strategy_class</dt><dd>{strategy.strategy_class || "由运行 API 决定"}</dd></div>
          <div><dt>bot_key</dt><dd>{strategy.runtime.bot_key}</dd></div>
          <div><dt>latency</dt><dd>{strategy.runtime.latency_ms === null ? "—" : `${strategy.runtime.latency_ms} ms`}</dd></div>
        </dl>
      ) : (
        <p className="plain-explanation">
          {strategy.role === "current"
            ? "这是当前展示主通道；它是否可以被替换，仍由独立证据和人工批准决定。"
            : "这是对照或观察通道；出现数据不代表它已经成为正式策略。"}
        </p>
      )}
    </article>
  );
}
