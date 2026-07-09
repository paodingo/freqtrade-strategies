# Task 104: Candidate Search Harness Design

## Summary

Designed the offline candidate-search harness for the next strategy search.

Conclusion:

```text
offline_candidate_search_harness_should_be_metric_first_and_data_gated
```

This task is a design only. No harness code was written. No strategy, bot
config, dashboard, deploy, or server state was modified.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `909b85f` |
| starting status | clean |
| readiness before design | passed |
| input tasks | Task 102, Task 103 |

## Harness Objective

Build a repeatable offline search process that can rank candidate strategy
families before any strategy implementation or bot deployment.

The harness must answer:

```text
Which candidate family deserves an exact-scope implementation task?
```

It must not answer:

```text
Can V11.30 replace V10.8.2?
Should current live/dry-run positions be manually closed?
Should production configs be changed now?
```

## Input Data Contract

| input | requirement |
|---|---|
| OHLCV candles | exact timeframe/pair coverage must be recorded before each run |
| V11.30 live evidence | read-only reports and SQLite-derived summaries only |
| V11.29 / V10.8.2 baseline evidence | read-only historical reports only unless a task authorizes fresh extraction |
| fees | include explicit fee bps assumption per run |
| funding | mark `missing` unless available from an approved source |
| alpha/taker-pressure data | mark `missing` or `unknown` if not available for the historical window |

Task 103 found recent `1h` OHLCV stale. Any harness mode requiring `1h` must
wait for a separate refresh task.

## Candidate Families For First Harness Pass

| family | starting evidence | initial scope |
|---|---|---|
| crash-rebound continuation | V11.29 high-vol replay ranked `crash_rebound` best; V11.30 can produce live entries | evaluate 15m + 4h only first |
| crash-rebound exit-quality variant | V11.30 first closed trade lost via time exit | simulate exit rules without changing live strategy |
| ranging-short / volatility fade | 30d feather study has `1214` candidates and positive 8-candle fee-adjusted mean | treat as research family with alpha-state caveat |
| volatility breakout continuation | aligns with recent rapid move windows | require drawdown and late-entry checks |
| alpha/taker-pressure contrarian | current alpha filters mostly block; could become features | require alpha data availability proof |
| multi-timeframe pullback continuation | could reduce pure 15m noise | blocked until recent `1h` OHLCV is refreshed |

## Required Metrics

Each candidate run must output at minimum:

| metric | reason |
|---|---|
| `trade_count` | avoid high-PnL low-sample traps |
| `closed_trade_count` | distinguish open theoretical entries from completed samples |
| `gross_pnl` | baseline before costs |
| `net_pnl_after_fees` | fees are material for short-horizon futures |
| `profit_factor` | separate payoff quality from winrate |
| `winrate` | useful only with payoff and drawdown |
| `max_drawdown` | reject fragile high-volatility candidates |
| `mean_return_bps` / `median_return_bps` | robust return summary |
| `mfe_bps` / `mae_bps` | exit and stop design input |
| `pair_count` | detect single-pair artifacts |
| `pair_concentration` | max pair share or HHI-style concentration |
| `exit_reason_distribution` | identify time-exit or stoploss dependence |
| `hold_time_distribution` | detect stale positions and capital lock |
| `window_coverage` | ensure run covers intended volatile interval |
| `data_gap_status` | prevent stale timeframe contamination |

## Anti-Overfit Controls

The harness should enforce:

- separate `1d`, `7d`, `14d`, and `30d` windows when data is available;
- at least one holdout window not used for threshold selection;
- pair holdout or pair-cluster holdout for the six-pair V11.30 universe;
- parameter-grid caps before running any search;
- minimum trade-count gates before ranking by PnL;
- pair concentration warning when one pair contributes more than half of
  trades or PnL;
- fee sensitivity at multiple fee assumptions;
- no ranking solely by best single horizon;
- no strategy implementation from a single event or one closed trade.

## Proposed Output Contract

Future implementation should produce machine-readable and human-readable output,
for example:

```text
reports/candidate_search/<run_id>/candidate_search_summary.json
reports/candidate_search/<run_id>/candidate_search_summary.md
reports/candidate_search/<run_id>/candidate_matrix.csv
```

Those paths are not authorized by this task. A guard/allowlist task may be
needed before implementation.

## Proposed Future Implementation Surface

Possible future script path:

```text
scripts/build_strategy_candidate_search_harness.js
```

This task does not authorize creating that file. Before implementation, create
an exact-path guard exception task if readiness blocks the new script or output
directory.

## Execution Modes

### Mode 1: 15m + 4h Recent High-Volatility Scan

Ready now, based on Task 103 data:

- use recent `15m` OHLCV through `2026-07-09T02:45:00Z`;
- use `4h` OHLCV through `2026-07-08T20:00:00Z`;
- exclude `1h` features.

### Mode 2: Full 15m / 1h / 4h Multi-Timeframe Scan

Blocked until:

```text
Task 103R refreshes exact 1h futures OHLCV data.
```

### Mode 3: Alpha/Taker Pressure Feature Scan

Blocked until:

- historical alpha/taker-pressure availability is proven;
- missing alpha states are represented as `missing` / `unknown`, not `false`.

## Safety Rules For Implementation

Future harness implementation must:

- be read-only against market data and reports;
- never read `.env` or `user_data/monitor.env`;
- never start, stop, restart, or trade bots;
- never write SQLite;
- never modify strategy or bot config files;
- never run live trading;
- never force-close V11.30 trades;
- clearly label insufficient samples;
- avoid V11.30 replacement conclusions.

## Recommended Task 105

Proceed with:

```text
Task 105: Candidate Search Harness Exact Path Allowlist Review
```

Task 105 should decide whether the following future paths are allowed:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/<run_id>/candidate_search_summary.json
reports/candidate_search/<run_id>/candidate_search_summary.md
reports/candidate_search/<run_id>/candidate_matrix.csv
```

Do not write the harness until Task 105 or an equivalent exact-scope task
approves the implementation surface.

## Safety Boundary

This task did not:

- write harness code;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read secrets;
- start, stop, or restart bots;
- force-close V11.30 trades;
- claim V11.30 is good or bad;
- claim V11.30 can replace V10.8.2.

