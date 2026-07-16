import { describe, expect, it } from "vitest";

import { formatAge, formatMoney, formatPercent, roleLabel, runtimeStateLabel, stageLabel } from "./format";

describe("dashboard formatting", () => {
  it("keeps specialist identifiers behind plain-language labels", () => {
    expect(roleLabel("current")).toBe("当前运行");
    expect(stageLabel("dry_run")).toBe("模拟运行");
  });

  it("distinguishes unavailable data from an unknown live state", () => {
    expect(runtimeStateLabel(false, null)).toBe("数据源不可用");
    expect(runtimeStateLabel(true, null)).toBe("状态未知");
  });

  it("uses concise relative time buckets", () => {
    expect(formatAge(4)).toBe("刚刚");
    expect(formatAge(75)).toBe("1 分钟前");
    expect(formatAge(null)).toBe("未知");
  });

  it("formats signed simulated profit without turning unknown into zero", () => {
    expect(formatMoney(12.5, "USDT")).toBe("+12.5 USDT");
    expect(formatMoney(null, "USDT")).toBe("—");
    expect(formatPercent(-1.25)).toBe("-1.25%");
  });
});
