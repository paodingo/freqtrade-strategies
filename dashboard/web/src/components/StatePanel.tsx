interface StatePanelProps {
  state: "loading" | "error" | "empty";
  onRetry?: () => void;
}

const COPY = {
  loading: {
    label: "正在建立证据链",
    title: "读取策略身份与运行状态",
    body: "页面会保留清晰的加载状态，不用旧数据冒充最新数据。",
  },
  error: {
    label: "连接未完成",
    title: "暂时无法读取 Strategy Registry",
    body: "当前不会猜测或补造策略数据。请重试，或通过旧版监控检查运行服务。",
  },
  empty: {
    label: "Registry 为空",
    title: "尚未声明可展示的运行策略",
    body: "这是一种安全状态：在部署清单发布前，页面不会自行选择版本号最大的策略。",
  },
} as const;

export function StatePanel({ state, onRetry }: StatePanelProps) {
  const copy = COPY[state];
  return (
    <main className="state-stage" aria-busy={state === "loading"}>
      <section className={`state-panel ${state}`}>
        <span className="state-code">{state === "loading" ? "SYNC" : state.toUpperCase()}</span>
        <p className="eyebrow">{copy.label}</p>
        <h2>{copy.title}</h2>
        <p>{copy.body}</p>
        {state === "loading" ? (
          <div className="loading-rail" aria-hidden="true"><span /></div>
        ) : null}
        {state === "error" && onRetry ? (
          <button className="primary-button" type="button" onClick={onRetry}>重新读取</button>
        ) : null}
      </section>
    </main>
  );
}
