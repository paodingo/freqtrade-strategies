# TASK-0096S: V11.30 Analyzed Dataframe Read-Only Probe

## Status

Completed.

## Objective

Check whether the existing V11.30 runtime exposes final analyzed dataframe
decision columns through read-only API/log surfaces.

## Result

Completed.

Conclusion:

```text
v1130_analyzed_dataframe_not_observable_from_existing_runtime_surfaces
```

Evidence:

- V11.30 container has no host API port mapping.
- Common in-container API ports did not respond.
- V11.30 logs did not expose per-candle `v1130_crash_rebound_gate` values.
- V11.29 control probe confirmed API probing can detect an exposed API, but
  protected `pair_candles` requires authorization.

## Boundaries

- No secrets read.
- No API credentials used.
- No strategy changes.
- No bot config changes.
- No dashboard/deploy changes.
- No bot start/stop/restart.
- No trading command.
- No backtest.
- No SQLite writes.

## Next

Run:

```text
Task 96T: V11.30 decision telemetry instrumentation plan
```
