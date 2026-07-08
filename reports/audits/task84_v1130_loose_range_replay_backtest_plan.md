# Task 84: V11.30 Loose-Range Offline Replay/Backtest Plan

## Summary

Defined a plan to evaluate the V11.30 loose-range watch gate before any live
strategy change. This is plan-only: no backtest was run and no strategy/config
was modified.

Conclusion:

- Task 81 proxy return study is useful but insufficient;
- the next validation needs replay/backtest with costs, funding, slippage, and
  concentration checks;
- no live threshold change should happen until the plan is executed and reviewed.

## Required Inputs

Data:

- corrected futures feather data from Task 80;
- pairs:
  - `ETH/USDT:USDT`
  - `SOL/USDT:USDT`
  - `DOGE/USDT:USDT`
  - `LINK/USDT:USDT`
  - `XRP/USDT:USDT`
  - `BCH/USDT:USDT`
- timeframes:
  - `15m`;
  - `4h`.

Strategy surfaces:

- current V11.30 strict gate;
- proposed watch-only loose gate:
  - `range >= 0.008`;
  - other conditions unchanged.

## Evaluation Stages

1. Offline replay report:
   - strict vs loose watch counts;
   - per-pair concentration;
   - per-day concentration;
   - forward returns at 1/4/8/16 candles;
   - alpha block reasons;
   - taker sell pressure blocks.

2. Cost-aware proxy:
   - subtract assumed round-trip fees;
   - include basic slippage assumptions;
   - report break-even threshold.

3. Freqtrade backtest candidate:
   - only after replay report is acceptable;
   - use a separate experimental strategy/config;
   - never overwrite live V11.30 config;
   - no live bot action.

4. Review gate:
   - compare strict vs loose;
   - decide whether to keep watch-only, reject, or propose a live shadow variant.

## Proposed Output Files For Future Task

Exact outputs should be approved by a guard task first if needed:

- `scripts/build_v1130_loose_range_replay_report.js`
- `reports/v1130_observation/v1130_loose_range_replay_report.json`
- `reports/v1130_observation/v1130_loose_range_replay_report.md`

Optional later outputs:

- `reports/v1130_observation/v1130_loose_range_cost_proxy.json`
- `reports/v1130_observation/v1130_loose_range_cost_proxy.md`

Do not use broad globs such as:

- `reports/v1130_observation/**`;
- `scripts/build_v1130_*`.

## Acceptance Criteria

Before any live strategy change:

- enough samples across more than one pair;
- positive net expectancy after fees/slippage assumptions;
- drawdown and loss tails acceptable;
- no excessive concentration in one event cluster;
- no evidence that relaxed range merely buys falling knives;
- user explicitly approves implementation.

## Forbidden Actions

Do not:

- modify current V11.30 live strategy;
- modify current V11.30 bot config;
- restart bots;
- read secrets;
- run live trading;
- claim replacement readiness.

## Recommended Next Task

Proceed with:

```text
Task 85: Continue live observation until next high-volatility window
Task 86R: Allow exact loose-range replay report paths
Task 86: V11.30 loose-range replay report builder
```
