import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import { formatAge, formatTimestamp } from "../lib/format";

interface FreshnessPanelProps {
  data: StrategyRegistryResponse;
}

export function FreshnessPanel({ data }: FreshnessPanelProps) {
  return (
    <section className="freshness-panel" aria-labelledby="freshness-title">
      <div className="section-copy">
        <p className="eyebrow">FRESHNESS</p>
        <h2 id="freshness-title">这些数据有多新？</h2>
        <p>实时状态、部署清单和研究结论各有自己的更新时间，页面不会把它们混为一谈。</p>
      </div>
      <div className="freshness-track">
        <article>
          <span className="track-index">01</span>
          <div><strong>运行观察</strong><p>{formatTimestamp(data.freshness.observed_at)}</p></div>
          <span className="freshness-value">刚刚</span>
        </article>
        <article>
          <span className="track-index">02</span>
          <div><strong>部署清单</strong><p>{formatTimestamp(data.registry.generated_at)}</p></div>
          <span className="freshness-value">{formatAge(data.freshness.registry_age_seconds)}</span>
        </article>
        <article>
          <span className="track-index">03</span>
          <div><strong>研究状态</strong><p>{formatTimestamp(data.research.generated_at)}</p></div>
          <span className="freshness-value">{formatAge(data.freshness.research_age_seconds)}</span>
        </article>
      </div>
    </section>
  );
}
