# Task 74: V11.30 Signal Telemetry Persistence Design

## Summary

Designed a persistence path for V11.30 gate telemetry. This task is design-only:
it does not modify the strategy, dashboard, database schema, or running server.

Conclusion:

- V11.30 currently records gate state in dataframe column
  `v1130_crash_rebound_gate`.
- That dataframe column is not persisted to SQLite trades/orders because it is
  only analysis-time signal state.
- Without persistence, zero-trade investigation must repeatedly replay gates
  from candle data.
- The safest next implementation is a separate read-only telemetry builder that
  samples analyzed candles or replay output and writes generated reports or a
  monitor-store table, not a strategy-side write path.

## Current Gate Surface

Observed in `strategies/RegimeAwareV1130CrashReboundShadow.py`:

- entry tag:
  - `v1130_crash_rebound_long`
- gate column:
  - `v1130_crash_rebound_gate`
- gate values:
  - `not_candidate`
  - `blocked_missing_columns:<columns>`
  - `blocked_pair_not_allowlisted`
  - `blocked_taker_sell_pressure`
  - `blocked_alpha_short`
  - `enabled_crash_rebound_long`
- exit reasons:
  - `v1130_rebound_take_profit`
  - `v1130_rebound_rsi_exit`
  - `v1130_rebound_time_exit`

Task 68 showed this gate can be replayed from analyzed candle data, but current
dashboard and SQLite do not persist gate counts.

## Existing Persistence Surface

Observed in `dashboard/lib/monitor_store.js`:

- `history_samples`
- `monitor_events`
- `alpha_risk_samples`
- `regime_router_samples`
- `trade_supervisor_decisions`

Useful existing event categories:

- `trade_event`
- `alert`
- `api_latency`
- `data_freshness`

There is no dedicated V11.30 gate telemetry table yet.

## Design Principles

The telemetry path should:

1. be read-only against Freqtrade runtime state;
2. avoid writing from the strategy class;
3. avoid reading secrets;
4. preserve per-pair and per-candle gate states;
5. summarize latest candle gate status;
6. retain aggregate counts over observation windows;
7. not imply that a missing signal is a strategy failure;
8. keep generated telemetry reports out of trading config.

## Recommended Data Model

For a generated JSON report:

```json
{
  "metadata": {
    "strategy": "RegimeAwareV1130CrashReboundShadow",
    "generated_at": "ISO-8601",
    "source": "read_only_gate_replay",
    "timeframe": "15m",
    "pairs": []
  },
  "latest": [
    {
      "pair": "ETH/USDT:USDT",
      "candle_time": "ISO-8601",
      "gate": "not_candidate",
      "enter_long": 0,
      "enter_tag": "",
      "failed_conditions": ["return", "range"],
      "alpha_flags": []
    }
  ],
  "window_summary": {
    "rows": 1440,
    "gate_counts": {},
    "raw_fail_counts": {},
    "enabled_examples": []
  },
  "limits": {
    "can_place_orders": false,
    "modifies_bot": false,
    "reads_secret": false
  }
}
```

If persisted into monitor history later, use a dedicated table such as:

```sql
CREATE TABLE IF NOT EXISTS v1130_gate_samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sampled_at TEXT NOT NULL,
  pair TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  candle_time TEXT,
  gate TEXT NOT NULL,
  enter_long INTEGER,
  enter_short INTEGER,
  enter_tag TEXT,
  failed_conditions_json TEXT,
  alpha_flags_json TEXT,
  source TEXT NOT NULL
);
```

This is a design draft only. It was not applied.

## Recommended Implementation Path

Task 76 should add a read-only builder script with exact outputs:

- `scripts/build_v1130_gate_telemetry_report.js`
- `reports/v1130_observation/v1130_gate_telemetry_report.json`
- `reports/v1130_observation/v1130_gate_telemetry_report.md`
- focused tests for the generated JSON shape

The first implementation should write generated report files only. A later task
can decide whether to also write into `monitor_history.sqlite`.

## Guardrail Needs

Because these paths include `v1130`, a guard exception may be needed before
Task 76.

The exception should be exact-path only:

- no `reports/v1130_observation/**` wildcard unless separately approved;
- no `scripts/build_v1130_*` wildcard;
- no strategy/config/dashboard broad allowance;
- no SQLite snapshot or runtime DB allowance.

## Blocking Gaps This Solves

Telemetry persistence would answer:

- did the latest candle fail because of `return`, `range`, `volume`, or `rsi`;
- did alpha-risk block the signal;
- did taker sell pressure block the signal;
- which pairs were closest to passing;
- whether a zero-trade interval had no candidate or had blocked candidates.

Telemetry persistence still would not answer:

- whether V11.30 is profitable;
- whether V11.30 can replace V10.8.2;
- order fill quality;
- latency;
- fee/funding quality.

## Non-Actions

This task did not:

- modify strategy code;
- modify dashboard code;
- modify monitor-store schema;
- write SQLite;
- read secrets;
- start, stop, or restart bots;
- run backtests.

## Recommended Next Task

Proceed with:

```text
Task 75: V11.30 Safe Market Data Refresh Dry-Run And Exact Command Approval
Task 76R: Allow V11.30 gate telemetry exact paths
Task 76: V11.30 Gate Telemetry Report Builder
```

Recommended order:

1. Task 75 first, because stale local market data should be handled before
   relying on file-based replay.
2. Task 76R/76 next, because live zero-trade diagnosis needs persisted gate
   telemetry.
