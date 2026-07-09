# Task 96Y: V11.30 Early Trade Quality and Open-Position Monitor

## Summary

Performed a read-only early trade-quality and open-position monitor for V11.30
after Task 96X confirmed live dry-run trades/orders.

Conclusion:

```text
v1130_early_trade_quality_insufficient_and_currently_negative
```

V11.30 is now trading, but the first observed sample is not good enough to
approve strategy confidence:

- sample size remains tiny: `2` trades and `3` orders;
- all observed trades are `BCH/USDT:USDT`;
- the first closed trade lost money after fees;
- the current open BCH long was also negative at the probe price;
- one temporary Binance market reload timeout was observed, while the bot
  remained `RUNNING`.

This task does not tune strategy behavior and does not conclude whether V11.30
can replace V10.8.2.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `7da05b0`
- Starting `git status --short --untracked-files=all`: empty
- Local readiness before monitoring: passed
- Source task:
  `reports/audits/task96x_v1130_live_final_decision_telemetry_analysis.md`

## Server Evidence

| item | observed |
|---|---|
| host | `43.134.72.69` |
| user | `ubuntu` |
| probe time UTC | `2026-07-09T02:36:56Z` |
| V11.30 container | `freqtrade-v1130-crash-rebound-shadow Up 13 hours` |
| V11.29 container | `freqtrade-v1129 Up 5 days` |

This task used read-only SQLite queries, public BCHUSDT ticker lookup, and log
inspection only.

## Trade Counts

Read-only SQLite snapshot:

```text
trades_count = 2
orders_count = 3
```

## Closed Trade Quality

Closed trade:

| field | value |
|---|---|
| trade id | `1` |
| pair | `BCH/USDT:USDT` |
| side | long |
| enter_tag | `v1130_crash_rebound_long` |
| open_date UTC | `2026-07-08 13:45:17.410371` |
| close_date UTC | `2026-07-08 15:45:47.966000` |
| open_rate | `232.71` |
| close_rate | `231.38` |
| amount | `1.074` |
| stake_amount | `249.93054` |
| fee_open_cost | `0.12496527 USDT` |
| fee_close_cost | `0.12425106 USDT` |
| funding_fees | `0.0` |
| realized_profit | `-1.67763633 USDT` |
| close_profit | `-0.006709055768192565` |
| exit_reason | `v1130_rebound_time_exit` |

Interpretation:

```text
first closed V11.30 dry-run trade = loss after fees
```

The exit was the time-based exit, not take-profit. This is an early warning
that `v1130_rebound_time_exit` may be closing weak rebounds at a loss, but the
sample size is one closed trade, so it is not enough to tune immediately.

## Open Position Monitor

Open trade:

| field | value |
|---|---|
| trade id | `2` |
| pair | `BCH/USDT:USDT` |
| side | long |
| enter_tag | `v1130_crash_rebound_long` |
| open_date UTC | `2026-07-09 01:15:40.444377` |
| open_rate | `235.41` |
| amount | `1.061` |
| stake_amount | `249.77001` |
| fee_open_cost | `0.124885005 USDT` |
| max_rate | `235.96` |
| min_rate | `232.93` |
| funding_fees | `0.0` |
| probe BCHUSDT price | `232.97` |
| probe time UTC | `2026-07-09T02:36:56Z` |

Approximate mark-to-market at probe price:

| metric | value |
|---|---:|
| gross move per BCH | `-2.44` |
| gross unrealized PnL | `-2.58884 USDT` |
| open fee already recorded | `0.124885005 USDT` |
| estimated close fee at probe price | `0.123624585 USDT` |
| estimated net if closed at probe price | `-2.83734959 USDT` |
| estimated net ratio on stake | `-1.136%` |

Interpretation:

```text
current open V11.30 BCH long was negative at the probe price
```

This is a monitor observation, not an instruction to close the trade.

## Order Evidence

Latest orders:

| id | trade | pair | side | status | order_type | price | average | filled | filled_date UTC |
|---:|---:|---|---|---|---|---:|---:|---:|---|
| `3` | `2` | `BCH/USDT:USDT` | buy | closed | limit | `235.41` | `235.41` | `1.061` | `2026-07-09 01:15:40.440000` |
| `2` | `1` | `BCH/USDT:USDT` | sell | closed | limit | `231.38` | `231.38` | `1.074` | `2026-07-08 15:45:47.966000` |
| `1` | `1` | `BCH/USDT:USDT` | buy | closed | limit | `232.71` | `232.71` | `1.074` | `2026-07-08 13:45:17.409000` |

No unfilled order was observed in the latest order rows.

## Runtime Logs

Observed entry path:

```text
2026-07-09 01:15:40 UTC: Long signal found for BCH/USDT:USDT
2026-07-09 01:15:40 UTC: dry-run buy order created and closed
2026-07-09 01:15:41 UTC: entry and entry_fill RPC messages emitted
```

Observed runtime warning:

```text
2026-07-09 01:38:02 UTC: RequestTimeout while reloading Binance dapi exchangeInfo
```

The bot continued to emit heartbeats after the timeout, so the warning is a
stability risk, not proof of a stopped bot.

## Current Diagnosis

V11.30 is no longer blocked at the "does it trade at all?" stage.

Current state:

```text
signals: yes
orders: yes
trades: yes
early trade quality: weak / insufficient
replacement readiness: not established
```

The next concern is not signal absence. The next concern is whether this
crash-rebound idea has positive expectancy after fees and time exits.

## What This Does Not Prove

This task does not prove:

- V11.30 is bad enough to abandon;
- V11.30 is good enough to keep;
- V11.30 can replace V10.8.2;
- `v1130_rebound_time_exit` is definitely wrong;
- BCH-only behavior will continue;
- the open trade will close at the probe price.

The sample is still too small.

## Safety Boundary

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print credentials;
- modify strategy code;
- modify bot config;
- modify dashboard;
- modify deploy files;
- restart bots;
- run backtests;
- write SQLite;
- force close trades;
- change stoploss, ROI, time exit, stake, pairlist, or thresholds;
- decide replacement readiness.

## Recommended Next Tasks

Proceed with:

```text
Task 96Z: V11.30 early trade follow-up after current BCH position closes
```

Task 96Z should wait for the open BCH trade to close, then evaluate:

- realized PnL after fees;
- exit reason;
- hold time;
- whether time exits are consistently negative;
- whether any non-BCH pair participates;
- whether the temporary Binance timeout repeats.

Parallel planning task:

```text
Task 101: Next strategy candidate search plan
```

Do not tune V11.30 until at least the current open trade outcome is known.
