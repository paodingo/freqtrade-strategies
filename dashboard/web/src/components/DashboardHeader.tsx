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
  const reliabilityStatus = data?.data_reliability.overall_status || "incomplete";
  const reliabilityLabels = {
    reliable: "数据可靠",
    degraded: "数据降级",
    stale: "数据已过期",
    incomplete: "数据不完整",
    blocked: "判断已熔断",
  } as const;
  const healthTone = reliabilityStatus === "reliable" ? "good" : reliabilityStatus === "blocked" ? "blocked" : "warn";
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
        <div className={`deployment-pill ${data?.deployment.available ? "good" : "warn"}`}>
          <span>DEPLOY</span>
          <code>{data?.deployment.git_short_sha || "unverified"}</code>
          <small>{data?.deployment.environment || data?.deployment.status_reason || "manifest missing"}</small>
        </div>
        <div className={`connection-pill ${healthTone}`} aria-live="polite">
          <span className="status-pulse" aria-hidden="true" />
          <span>{isFetching ? "同步中" : reliabilityLabels[reliabilityStatus]}</span>
          <time>{formatTimestamp(data?.data_reliability.checked_at || null)}</time>
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
