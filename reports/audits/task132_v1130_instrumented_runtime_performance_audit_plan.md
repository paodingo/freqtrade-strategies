# Task 132: V11.30 Instrumented Runtime Performance Audit Plan

## Summary

Defined a safe plan to instrument and audit V11.30 runtime performance after
Task 129 confirmed one strategy-analysis overrun and one Binance market reload
timeout.

Decision:

```text
plan_telemetry_only_runtime_perf_audit_before_promoting_v1130
```

The plan does not modify strategy behavior, bot config, dashboard, deploy files,
or running containers.

## Source Evidence

| source | path |
|---|---|
| Task 126 live evidence refresh | `reports/audits/task126_v1130_live_evidence_refresh_candidate_priority_rebalance.md` |
| Task 129 runtime investigation | `reports/audits/task129_v1130_runtime_performance_warning_investigation.md` |

## Observed Risk

Task 129 confirmed:

- `Strategy analysis took 260.81s`, above the `225s` warning threshold for
  a `15m` timeframe;
- one Binance `exchangeInfo` `RequestTimeout`;
- V11.30 remained `RUNNING` afterward;
- point-in-time CPU/memory snapshot was low, so the issue may be intermittent.

## Audit Questions

The next audit must answer:

1. How often does `Strategy analysis took ...` occur?
2. Are overruns clustered around entry/exit events?
3. Are overruns correlated with API timeouts or market reloads?
4. Does V11.29 co-running create resource contention?
5. Which pairs or candles dominate analysis time?
6. Is the bottleneck indicator computation, data loading, exchange I/O, or
   container resource contention?

## Safe Measurement Sources

Allowed read-only / telemetry-only sources for a future task:

- `docker logs --tail ...` keyword summaries;
- `docker stats --no-stream` repeated samples;
- SQLite read-only trade/order timing queries;
- existing committed reports;
- non-secret file size/mtime for OHLCV data;
- optional telemetry-only script if separately authorized by exact path.

Forbidden:

- `docker restart`, `docker stop`, `docker start`;
- `freqtrade trade`;
- backtests;
- `docker inspect` full output;
- reading `.env` or `user_data/monitor.env`;
- printing secrets;
- modifying strategy/config/dashboard/deploy files.

## Proposed Future Exact Paths

If a local report builder is needed, review exact paths in a separate task:

```text
scripts/build_v1130_runtime_performance_audit.js
reports/v1130_observation/v1130_runtime_performance_audit.json
reports/v1130_observation/v1130_runtime_performance_audit.md
```

Do not allow broad rules such as:

```text
scripts/build_v1130_*
reports/v1130_observation/**
```

## Acceptance Criteria

A useful performance audit should report:

- count and timestamps of analysis overruns;
- max / median / recent analysis duration if available;
- count and timestamps of exchange/API timeouts;
- current and sampled container CPU/memory;
- whether V11.29 is still co-running;
- trade/order timing around overrun windows;
- whether performance risk blocks promotion.

## Recommended Next Task

Proceed with:

```text
Task 135: V11.30 Runtime Performance Audit Exact Path Review
```

Do not promote V11.30 before the runtime performance risk is understood.

