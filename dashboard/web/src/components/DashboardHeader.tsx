import type { ExpertiseMode } from "../hooks/useDashboardPreferences";
import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import { formatTimestamp } from "../lib/format";

interface DashboardHeaderProps {
  data: StrategyRegistryResponse | undefined;
  expertise: ExpertiseMode;
  isFetching: boolean;
  onExpertiseChange: (mode: ExpertiseMode) => void;
}

export function DashboardHeader({
  data,
  expertise,
  isFetching,
  onExpertiseChange,
}: DashboardHeaderProps) {
  const allRuntimeHealthy = Boolean(data?.strategies.length)
    && data?.strategies.every((strategy) => strategy.runtime.ok);
  const healthTone = allRuntimeHealthy ? "good" : "warn";
  return (
    <header className="dashboard-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">FT</span>
        <div>
          <p className="eyebrow">STRATEGY OBSERVATORY</p>
          <h1>策略观察台</h1>
          <p className="header-deck">先说明现在运行什么，再展开它为什么值得相信。</p>
        </div>
      </div>
      <div className="header-actions">
        <div className={`connection-pill ${healthTone}`} aria-live="polite">
          <span className="status-pulse" aria-hidden="true" />
          <span>{isFetching ? "同步中" : allRuntimeHealthy ? "数据连接正常" : "部分数据待确认"}</span>
          <time>{formatTimestamp(data?.freshness.observed_at || null)}</time>
        </div>
        <div className="segmented-control" aria-label="信息深度">
          <button
            className={expertise === "guided" ? "active" : ""}
            type="button"
            onClick={() => onExpertiseChange("guided")}
          >
            引导模式
          </button>
          <button
            className={expertise === "professional" ? "active" : ""}
            type="button"
            onClick={() => onExpertiseChange("professional")}
          >
            专业模式
          </button>
        </div>
        <a className="legacy-link" href="/">旧版监控</a>
      </div>
    </header>
  );
}
