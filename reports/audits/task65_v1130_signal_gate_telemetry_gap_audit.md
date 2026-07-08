# Task 65: V11.30 Signal/Gate Telemetry Gap Audit

## Summary

Audited why current V11.30 `orders=0` cannot yet be explained from available
runtime evidence.

Conclusion:

- `orders=0` and `trades=0` are observed facts from SQLite.
- They do not prove there were no crash-rebound candidates.
- They do not prove V11.30 failed.
- The current V11.30 gate telemetry exists only as an in-memory dataframe
  column and is not persisted to SQLite, logs, or dashboard.

Therefore the next useful task is not immediate strategy loosening. The next
useful task is a read-only latest-candle gate replay / telemetry locator.

## Inputs Reviewed

- `reports/audits/task64_v1130_first_observation_check.md`
- `reports/audits/task63_v1130_runtime_resource_decision_and_shadow_start.md`
- `strategies/RegimeAwareV1130CrashReboundShadow.py`
- `tests/test_regime_aware_v1130_crash_rebound_shadow.py`
- `dashboard/lib/config.js`
- `dashboard/server.js`

## Observed Facts

From Task 64:

- V11.30 container is running.
- V11.30 heartbeat is present.
- V11.30 SQLite DB exists.
- `trades = 0`.
- `orders = 0`.
- `pairlocks = 0`.
- no V11.30 traceback/error was observed in filtered logs.

From V11.30 strategy code:

- V11.30 writes gate state to dataframe column
  `v1130_crash_rebound_gate`;
- enabled entry tag is `v1130_crash_rebound_long`;
- hard gate blockers include:
  - missing raw columns;
  - pair not allowlisted;
  - missing alpha columns;
  - `alpha_filter_block_short`;
  - `takerSellPressure`;
  - raw crash-rebound gate failure.

## Current Telemetry Coverage

| Signal/Gate Evidence | Current Availability | Notes |
|---|---|---|
| container running state | observed | from `docker ps` and heartbeat |
| SQLite trades/orders | observed | `0` rows in both tables |
| entry tag counts | observed but empty | no trades means no persisted `enter_tag` |
| pairlocks | observed | `0` rows |
| startup config/strategy/pairlist | observed | logs confirm six pairs and dry-run |
| `v1130_crash_rebound_gate` state counts | missing | dataframe-only, not persisted |
| per-pair latest candidate count | missing | requires read-only latest candle replay |
| per-pair alpha block reason | missing | alpha columns are not persisted by SQLite when no trade occurs |
| raw candle gate failures | missing | no current report of return/range/rsi/volume gate values |
| protection veto on a candidate | unknown | no orders/trades; pairlocks are zero, but protections may still influence entries |
| unfilled signal vs no signal | unknown | no order rows and no candidate telemetry |

## Why `orders=0` Is Not Enough

`orders=0` can result from several distinct situations:

- no raw crash-rebound candidate occurred;
- raw candidate occurred but alpha short block vetoed it;
- raw candidate occurred but `takerSellPressure` vetoed it;
- pair was outside the V11.30 allowlist;
- required indicator/alpha columns were missing;
- strategy analysis was delayed and missed the candle;
- protection or pairlist behavior prevented entry;
- exchange/API issues prevented normal cycle progression;
- a real signal occurred but was not visible because gate telemetry is not
  persisted.

The current evidence only confirms there are no persisted orders/trades.

## Data/Gate Readiness

What is currently enough:

- The bot can run.
- The strategy can load.
- The target DB schema exists.
- The target pairs are loaded.
- Orders/trades can be counted later.

What is not currently enough:

- explaining absence of orders;
- proving absence of signals;
- ranking gate blockers;
- deciding whether thresholds are too strict;
- deciding whether alpha vetoes are too aggressive.

## Dashboard/Runtime Visibility Gap

V11.30 currently has no `api_server` block and exposes no REST API port. That is
intentional from Task 60/63 to avoid new secret/API surface.

Consequences:

- dashboard cannot call `/api/v1/pair_candles` for V11.30;
- dashboard cannot read V11.30 analyzed dataframe directly;
- SQLite can show runtime DB facts, but not dataframe gate states before a trade
  exists.

Existing dashboard code can load SQLite bots, but current dashboard config only
lists:

- `v1129` API bot;
- `v1129_shadow` SQLite bot pointing to the old ranging-short shadow DB.

It does not yet list V11.30 as the active shadow.

## Recommended Next Investigation

Recommended next task:

```text
Task 67: V11.30 Live Candle Data Freshness Audit
```

Then:

```text
Task 68: V11.30 Live Gate Replay On Latest Candles
```

Reason:

1. First confirm the V11.30 process has fresh 15m/4h market data available for
   the six allowlisted pairs.
2. Then replay the V11.30 gate read-only over the latest candles and produce
   per-pair blocker counts:
   - `not_candidate`;
   - `blocked_alpha_short`;
   - `blocked_taker_sell_pressure`;
   - `blocked_missing_columns`;
   - `enabled_crash_rebound_long`.

Only after that should thresholds be reviewed.

## Non-Actions

This task did not:

- modify V11.30 strategy;
- modify V11.30 config;
- restart containers;
- run a backtest;
- read secrets;
- write SQLite;
- change dashboard code.

## Stop Condition

Do not loosen V11.30 gates until a read-only latest-candle replay proves which
gate is blocking entries.
