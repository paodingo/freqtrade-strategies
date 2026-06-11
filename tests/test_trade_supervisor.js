"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { buildTradeSupervisorDecision } = require("../dashboard/lib/trade_supervisor");

function botFixture(overrides = {}) {
  return {
    key: "v66",
    label: "V6.6 Alpha",
    ok: true,
    state: "running",
    currentOpenTrades: 0,
    openTrades: [],
    balance: { totalBot: 10000, freeStake: 7500, usedStake: 0 },
    ...overrides,
  };
}

test("chop window keeps benchmark running but blocks challenger fresh entries", () => {
  const decision = buildTradeSupervisorDecision({
    regimeRouter: {
      windowType: "chop",
      allowedPlaybook: "flat",
      riskBudgetPct: 25,
      confidence: 52,
      policy: {
        allowTrendLong: false,
        allowTrendShort: false,
        allowRangeLong: false,
        allowRangeShort: false,
        maxStakeMultiplier: 0.25,
      },
    },
    bots: [
      botFixture({ key: "v65", label: "V6.5" }),
      botFixture({ key: "v66", label: "V6.6 Alpha" }),
    ],
  });

  assert.equal(decision.mode, "defensive");
  assert.equal(decision.systemAction, "observe");
  assert.equal(decision.riskBudgetPct, 25);
  assert.equal(decision.maxNewStakePct, 0);
  assert.equal(decision.actions.v65.allowFreshEntries, true);
  assert.equal(decision.actions.v65.role, "benchmark");
  assert.equal(decision.actions.v66.allowFreshEntries, false);
  assert.equal(decision.actions.v66.recommendedAction, "block_new_entries");
  assert.equal(decision.summary, "信号互相打架：V6.5（Benchmark，基准策略）保持观察，V6.6 Alpha（Challenger，挑战策略）暂停新开仓，等窗口更干净再放行。");
  assert.ok(decision.guardrails.some((item) => item.label === "混合窗口防守"));
  assert.ok(decision.guardrails.some((item) => item.note.includes("V6.6 Alpha 暂不新开仓")));
  assert.ok(decision.guardrails.some((item) => item.key === "chop_flat"));
});

test("downtrend window routes challenger only to trend shorts", () => {
  const decision = buildTradeSupervisorDecision({
    regimeRouter: {
      windowType: "downtrend",
      allowedPlaybook: "trend_short",
      riskBudgetPct: 50,
      confidence: 82,
      policy: {
        allowTrendLong: false,
        allowTrendShort: true,
        allowRangeLong: false,
        allowRangeShort: false,
        maxStakeMultiplier: 0.5,
      },
    },
    bots: [
      botFixture({ key: "v65", label: "V6.5" }),
      botFixture({ key: "v66", label: "V6.6 Alpha" }),
    ],
  });

  assert.equal(decision.mode, "attack");
  assert.equal(decision.actions.v66.allowFreshEntries, true);
  assert.deepEqual(decision.actions.v66.allowedTags, ["trending_short"]);
  assert.deepEqual(decision.actions.v66.blockedTags, ["ranging_long", "ranging_short", "trending_long"]);
  assert.equal(decision.actions.v66.maxStakeMultiplier, 0.5);
});

test("capitulation window blocks all fresh entries and recommends reducing risk", () => {
  const decision = buildTradeSupervisorDecision({
    regimeRouter: {
      windowType: "capitulation",
      allowedPlaybook: "flat",
      riskBudgetPct: 5,
      confidence: 90,
      policy: { maxStakeMultiplier: 0 },
    },
    bots: [
      botFixture({ key: "v65", label: "V6.5", currentOpenTrades: 1 }),
      botFixture({ key: "v66", label: "V6.6 Alpha", currentOpenTrades: 1 }),
    ],
  });

  assert.equal(decision.mode, "risk_off");
  assert.equal(decision.systemAction, "reduce_risk");
  assert.equal(decision.maxNewStakePct, 0);
  assert.equal(decision.actions.v65.allowFreshEntries, false);
  assert.equal(decision.actions.v66.allowFreshEntries, false);
  assert.equal(decision.actions.v65.recommendedAction, "manage_existing_only");
  assert.equal(decision.actions.v66.recommendedAction, "manage_existing_only");
});

test("range window allows challenger range-edge tags only", () => {
  const decision = buildTradeSupervisorDecision({
    regimeRouter: {
      windowType: "range",
      allowedPlaybook: "range_edge",
      riskBudgetPct: 60,
      confidence: 74,
      policy: {
        allowRangeLong: true,
        allowRangeShort: true,
        maxStakeMultiplier: 0.6,
      },
    },
    bots: [
      botFixture({ key: "v65", label: "V6.5" }),
      botFixture({ key: "v66", label: "V6.6 Alpha" }),
    ],
  });

  assert.equal(decision.mode, "range");
  assert.equal(decision.actions.v66.allowFreshEntries, true);
  assert.deepEqual(decision.actions.v66.allowedTags, ["ranging_long", "ranging_short"]);
  assert.deepEqual(decision.actions.v66.blockedTags, ["trending_long", "trending_short"]);
  assert.equal(decision.actions.v66.maxStakeMultiplier, 0.6);
});
