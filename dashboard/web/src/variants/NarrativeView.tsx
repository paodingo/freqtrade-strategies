import type { StrategyRegistryResponse } from "../api/strategyRegistry";
import type { ExpertiseMode } from "../hooks/useDashboardPreferences";
import { EvidencePanel } from "../components/EvidencePanel";
import { FreshnessPanel } from "../components/FreshnessPanel";
import { MarketPanel } from "../components/MarketPanel";
import { RecentTradesPanel } from "../components/RecentTradesPanel";
import { StrategyComparisonPanel } from "../components/StrategyComparisonPanel";
import { StrategyCard } from "../components/StrategyCard";
import { runtimeStateLabel } from "../lib/format";

interface NarrativeViewProps {
  data: StrategyRegistryResponse;
  expertise: ExpertiseMode;
}

export function NarrativeView({ data, expertise }: NarrativeViewProps) {
  const current = data.strategies.find((strategy) => strategy.role === "current");
  const researchName = data.research.formal_strategy?.name || "研究状态不可用";
  return (
    <main className="variant-view narrative-view">
      <section className="narrative-intro">
        <p className="eyebrow">GUIDED EXPLANATION</p>
        <h2>用四步看懂今天的策略状态</h2>
        <p>先看市场和实际运行，再比较多策略证据，最后确认研究结论有没有授权替换。</p>
      </section>
      <ol className="narrative-steps">
        <li>
          <span className="step-number">01</span>
          <div className="step-copy">
            <p className="eyebrow">现在运行什么</p>
            <h3>{current?.display_name || "未声明当前策略"}</h3>
            <p>{current ? runtimeStateLabel(current.runtime.ok, current.runtime.state) : "Registry 没有 current 角色。"}</p>
            <MarketPanel />
            {current ? <StrategyCard strategy={current} expertise={expertise} featured /> : null}
          </div>
        </li>
        <li>
          <span className="step-number">02</span>
          <div className="step-copy">
            <p className="eyebrow">多策略谁更有优势</p>
            <h3>按收益、风险与样本分别比较</h3>
            <p>某一项领先不等于整体获批；缺失收益证据的策略不会被强行排名。</p>
            <StrategyComparisonPanel data={data} />
            <RecentTradesPanel />
          </div>
        </li>
        <li>
          <span className="step-number">03</span>
          <div className="step-copy">
            <p className="eyebrow">数据是不是最新</p>
            <h3>四类证据分别标注</h3>
            <p>可靠性巡检、运行观察、部署清单和研究快照各自保留时间戳，旧数据不会伪装成实时状态。</p>
            <FreshnessPanel data={data} />
          </div>
        </li>
        <li>
          <span className="step-number">04</span>
          <div className="step-copy">
            <p className="eyebrow">它是否代表研究结论</p>
            <h3>正式研究策略：{researchName}</h3>
            <p>运行通道与正式研究身份不同是允许的；只有治理流程能够批准晋升或替换。</p>
            <EvidencePanel data={data} />
          </div>
        </li>
      </ol>
    </main>
  );
}
