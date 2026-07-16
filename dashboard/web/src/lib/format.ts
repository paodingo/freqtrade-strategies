const ROLE_LABELS = {
  current: "当前运行",
  benchmark: "基准",
  shadow: "影子观察",
  candidate: "研究候选",
  retired: "已退役",
} as const;

const STAGE_LABELS = {
  research: "研究中",
  approved: "已批准",
  dry_run: "模拟运行",
  live: "实盘",
  retired: "已退役",
} as const;

export function roleLabel(role: keyof typeof ROLE_LABELS): string {
  return ROLE_LABELS[role];
}

export function stageLabel(stage: keyof typeof STAGE_LABELS): string {
  return STAGE_LABELS[stage];
}

export function runtimeStateLabel(ok: boolean, state: string | null): string {
  if (!ok) return "数据源不可用";
  if (state === "running") return "运行中";
  if (state === "paused") return "已暂停";
  if (state === "stopped") return "已停止";
  return state || "状态未知";
}

export function formatAge(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "未知";
  if (seconds < 10) return "刚刚";
  if (seconds < 60) return `${Math.round(seconds)} 秒前`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时前`;
  return `${Math.round(seconds / 86400)} 天前`;
}

export function formatTimestamp(value: string | null): string {
  if (!value) return "未知";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatMoney(value: number | null, currency = "USDT"): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value)} ${currency}`;
}

export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function valueTone(value: number | null): "positive" | "negative" | "neutral" {
  if (value === null || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}
