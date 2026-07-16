import type { StrategyRegistryResponse } from "../api/strategyRegistry";

interface EvidencePanelProps {
  data: StrategyRegistryResponse;
}

export function EvidencePanel({ data }: EvidencePanelProps) {
  const formal = data.research.formal_strategy;
  return (
    <section className="evidence-panel" aria-labelledby="evidence-title">
      <div className="section-copy">
        <p className="eyebrow">EVIDENCE BOUNDARY</p>
        <h2 id="evidence-title">运行身份不等于研究结论</h2>
        <p>Dashboard 只展示权威来源已经声明的身份，不参与策略晋升。</p>
      </div>
      <div className="evidence-grid">
        <article>
          <span className="evidence-label">当前运行主通道</span>
          <strong>{data.strategies.find((strategy) => strategy.role === "current")?.display_name || "未声明"}</strong>
          <p>来源：{data.registry.registry_id}</p>
        </article>
        <article>
          <span className="evidence-label">正式研究策略</span>
          <strong>{formal?.name || "研究状态不可用"}</strong>
          <p>{formal?.path || "未读取到研究工件"}</p>
        </article>
        <article>
          <span className="evidence-label">完整性状态</span>
          <strong>{data.research.state_conflict_count === 0 ? "未记录冲突" : `${data.research.state_conflict_count ?? "—"} 个冲突`}</strong>
          <p>{formal?.sha256 ? `SHA-256 ${formal.sha256.slice(0, 12)}…` : "没有可展示的指纹"}</p>
        </article>
      </div>
    </section>
  );
}
