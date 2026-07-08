# TASK-0096R: V11.30 Final Decision Path Observability Plan

## Status

Completed.

## Objective

Define how to observe the final V11.30 live strategy decision path without
changing strategy behavior, bot config, dashboard, deploy, or live runtime
state.

## Result

Plan completed.

Task 95R showed fresh data and zero trades/orders. This task identifies the
remaining gap as missing final decision-path evidence:

- `alpha_filter_block_short`
- `alpha_risk_flags`
- `v1130_crash_rebound_gate`
- final analyzed dataframe `enter_long`
- final analyzed dataframe `enter_tag`
- runtime order-blocking causes if `enter_long = 1` exists

## Recommended Next

Run:

```text
Task 96S: V11.30 analyzed dataframe read-only probe
```

## Boundaries

- No strategy changes.
- No bot config changes.
- No dashboard/deploy changes.
- No secret reads.
- No bot start/stop/restart.
- No trading command.
- No backtest.
- No SQLite writes.
- No replacement conclusion.
