# Task 101R: Next Strategy Candidate Search Plan Refresh

## Summary

Refreshed the next strategy candidate search plan after V11.30 telemetry and
early trade-quality evidence changed the situation.

Conclusion:

```text
prepare_next_strategy_search_but_do_not_abandon_v1130_yet
```

V11.30 is no longer inert: it has produced dry-run signals, orders, and trades.
However, early quality is weak and sample size is too small. The correct next
move is to prepare a parallel candidate-search pipeline while continuing
read-only V11.30 observation until the current BCH open trade closes.

This task is a plan only. It does not search, backtest, tune, deploy, or modify
any strategy.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `fcfdedf`
- Starting `git status --short --untracked-files=all`: empty
- Local readiness before planning: passed
- Source evidence:
  - `reports/audits/task96x_v1130_live_final_decision_telemetry_analysis.md`
  - `reports/audits/task96y_v1130_early_trade_quality_open_position_monitor.md`

## Current V11.30 State

Observed from Task 96X / 96Y:

```text
V11.30 signals: yes
V11.30 orders: yes
V11.30 trades: yes
trades_count = 2
orders_count = 3
current open trade = BCH/USDT:USDT long
first closed trade realized_profit = -1.67763633 USDT
first closed trade exit_reason = v1130_rebound_time_exit
```

Fresh probe on `2026-07-09T02:54:41Z`:

```text
open_count = 1
open_trade_id = 2
open_pair = BCH/USDT:USDT
open_rate = 235.41
current trade still open
```

Therefore:

```text
Task 96Z is not ready yet because the current BCH position has not closed.
```

## Why Candidate Search Should Start In Parallel

Candidate search is justified because:

- V11.30 early closed trade is negative after fees;
- current open BCH trade was negative at Task 96Y probe price;
- all observed V11.30 trades are BCH-only so far;
- sample size is too small to tune safely;
- the system needs an alternative path if V11.30 continues to show negative
  expectancy or narrow participation.

Candidate search should remain parallel planning until V11.30 has a few more
execution samples or the current open trade closes.

## Search Objective

Find the next candidate strategy family that can handle fast volatility without
requiring unsafe live tuning.

The search should prioritize:

1. strategies that produce enough signals in volatile 15m / 1h windows;
2. strategies with clean entry/exit explainability;
3. strategies with low dependence on a single pair;
4. strategies that can be evaluated with existing harness reports before any
   server deployment;
5. strategies that keep dry-run first and avoid live-money assumptions.

## Candidate Families

Recommended first-pass families:

| family | reason to inspect | risk |
|---|---|---|
| volatility breakout continuation | captures fast trend continuation after range expansion | can chase tops after exhaustion |
| crash-rebound with stricter exit validation | close to V11.30 but focuses on exit quality | may overfit current BCH sample |
| mean-reversion after liquidation wick | targets overshoot / snapback behavior | can catch falling knives |
| funding / taker-pressure contrarian filter | uses alpha pressure directly instead of blocking only | alpha data quality dependency |
| multi-timeframe pullback continuation | less reactive than pure 15m crash rebound | slower signal frequency |

Do not implement these in this task.

## Required Evidence Before Implementation

Before a new strategy file is created, Task 102 should inventory existing
evidence:

- historical high-volatility replay outputs;
- V11.29 / V11.30 telemetry and trade data;
- existing strategy families in `strategies/**`;
- existing backtest summary reports;
- market-data freshness by pair/timeframe;
- whether current backtest data covers the recent volatile window.

This inventory must be read-only.

## Proposed Batch

### Task 96Z: V11.30 Current BCH Trade Closure Review

Trigger:

```text
trade id 2 is closed
```

Goal:

- read-only inspect realized PnL, exit reason, hold time, fee, funding fee;
- decide whether V11.30 should continue observation or be frozen for tuning
  review;
- no strategy changes.

### Task 102: Strategy Candidate Evidence Inventory

Goal:

- read-only inventory existing strategy/report evidence;
- identify promising candidate families;
- do not run backtests;
- do not modify strategies.

Allowed outputs:

```text
reports/audits/task102_strategy_candidate_evidence_inventory.md
tasks/active/TASK-0102-strategy-candidate-evidence-inventory.md
```

### Task 103: High-Volatility Window Dataset Readiness Plan

Goal:

- verify whether recent volatile windows have complete 15m / 1h / 4h data;
- plan data refresh only if needed;
- do not run backtests.

### Task 104: Candidate Search Harness Design

Goal:

- define a repeatable offline search harness;
- set metrics before implementation;
- include anti-overfit controls;
- require exact path allowlist before code changes.

## Candidate Search Stop Conditions

Stop before implementation if:

- strategy changes are required without an approved exact allowlist;
- backtest data is stale or incomplete;
- the proposed metric is only PnL without trade count / drawdown / fee checks;
- the plan requires reading secrets;
- the plan requires live/server operations;
- the plan requires changing V11.30 while the open BCH trade is unresolved.

## Safety Boundary

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- modify strategies;
- modify bot configs;
- modify dashboard;
- modify deploy files;
- restart bots;
- run backtests;
- write SQLite;
- force-close the current V11.30 trade;
- decide V11.30 replacement readiness.

## Recommended Next Task

Proceed now with:

```text
Task 102: Strategy Candidate Evidence Inventory
```

Keep `Task 96Z` pending until V11.30 trade id `2` closes.
