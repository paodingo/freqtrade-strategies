# Task 96S: V11.30 Analyzed Dataframe Read-Only Probe

## Summary

Probed whether the current V11.30 runtime exposes analyzed dataframe decision
columns through existing read-only surfaces.

Conclusion:

```text
v1130_analyzed_dataframe_not_observable_from_existing_runtime_surfaces
```

The probe did not find a usable V11.30 `pair_candles` / analyzed dataframe API
surface. Existing logs also do not expose per-candle V11.30 gate reasons.

Therefore Task 95R's classification remains:

```text
insufficient
```

This task did not modify strategy code, bot config, dashboard, deploy, server
runtime state, or SQLite.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `9d6a092`
- Starting `git status --short --untracked-files=all`: empty
- Local readiness before probing: passed

## Server Runtime Evidence

Server check time:

```text
2026-07-08T12:29:57Z
```

Container state:

```text
freqtrade-v1130-crash-rebound-shadow: Up 10 hours
freqtrade-v1129: Up 4 days, 127.0.0.1:8122->8122/tcp
```

Interpretation:

- V11.29 exposes a host API port.
- V11.30 does not expose a host API port.

## API Port Probe

V11.30 host port mapping:

```text
docker port freqtrade-v1130-crash-rebound-shadow: no mapped ports
```

V11.30 common in-container API ports checked:

```text
8080: no API response
8081: no API response
8122: no API response
8123: no API response
```

V11.30 `/proc/net/tcp` showed established outbound connections but no clear
`LISTEN` socket for a local REST API.

V11.29 control probe:

```text
/api/v1/ping on 127.0.0.1:8122: reachable
/api/v1/pair_candles on 127.0.0.1:8122: 401 Unauthorized without credentials
```

This confirms the probe method can detect an exposed Freqtrade API when one is
available, while also confirming that protected endpoints must not be queried
with credentials unless separately authorized.

## Log Probe

Read-only V11.30 log tail was searched for:

- `api`
- `rpc`
- `listen`
- `rest`
- `jwt`
- `freqUI`
- `v1130_crash_rebound_gate`
- `enabled_crash_rebound_long`
- `blocked_taker_sell_pressure`
- `blocked_alpha_short`
- `blocked_missing_columns`

Observed:

```text
recent logs contain heartbeat lines only for this decision-path purpose
```

No per-candle V11.30 gate evidence was found in the log tail.

## Target Columns

Task 96S attempted to locate a read-only source for these fields:

| field | observed from existing runtime API/logs? |
|---|---|
| `date` | no V11.30 analyzed API available |
| `open` / `high` / `low` / `close` / `volume` | available from feather only, not final analyzed dataframe |
| `volume_mean` | not observed from V11.30 runtime API |
| `rsi` | derived in reports, not observed from V11.30 runtime API |
| `alpha_filter_block_short` | not observed |
| `alpha_risk_flags` | not observed |
| `v1130_crash_rebound_gate` | not observed |
| `enter_long` | not observed from final analyzed dataframe |
| `enter_tag` | not observed from final analyzed dataframe |

## What Can Still Be Said

From Task 95R:

- fresh OHLCV data exists;
- latest observed candle was `2026-07-08T11:30:00Z`;
- latest candle had watch-only opportunities for `SOL` and `LINK`;
- latest candle had no strict live candidate in the OHLCV reconstruction;
- 240-candle window had `10` strict candidates and `29` watch candidates;
- SQLite still showed `0` trades and `0` orders;
- log tail showed heartbeat and no recent errors.

From Task 96S:

- current V11.30 runtime does not expose enough read-only API/log evidence to
  prove final strategy decision reasons;
- zero orders cannot yet be attributed to a specific final cause such as alpha
  block, taker pressure, protection, wallet, pairlock, or strict gate failure.

## What Must Not Be Inferred

Do not infer:

- V11.30 strategy failure;
- V11.30 replacement readiness;
- wallet/protection block;
- alpha/taker block;
- final `enter_long = 0` for every live candle;
- final `enter_long = 1` that failed order creation.

Those require direct final decision-path evidence.

## Safety Boundary

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print API credentials;
- use dashboard/API credentials;
- run full `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- modify strategies;
- modify bot configs;
- modify dashboard;
- modify deploy files;
- install services or timers.

## Recommended Next Task

Proceed with:

```text
Task 96T: V11.30 decision telemetry instrumentation plan
```

Task 96T should design the smallest behavior-neutral instrumentation needed to
record final decision fields.

Required instrumentation constraints:

- no threshold changes;
- no pairlist changes;
- no stake/risk changes;
- no exit logic changes;
- no order behavior changes;
- no secret reads;
- no bot restart until a separate install/rollout task is explicitly approved.

Candidate output fields:

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

Recommended follow-up after Task 96T:

```text
Task 96U: Implement V11.30 behavior-neutral decision telemetry
```

Only after an explicitly approved implementation and deployment should we
rerun the V11.30 decision trace and classify the zero-trade cause.
