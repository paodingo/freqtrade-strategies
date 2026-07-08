# Task 87: V11.30 Watch-Only Telemetry Lane Decision

## Summary

Reviewed the loose-range watch gate evidence and decided whether to implement a
watch-only telemetry lane.

Decision:

```text
Proceed with watch-only telemetry lane design and implementation planning.
Do not modify live entry thresholds yet.
```

## Evidence Reviewed

Task 83:

- proposed `v1130_loose_range_watch`;
- explicitly watch-only;
- does not set `enter_long`;
- strict live gate remains unchanged.

Task 86:

- candidates: `29`;
- enabled: `23`;
- enabled spread across all six pairs;
- enabled spread across three days;
- 4-candle and 8-candle proxy returns positive;
- 16-candle proxy weakens.

Task 85:

- V11.30 still running;
- V11.30 still has `trades = 0` and `orders = 0`;
- latest candles still did not justify live action.

## Decision Rationale

Proceed with watch-only telemetry because:

- it improves observability without changing trading behavior;
- it can explain how often strict V11.30 narrowly misses;
- it can collect evidence for future strategy research;
- it does not place orders or alter risk.

Do not modify live entry thresholds because:

- no cost-aware replay/backtest has been run;
- no fill/slippage/funding/fee modeling has been done;
- V11.30 has no real execution samples yet;
- sample size remains small;
- current strict V11.30 is still under observation.

## Recommended Implementation Boundary

Future Task 88 should:

- add a generated watch-only telemetry report or dashboard-visible generated
  artifact;
- never set `enter_long`;
- never alter live `enter_tag`;
- never modify V11.30 bot config;
- avoid dashboard changes unless separately authorized;
- preserve exact-path guard allowances.

## Recommended Next Tasks

```text
Task 88R: Allow exact V11.30 watch-only telemetry implementation paths
Task 88: Implement V11.30 watch-only telemetry report
Task 89: Continue live observation and compare strict vs watch-only opportunities
```

## Non-Actions

This task did not:

- modify strategy code;
- modify bot configs;
- start, stop, or restart bots;
- read secrets;
- run backtests;
- write SQLite;
- claim V11.30 replacement readiness.
