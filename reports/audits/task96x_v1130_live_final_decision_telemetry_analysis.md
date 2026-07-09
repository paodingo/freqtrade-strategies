# Task 96X: V11.30 Live Final Decision Telemetry Analysis

## Summary

Analyzed the live V11.30 final decision telemetry and read-only SQLite/log
evidence after Task 96W deployed behavior-neutral telemetry.

Conclusion:

```text
v1130_has_live_dry_run_trades_and_orders
```

The previous "zero trades / zero orders" condition is no longer current.

Observed on `2026-07-09T02:18Z`:

```text
trades_count = 2
orders_count = 3
open_trade = BCH/USDT:USDT long
latest telemetry enabled_rows = 1
```

This task does not claim V11.30 is profitable or ready to replace V10.8.2. It
only confirms that the strategy is now producing final live entry signals and
dry-run orders/trades.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `368b10c`
- Starting `git status --short --untracked-files=all`: empty
- Local readiness before analysis: passed
- Source deploy task:
  `reports/audits/task96w_v1130_final_decision_telemetry_server_deploy.md`

## Server Evidence

| item | observed |
|---|---|
| host | `VM-0-8-ubuntu` |
| probe time UTC | `2026-07-09T02:18:49Z` |
| V11.30 container | `freqtrade-v1130-crash-rebound-shadow Up 13 hours` |
| V11.29 container | `freqtrade-v1129 Up 5 days` |
| V10.8.2 container | not touched by this task |

No bot config, strategy parameters, dashboard code, deploy files, or SQLite
data were modified.

## Live Telemetry Snapshot

Latest live telemetry file:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

Telemetry metadata:

| field | value |
|---|---|
| generated_at | `2026-07-09T02:15:48.929721+00:00` |
| latest_updated_pair | `BCH/USDT:USDT` |
| safety_verdict | `telemetry_only_no_behavior_change` |

Telemetry summary:

| field | value |
|---|---:|
| pairs_observed | `6` |
| rows_observed | `300` |
| candidate_rows | `1` |
| enabled_rows | `1` |
| blocked_rows | `0` |

Pair summary:

| pair | rows | candidates | enabled | blocked |
|---|---:|---:|---:|---:|
| `BCH/USDT:USDT` | `50` | `1` | `1` | `0` |
| `DOGE/USDT:USDT` | `50` | `0` | `0` | `0` |
| `ETH/USDT:USDT` | `50` | `0` | `0` | `0` |
| `LINK/USDT:USDT` | `50` | `0` | `0` | `0` |
| `SOL/USDT:USDT` | `50` | `0` | `0` | `0` |
| `XRP/USDT:USDT` | `50` | `0` | `0` | `0` |

## Decision Path Interpretation

Current live telemetry says:

```text
BCH/USDT:USDT produced a crash-rebound candidate and passed the final V11.30 gate.
```

Observed final state:

```text
v1130_crash_rebound_gate = enabled_crash_rebound_long
enter_long = 1
enter_tag = v1130_crash_rebound_long
```

Therefore the current zero-order cause is not:

- missing market data;
- no strategy loop;
- pair not allowlisted;
- all candidates blocked by taker sell pressure;
- all candidates blocked by alpha short filter;
- final `enter_long` staying at `0`.

Those were plausible before telemetry. They are not the current live state.

## SQLite Evidence

Read-only SQLite query against:

```text
/freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Observed:

```text
trades_count = 2
orders_count = 3
```

Latest trades:

| id | pair | is_open | side | enter_tag | open_date UTC | open_rate | close_date UTC | close_rate | exit_reason |
|---:|---|---:|---|---|---|---:|---|---:|---|
| `2` | `BCH/USDT:USDT` | `1` | long | `v1130_crash_rebound_long` | `2026-07-09 01:15:40.444377` | `235.41` | | | |
| `1` | `BCH/USDT:USDT` | `0` | long | `v1130_crash_rebound_long` | `2026-07-08 13:45:17.410371` | `232.71` | `2026-07-08 15:45:47.966000` | `231.38` | `v1130_rebound_time_exit` |

Latest orders:

| id | pair | side | status | type | filled | average | filled_date UTC |
|---:|---|---|---|---|---:|---:|---|
| `3` | `BCH/USDT:USDT` | buy | closed | limit | `1.061` | `235.41` | `2026-07-09 01:15:40.440000` |
| `2` | `BCH/USDT:USDT` | sell | closed | limit | `1.074` | `231.38` | `2026-07-08 15:45:47.966000` |
| `1` | `BCH/USDT:USDT` | buy | closed | limit | `1.074` | `232.71` | `2026-07-08 13:45:17.409000` |

## Runtime Log Evidence

The V11.30 log shows a live dry-run entry path:

```text
2026-07-09 01:15:40 UTC: Long signal found for BCH/USDT:USDT
2026-07-09 01:15:40 UTC: dry_run buy order created and closed
2026-07-09 01:15:41 UTC: entry and entry_fill RPC messages emitted
```

The log also shows:

```text
2026-07-09 01:38:02 UTC: Temporary Binance dapi exchangeInfo timeout
```

This was followed by heartbeat logs and pairlist refresh, so it is a runtime
stability warning but not evidence that V11.30 stopped.

## What Changed From Task 96W

Task 96W initial post-deploy telemetry showed:

```text
candidate_rows = 1
enabled_rows = 0
blocked_rows = 1
gate = blocked_taker_sell_pressure
```

The later live telemetry now shows:

```text
candidate_rows = 1
enabled_rows = 1
blocked_rows = 0
gate = enabled_crash_rebound_long
```

So the correct current diagnosis is:

```text
V11.30 was not permanently inert. It was previously blocked by final gate logic,
then later emitted BCH long signals and created dry-run orders/trades.
```

## What This Does Not Prove

This task does not prove:

- V11.30 is profitable;
- V11.30 can replace V10.8.2;
- V11.30 has enough sample size;
- BCH-only behavior is diversified enough;
- execution quality is good;
- the open BCH trade will close profitably;
- the temporary exchange timeout is harmless long term.

## Current Risks

Observed risks:

- sample size is still very small: `2` trades and `3` orders;
- all observed V11.30 live trades are `BCH/USDT:USDT`;
- one closed trade exited by `v1130_rebound_time_exit`;
- one trade is still open;
- no same-window performance comparison is valid yet;
- a temporary Binance market reload timeout occurred.

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
- start live trading;
- decide replacement readiness.

## Recommended Next Task

Proceed with:

```text
Task 96Y: V11.30 early trade quality and open-position monitor
```

Task 96Y should track the current BCH open trade and the first closed trade,
including:

- entry price;
- current/close price;
- fee;
- time in trade;
- exit reason;
- realized PnL after fees;
- whether `v1130_rebound_time_exit` is causing bad exits;
- whether the next trades remain BCH-only.

Do not tune strategy behavior until this early execution-quality evidence is
collected.
