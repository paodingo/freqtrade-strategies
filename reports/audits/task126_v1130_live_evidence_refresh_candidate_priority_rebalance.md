# Task 126: V11.30 Live Evidence Refresh And Candidate Priority Rebalance

## Summary

Performed a read-only V11.30 live evidence refresh on the server.

Decision:

```text
v1130_live_quality_negative_keep_observing_do_not_promote
```

V11.30 is live-capable and has produced real dry-run trades/orders, but the
current realized sample is negative and too small. It should not be promoted,
and the candidate pipeline should continue with V11.31 longer-window evidence
and the ranging-short research review.

## Server Evidence

| item | value |
|---|---|
| host | `43.134.72.69` |
| user | `ubuntu` |
| hostname | `VM-0-8-ubuntu` |
| server time checked | `2026-07-09T15:43:31+08:00` |
| V11.30 container | `freqtrade-v1130-crash-rebound-shadow` |
| V11.30 state | `Up 18 hours` |
| V11.29 container | `freqtrade-v1129` |
| V11.29 state | `Up 5 days` |

Commands were read-only. This task did not use `docker inspect`, did not read
env files, did not print secrets, and did not start/stop/restart any bot.

## V11.30 SQLite Evidence

Source:

```text
/freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

| metric | value |
|---|---:|
| trades | `2` |
| orders | `4` |
| open trades | `0` |
| closed trades | `2` |
| first open time | `2026-07-08 13:45:17.410371` |
| last open time | `2026-07-09 01:15:40.444377` |
| first close time | `2026-07-08 15:45:47.966000` |
| last close time | `2026-07-09 03:15:52.089000` |

## Trade Quality Snapshot

| trade | pair | side | entry | exit | exit reason | realized PnL |
|---:|---|---|---:|---:|---|---:|
| `1` | `BCH/USDT:USDT` | long | `232.71` | `231.38` | `v1130_rebound_time_exit` | `-1.67763633` |
| `2` | `BCH/USDT:USDT` | long | `235.41` | `232.83` | `v1130_rebound_time_exit` | `-2.98578132` |

Aggregate realized PnL:

```text
-4.66341765 USDT
```

Both trades used:

- `enter_tag = v1130_crash_rebound_long`
- `exit_reason = v1130_rebound_time_exit`
- `fee_open = 0.0005`
- `fee_close = 0.0005`
- `funding_fees = 0.0`

## Log Findings

Recent log tail showed:

- repeated `state='RUNNING'` heartbeats;
- whitelist with 6 pairs;
- no traceback/error lines in the checked tail;
- one important warning:

```text
Strategy analysis took 260.81s, more than 25% of the timeframe (225.00s).
```

This supports the earlier concern that runtime performance can delay orders or
miss signals. It does not prove the strategy is bad, but it is a live-operation
risk.

## Candidate Priority Rebalance

| candidate | previous posture | refreshed posture |
|---|---|---|
| V11.30 crash rebound | live-capable but insufficient | live-capable, `2` closed trades, both negative; do not promote |
| V11.31 loose range | plausible, below replay gate | keep parked; acquire longer replay window |
| ranging short volatility fade | research candidate | move to next deep read-only review |

## Blocking Gaps

- V11.30 has only `2` closed trades, both from `BCH`.
- V11.30 exits are both time-exit losses.
- Runtime warning shows analysis can exceed the safe budget.
- No same-window comparison proves V11.30 is better than baseline.
- V11.31 still lacks enough exact-threshold samples.
- Ranging-short evidence lacks alpha/execution proof.

## Safety Boundary

This task did not:

- read `.env` or `user_data/monitor.env`;
- print API keys, exchange credentials, server keys, or dashboard passwords;
- run `docker inspect`;
- start, stop, or restart containers;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- modify server files;
- modify strategy code;
- modify bot config;
- modify dashboard or deploy files.

## Recommended Next Tasks

Proceed in this order:

```text
Task 127: V11.31 Longer Replay Window Inventory Exact Path Review
Task 128: Ranging Short Candidate Evidence Deep Review
Task 129: V11.30 Runtime Performance Warning Investigation
```

Do not promote V11.30 or V11.31 until sample and runtime quality gates are
cleared.

