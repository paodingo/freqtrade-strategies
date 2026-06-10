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
    label: bot?.label || "V6.5",
    role: "benchmark",
    allowFreshEntries: true,
    recommendedAction: "keep_running",
    allowedTags: ["ranging_long", "ranging_short", "trending_long", "trending_short"],
    blockedTags: [],
    maxStakeMultiplier: 1,
    notes: ["Benchmark keeps running unless the system is in risk-off mode."],
    ...overrides,
  };
}

function challengerAction(bot, overrides = {}) {
  return {
    botKey: bot?.key || "v66",
    label: bot?.label || "V6.6",
    role: "challenger",
    allowFreshEntries: false,
    recommendedAction: "block_new_entries",
    allowedTags: [],
    blockedTags: ["ranging_long", "ranging_short", "trending_long", "trending_short"],
    maxStakeMultiplier: 0,
    notes: ["Challenger waits for a cleaner regime window."],
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
      summary: "Extreme downside or data stress. No fresh entries; manage existing exposure only.",
      actions: {
        v65: benchmarkAction(v65, {
          allowFreshEntries: false,
          recommendedAction: "manage_existing_only",
          allowedTags: [],
          blockedTags: ["ranging_long", "ranging_short", "trending_long", "trending_short"],
          maxStakeMultiplier: 0,
          notes: ["Risk-off blocks benchmark fresh entries too."],
        }),
        v66: challengerAction(v66, {
          recommendedAction: "manage_existing_only",
          notes: ["Do not add risk during capitulation."],
        }),
      },
      guardrails: [
        guardrail("capitulation_flat", "Risk-off", "danger", "Block all fresh entries until volatility cools."),
      ],
    };
  }

  if (windowType === "downtrend" && allowedPlaybook === "trend_short") {
    return {
      ...shared,
      mode: "attack",
      systemAction: "route",
      maxNewStakePct: riskBudgetPct,
      summary: "Bear trend is actionable. Challenger may only take trend-short entries.",
      actions: {
        v65: benchmarkAction(v65),
        v66: challengerAction(v66, {
          allowFreshEntries: true,
          recommendedAction: "allow_trend_short",
          allowedTags: ["trending_short"],
          blockedTags: ["ranging_long", "ranging_short", "trending_long"],
          maxStakeMultiplier,
          notes: ["Only trend-short entries match this window."],
        }),
      },
      guardrails: [
        guardrail("downtrend_short_only", "Short-only route", "warning", "Block range longs and trend longs in bearish pressure."),
      ],
    };
  }

  if (windowType === "range" && allowedPlaybook === "range_edge") {
    return {
      ...shared,
      mode: "range",
      systemAction: "route",
      maxNewStakePct: riskBudgetPct,
      summary: "Range window is actionable. Challenger may only take range-edge entries.",
      actions: {
        v65: benchmarkAction(v65),
        v66: challengerAction(v66, {
          allowFreshEntries: true,
          recommendedAction: "allow_range_edge",
          allowedTags: ["ranging_long", "ranging_short"],
          blockedTags: ["trending_long", "trending_short"],
          maxStakeMultiplier,
          notes: ["Only edge entries match the current range window."],
        }),
      },
      guardrails: [
        guardrail("range_edges_only", "Range edge only", "info", "Do not chase trend entries inside a low-volatility range."),
      ],
    };
  }

  if (windowType === "uptrend" && allowedPlaybook === "trend_long") {
    return {
      ...shared,
      mode: "attack",
      systemAction: "route",
      maxNewStakePct: riskBudgetPct,
      summary: "Bull trend is actionable. Challenger may only take trend-long entries.",
      actions: {
        v65: benchmarkAction(v65),
        v66: challengerAction(v66, {
          allowFreshEntries: true,
          recommendedAction: "allow_trend_long",
          allowedTags: ["trending_long"],
          blockedTags: ["ranging_long", "ranging_short", "trending_short"],
          maxStakeMultiplier,
          notes: ["Only trend-long entries match this window."],
        }),
      },
      guardrails: [
        guardrail("uptrend_long_only", "Long-only route", "info", "Do not fade a clean bull trend."),
      ],
    };
  }

  return {
    ...shared,
    mode: "defensive",
    systemAction: "observe",
    summary: "Signals are mixed. Keep the benchmark as reference and block challenger fresh entries.",
    guardrails: [
      guardrail("chop_flat", "Mixed-window defense", "warning", "No fresh challenger entries while regime signals disagree."),
    ],
  };
}

module.exports = {
  buildTradeSupervisorDecision,
};
