"use strict";

function numeric(value, fallback = null) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function guardrail(key, label, level, note) {
  return { key, label, level, note };
}

function botByKey(bots, key) {
  return (Array.isArray(bots) ? bots : []).find((bot) => bot?.key === key) || null;
}

function benchmarkAction(bot, overrides = {}) {
  return {
    botKey: bot?.key || "v65",
    label: bot?.label || "Benchmark（基准策略）",
    role: "benchmark",
    allowFreshEntries: true,
    recommendedAction: "keep_running",
    allowedTags: ["ranging_long", "ranging_short", "trending_long", "trending_short"],
    blockedTags: [],
    maxStakeMultiplier: 1,
    notes: [`除非进入 risk-off（风险下线）窗口，${bot?.label || "Benchmark（基准策略）"} 继续作为赚钱基准运行。`],
    ...overrides,
  };
}

function challengerAction(bot, overrides = {}) {
  return {
    botKey: bot?.key || "v66",
    label: bot?.label || "Challenger（挑战策略）",
    role: "challenger",
    allowFreshEntries: false,
    recommendedAction: "block_new_entries",
    allowedTags: [],
    blockedTags: ["ranging_long", "ranging_short", "trending_long", "trending_short"],
    maxStakeMultiplier: 0,
    notes: [`${bot?.label || "Challenger（挑战策略）"} 等待更干净的市场窗口再放行新开仓。`],
    ...overrides,
  };
}

function buildTradeSupervisorDecision({ regimeRouter = null, bots = [], generatedAt = null } = {}) {
  const windowType = regimeRouter?.windowType || "unknown";
  const allowedPlaybook = regimeRouter?.allowedPlaybook || "flat";
  const riskBudgetPct = numeric(regimeRouter?.riskBudgetPct, 0);
  const policy = regimeRouter?.policy || {};
  const v65 = botByKey(bots, "v65");
  const v66 = botByKey(bots, "v66");
  const benchmarkLabel = v65?.label || "Benchmark（基准策略）";
  const challengerLabel = v66?.label || "Challenger（挑战策略）";
  const maxStakeMultiplier = numeric(policy.maxStakeMultiplier, 0);
  const shared = {
    generatedAt: generatedAt || new Date().toISOString(),
    windowType,
    allowedPlaybook,
    confidence: numeric(regimeRouter?.confidence, 0),
    riskBudgetPct,
    sourceStatus: regimeRouter?.status || "unknown",
    regimeGeneratedAt: regimeRouter?.generatedAt || null,
    maxNewStakePct: 0,
    guardrails: [],
    actions: {
      v65: benchmarkAction(v65),
      v66: challengerAction(v66),
    },
  };

  if (windowType === "capitulation") {
    return {
      ...shared,
      mode: "risk_off",
      systemAction: "reduce_risk",
      summary: "出现 capitulation（踩踏）或数据压力：进入 risk-off（风险下线），暂停所有新开仓，只管理已有仓位。",
      actions: {
        v65: benchmarkAction(v65, {
          allowFreshEntries: false,
          recommendedAction: "manage_existing_only",
          allowedTags: [],
          blockedTags: ["ranging_long", "ranging_short", "trending_long", "trending_short"],
          maxStakeMultiplier: 0,
          notes: ["风险下线时，基准策略也暂停新开仓。"],
        }),
        v66: challengerAction(v66, {
          recommendedAction: "manage_existing_only",
          notes: ["瀑布/踩踏窗口不要继续加风险。"],
        }),
      },
      guardrails: [
        guardrail("capitulation_flat", "风险下线", "danger", "等波动降温前，阻止所有新开仓。"),
      ],
    };
  }

  if (windowType === "downtrend" && allowedPlaybook === "trend_short") {
    return {
      ...shared,
      mode: "attack",
      systemAction: "route",
      maxNewStakePct: riskBudgetPct,
      summary: `下跌趋势可执行：${challengerLabel} 只允许趋势做空入场。`,
      actions: {
        v65: benchmarkAction(v65),
        v66: challengerAction(v66, {
          allowFreshEntries: true,
          recommendedAction: "allow_trend_short",
          allowedTags: ["trending_short"],
          blockedTags: ["ranging_long", "ranging_short", "trending_long"],
          maxStakeMultiplier,
          notes: ["当前窗口只匹配趋势做空。"],
        }),
      },
      guardrails: [
        guardrail("downtrend_short_only", "只走做空路由", "warning", "下跌压力下阻止震荡做多和趋势做多。"),
      ],
    };
  }

  if (windowType === "range" && allowedPlaybook === "range_edge") {
    return {
      ...shared,
      mode: "range",
      systemAction: "route",
      maxNewStakePct: riskBudgetPct,
      summary: `震荡区间可执行：${challengerLabel} 只允许区间边缘入场。`,
      actions: {
        v65: benchmarkAction(v65),
        v66: challengerAction(v66, {
          allowFreshEntries: true,
          recommendedAction: "allow_range_edge",
          allowedTags: ["ranging_long", "ranging_short"],
          blockedTags: ["trending_long", "trending_short"],
          maxStakeMultiplier,
          notes: ["当前窗口只匹配区间边缘交易。"],
        }),
      },
      guardrails: [
        guardrail("range_edges_only", "只做区间边缘", "info", "低波动震荡里不追趋势入场。"),
      ],
    };
  }

  if (windowType === "uptrend" && allowedPlaybook === "trend_long") {
    return {
      ...shared,
      mode: "attack",
      systemAction: "route",
      maxNewStakePct: riskBudgetPct,
      summary: `上涨趋势可执行：${challengerLabel} 只允许趋势做多入场。`,
      actions: {
        v65: benchmarkAction(v65),
        v66: challengerAction(v66, {
          allowFreshEntries: true,
          recommendedAction: "allow_trend_long",
          allowedTags: ["trending_long"],
          blockedTags: ["ranging_long", "ranging_short", "trending_short"],
          maxStakeMultiplier,
          notes: ["当前窗口只匹配趋势做多。"],
        }),
      },
      guardrails: [
        guardrail("uptrend_long_only", "只走做多路由", "info", "清晰上涨趋势里不逆势做空。"),
      ],
    };
  }

  return {
    ...shared,
    mode: "defensive",
    systemAction: "observe",
    summary: `信号互相打架：${benchmarkLabel}（Benchmark，基准策略）保持观察，${challengerLabel}（Challenger，挑战策略）暂停新开仓，等窗口更干净再放行。`,
    guardrails: [
      guardrail("chop_flat", "混合窗口防守", "warning", `趋势、波动和合约数据不一致时，${challengerLabel} 暂不新开仓。`),
    ],
  };
}

module.exports = {
  buildTradeSupervisorDecision,
};
