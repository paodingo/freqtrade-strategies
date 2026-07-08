# Task 101: Next Strategy Candidate Search Plan

## Summary

Defined the next strategy candidate search plan in case V11.30 remains
unproductive after data freshness is fixed.

This is a plan only. It does not modify strategies, configs, live bots, or
server state.

## Search Trigger

Start next strategy search only if:

- market data freshness is fixed;
- V11.30 is observed on current candles;
- decision trace still shows no actionable entry path or no trades/orders;
- no data/runtime blocker explains the zero-trade state.

## Candidate Families

| family | purpose | required evidence |
|---|---|---|
| high-volatility continuation | trade post-breakout continuation after large candles | 15m/1h replay with cost-aware forward returns |
| crash-rebound refined | keep V11.30 idea but change filters after evidence | decision trace proving which filter blocks valid candidates |
| funding/basis-assisted mean reversion | use futures-specific signals to avoid crowded reversals | funding, mark/index premium, long/short and taker-flow data |
| regime-separated long/short | separate long and short logic by volatility/trend regime | multi-regime replay and anti-concentration checks |
| no-trade sentinel strategy | intentionally detect conditions where trading should stay off | negative-control evidence and alerting |

## Required Harness Before New Strategy

- exact-path guard plan;
- read-only candidate data inventory;
- replay harness with no live config changes;
- anti-overfit scorecard;
- sample sufficiency thresholds;
- explicit no-replacement conclusion until real execution samples exist.

## Recommended Next Tasks

1. `Task 94R: V11.30 market data refresh pipeline diagnosis and safe refresh plan`
2. `Task 102: High-volatility candidate universe inventory`
3. `Task 103: Cost-aware replay schema for next candidates`
4. `Task 104: Next strategy candidate replay harness`

## Safety Boundary

This plan does not authorize:

- strategy code changes;
- bot config changes;
- live/server operations;
- bot restart;
- order placement;
- secret reads.
