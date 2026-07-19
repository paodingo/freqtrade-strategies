import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import { formatAge, formatTimestamp } from "../lib/format";

interface FreshnessPanelProps {
  data: StrategyRegistryResponse;
}

export function FreshnessPanel({ data }: FreshnessPanelProps) {
  const reliability = data.data_reliability;
  const reliabilityLabels = {
    reliable: "可靠",
    degraded: "降级可观察",
    stale: "已过期",
    incomplete: "不完整",
    blocked: "已熔断",
  } as const;
  return (
    <section className="freshness-panel" aria-labelledby="freshness-title">
      <div className="section-copy">
        <p className="eyebrow">FRESHNESS</p>
        <h2 id="freshness-title">这些数据有多新？</h2>
        <p>
          运行状态、行情、部署清单和研究结论分别校验；缺失值不会被伪装成 0。
          {!reliability.decision_allowed ? " 当前数据已禁止用于新的策略判断，模拟机器人仍独立运行。" : ""}
        </p>
      </div>
      <div className="freshness-track">
        <article>
          <span className="track-index">01</span>
          <div>
            <strong>可靠性控制器</strong>
            <p>{formatTimestamp(reliability.checked_at)}</p>
          </div>
          <span className={`reliability-badge ${reliability.overall_status}`}>
            {reliabilityLabels[reliability.overall_status]}
            {reliability.summary.issue_count > 0 ? ` · ${reliability.summary.issue_count} 项` : ""}
          </span>
        </article>
        <article>
          <span className="track-index">02</span>
          <div><strong>运行观察</strong><p>{formatTimestamp(data.freshness.observed_at)}</p></div>
          <span className="freshness-value">刚刚</span>
        </article>
        <article>
          <span className="track-index">03</span>
          <div><strong>部署清单</strong><p>{formatTimestamp(data.registry.generated_at)}</p></div>
          <span className="freshness-value">{formatAge(data.freshness.registry_age_seconds)}</span>
        </article>
        <article>
          <span className="track-index">04</span>
          <div><strong>研究状态</strong><p>{formatTimestamp(data.research.generated_at)}</p></div>
          <span className="freshness-value">{formatAge(data.freshness.research_age_seconds)}</span>
        </article>
      </div>
    </section>
  );
}
