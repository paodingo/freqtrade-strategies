# TASK-0096T: V11.30 Decision Telemetry Instrumentation Plan

## Status

Completed.

## Objective

Define the smallest behavior-neutral instrumentation plan needed to observe the
V11.30 final decision path after Task 96S confirmed that existing runtime
API/log surfaces are insufficient.

## Result

Completed.

Conclusion:

```text
behavior_neutral_decision_telemetry_required
```

Generated:

```text
reports/audits/task96t_v1130_decision_telemetry_instrumentation_plan.md
```

## Scope

Plan only.

No strategy implementation was performed. No bot config, dashboard, deploy,
server runtime, SQLite, or generated telemetry output was changed.

## Required Future Telemetry Fields

- `pair`
- `timeframe`
- `candle_time`
- `candle_return`
- `candle_range`
- `rsi`
- `volume_ratio`
- `candidate`
- `alpha_filter_block_short`
- `alpha_risk_flags`
- `taker_sell_pressure`
- `v1130_crash_rebound_gate`
- `enter_long`
- `enter_tag`

Missing fields must be recorded as `missing` or `unknown`, not `0`.

## Boundaries

- No threshold changes.
- No pairlist changes.
- No stake/risk changes.
- No exit logic changes.
- No order behavior changes.
- No bot config changes.
- No secret reads.
- No server login.
- No bot start/stop/restart.
- No backtest.
- No replacement conclusion.

## Next

Run:

```text
Task 96U: V11.30 behavior-neutral decision telemetry guard review
```

Task 96U should approve exact future paths and guard behavior before any
strategy implementation.
