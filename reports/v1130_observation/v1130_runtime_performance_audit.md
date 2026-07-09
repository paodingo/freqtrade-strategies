# V11.30 Runtime Performance Audit

## Summary

This report audits V11.30 runtime performance using committed read-only evidence
only. It does not reconnect to the server and does not start, stop, restart, or
modify any bot.

Decision:

```text
active_risk
```

## Sources

- `reports/audits/task126_v1130_live_evidence_refresh_candidate_priority_rebalance.md`
- `reports/audits/task129_v1130_runtime_performance_warning_investigation.md`
- `reports/audits/task132_v1130_instrumented_runtime_performance_audit_plan.md`

## Server Context From Committed Evidence

| item | value |
|---|---|
| host | `43.134.72.69` |
| hostname | `VM-0-8-ubuntu` |
| server time checked | `2026-07-09T15:50:03+08:00` |
| V11.30 container | `freqtrade-v1130-crash-rebound-shadow` |
| V11.30 state | `Up 18 hours` |
| V11.29 container | `freqtrade-v1129` |
| V11.29 state | `Up 5 days` |

## Observed Runtime Signals

| signal | state | value | source |
|---|---|---|---|
| `analysis_overrun` | `observed` | 260.81 | `reports/audits/task129_v1130_runtime_performance_warning_investigation.md` |
| `exchange_timeout` | `observed` | binance dapi exchangeInfo | `reports/audits/task129_v1130_runtime_performance_warning_investigation.md` |
| `running_after_warning` | `observed` |  | `reports/audits/task129_v1130_runtime_performance_warning_investigation.md` |
| `point_in_time_resource_saturation` | `not_observed_in_snapshot` | Point-in-time docker stats do not rule out intermittent spikes during analysis cycles. | `reports/audits/task129_v1130_runtime_performance_warning_investigation.md` |

## Trade Context

| item | value |
|---|---:|
| trades | 2 |
| orders | 4 |
| open trades | 0 |
| closed trades | 2 |
| realized PnL USDT | -4.66341765 |

This trade context does not authorize a strategy quality conclusion.

## Audit Questions

| question | state | reason |
|---|---|---|
| `overrun_frequency` | `unknown` | Committed evidence confirms at least one overrun but does not include full log-window counts. |
| `overrun_trade_correlation` | `unknown` | Committed evidence does not join analysis warnings to exact trade/order timing. |
| `api_timeout_correlation` | `unknown` | One exchangeInfo timeout is observed, but frequency and correlation remain unknown. |
| `v1129_resource_contention` | `unknown` | V11.29 is co-running, but point-in-time CPU/memory is not enough to prove contention. |
| `bottleneck_source` | `unknown` | No per-indicator, data-loading, or exchange-I/O timing breakdown is available. |

## Risk Decision

| item | value |
|---|---|
| blocks promotion | `true` |
| can claim runtime stable | `false` |
| can claim replacement | `false` |
| reason | At least one analysis overrun and one exchange timeout are observed; frequency and impact remain unknown. |

## Required Next Evidence

- `full_log_window_analysis_duration_count`
- `exchange_timeout_count_by_window`
- `docker_stats_repeated_samples`
- `trade_order_timing_join_around_warning_windows`
- `v1129_correlation_or_resource_isolation_check`
- `per_cycle_or_per_pair_bottleneck_measurement`

## What This Cannot Conclude

- Does not prove V11.30 is bad.
- Does not prove V11.30 is good.
- Does not prove runtime is stable.
- Does not authorize promotion or replacement.
- Does not authorize bot restart or configuration changes.

## Recommended Next Task

```text
Task 143: V11.30 Live Telemetry Window Collection Authorization
```
