"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  classifyCandidateTypes,
  buildReplayScorecard,
} = require("../scripts/build_v1129_high_volatility_replay_harness");

test("classifyCandidateTypes identifies high-volatility candidate families", () => {
  const selloff = {
    open: 100,
    high: 101,
    low: 98,
    close: 99,
    volume: 120,
    volume_mean: 100,
    adx_4h: 35,
    rsi: 42,
    bb_percent: 0.3,
    range_position_24h: 0.2,
  };
  assert.deepEqual(classifyCandidateTypes(selloff), [
    "high_volatility",
    "selloff_continuation",
  ]);

  const blowoff = {
    open: 100,
    high: 103,
    low: 99,
    close: 102,
    volume: 90,
    volume_mean: 100,
    adx_4h: 28,
    rsi: 68,
    bb_percent: 0.91,
    range_position_24h: 0.88,
  };
  assert.deepEqual(classifyCandidateTypes(blowoff), [
    "high_volatility",
    "blowoff_short",
  ]);

  const rebound = {
    open: 100,
    high: 103,
    low: 99,
    close: 101,
    volume: 95,
    volume_mean: 100,
    adx_4h: 44,
    rsi: 51,
    bb_percent: 0.45,
    range_position_24h: 0.45,
  };
  assert.deepEqual(classifyCandidateTypes(rebound), [
    "high_volatility",
    "crash_rebound",
  ]);
});

test("buildReplayScorecard computes direction-aware forward returns", () => {
  const rowsByPair = {
    "BTC/USDT:USDT": [
      {
        date: "2026-07-07T00:00:00Z",
        open: 100,
        high: 101,
        low: 98,
        close: 99,
        volume: 120,
        volume_mean: 100,
        adx_4h: 35,
        rsi: 42,
        bb_percent: 0.3,
        range_position_24h: 0.2,
        enter_long: 0,
        enter_short: 0,
        alpha_filter_block_long: true,
        alpha_filter_block_short: false,
      },
      {
        date: "2026-07-07T00:15:00Z",
        open: 99,
        high: 100,
        low: 96,
        close: 97,
        volume: 40,
        volume_mean: 100,
        adx_4h: 18,
        rsi: 35,
        bb_percent: 0.2,
        range_position_24h: 0.15,
      },
      {
        date: "2026-07-07T00:30:00Z",
        open: 97,
        high: 98,
        low: 94,
        close: 95,
        volume: 40,
        volume_mean: 100,
        adx_4h: 18,
        rsi: 31,
        bb_percent: 0.15,
        range_position_24h: 0.1,
      },
    ],
    "ETH/USDT:USDT": [
      {
        date: "2026-07-07T00:00:00Z",
        open: 100,
        high: 103,
        low: 99,
        close: 101,
        volume: 95,
        volume_mean: 100,
        adx_4h: 44,
        rsi: 51,
        bb_percent: 0.45,
        range_position_24h: 0.45,
        enter_long: 0,
        enter_short: 0,
        alpha_filter_block_long: true,
        alpha_filter_block_short: false,
      },
      {
        date: "2026-07-07T00:15:00Z",
        open: 101,
        high: 104,
        low: 100,
        close: 103,
        volume: 40,
        volume_mean: 100,
        adx_4h: 43,
        rsi: 55,
        bb_percent: 0.52,
        range_position_24h: 0.5,
      },
    ],
  };

  const scorecard = buildReplayScorecard(rowsByPair, { feeBps: 10, horizons: [1, 2] });

  assert.equal(scorecard.metadata.total_rows, 5);
  assert.equal(scorecard.aggregate.candidate_counts.selloff_continuation, 1);
  assert.equal(scorecard.aggregate.candidate_counts.crash_rebound, 1);
  assert.equal(scorecard.aggregate.final_entry_rows, 0);
  assert.equal(
    scorecard.aggregate.by_candidate.selloff_continuation.horizons["1"].fee_adjusted_return.mean_bps,
    192.0202,
  );
  assert.equal(
    scorecard.aggregate.by_candidate.crash_rebound.horizons["1"].fee_adjusted_return.mean_bps,
    188.0198,
  );
  assert.equal(scorecard.verdict.next_required_task, "Task 58: V11.30 Candidate Selection");
});
