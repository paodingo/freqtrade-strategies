# Task 96R: V11.30 Final Decision Path Observability Plan

## Summary

Created a plan to make V11.30 zero-trade diagnosis observable without changing
trading behavior.

Conclusion:

```text
final_decision_path_observability_gap_confirmed
```

Task 95R proved that fresh data is now available, but V11.30 still has:

- trades: `0`
- orders: `0`
- open trades: `0`

The current blocker is not market data freshness. The blocker is that existing
reports do not observe the final live strategy decision path.

This task is a plan only. It does not modify strategy code, bot config,
dashboard code, server deployment, or running bot state.

## Evidence Reviewed

- `reports/audits/task95r_v1130_fresh_data_telemetry_decision_trace.md`
- `reports/v1130_observation/v1130_decision_trace_report.json`
- `strategies/RegimeAwareV1130CrashReboundShadow.py`
- `user_data/config_multi_futures_v1130_crash_rebound_shadow.json`
- `strategies/RegimeAwareV66AlphaRisk.py` references
- `strategies/alpha_risk_filter.py` references
- dashboard API inventory and runtime verification plan from Tasks 96 and 97

## Current Observed State

Latest fresh-data report:

```text
latest candle: 2026-07-08T11:30:00Z
strict candidates in 240-candle window: 10
watch candidates in 240-candle window: 29
watch-only enabled: 19
latest candle watch-only pairs: SOL, LINK
V11.30 trades: 0
V11.30 orders: 0
V11.30 log-tail errors: 0
```

Current classification:

```text
insufficient
```

Reason:

```text
Existing sources do not expose the final live strategy decision path.
```

## Strategy Decision Fields Available In Code

The V11.30 strategy already computes a strategy-internal gate column:

```text
v1130_crash_rebound_gate
```

Possible values from code include:

- `not_candidate`
- `blocked_missing_columns:<columns>`
- `blocked_pair_not_allowlisted`
- `blocked_taker_sell_pressure`
- `blocked_alpha_short`
- `enabled_crash_rebound_long`

The strategy also depends on alpha fields created by the parent alpha-risk
pipeline:

- `alpha_filter_block_short`
- `alpha_risk_flags`

The current fresh-data report does not observe these final analyzed dataframe
columns for V11.30 live runtime. It reconstructs OHLCV-only gates from feather
files, so alpha/taker/protection/final entry state remains unknown.

## Missing Or Unknown Fields

These fields remain unproven:

| field | current state | why it matters |
|---|---|---|
| `alpha_filter_block_short` | unknown | can block candidates after OHLCV gate |
| `alpha_risk_flags` | unknown | contains `takerSellPressure` and other alpha risk flags |
| `v1130_crash_rebound_gate` | unknown | strategy's own final per-row gate result |
| `enter_long` in analyzed dataframe | unknown | final strategy signal before Freqtrade order checks |
| `enter_tag` in analyzed dataframe | unknown | proves whether V11.30 tag was emitted |
| pairlist inclusion | partially known from config | runtime pairlist still should be observed |
| protections / pairlocks | unknown | can block order creation after signal |
| wallet/stake/max-open-trades block | unknown | can block order creation after signal |
| final order creation attempt | unknown | no orders exist, so rejection reason is not in SQLite |

## Observability Path A: Read Existing Runtime Analyzed DataFrame

Recommended next task:

```text
Task 96S: V11.30 analyzed dataframe read-only probe
```

Goal:

Use Freqtrade's local REST API `pair_candles` endpoint, if available for the
V11.30 bot, to inspect the latest analyzed dataframe columns without modifying
strategy or bot config.

Target fields:

- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `volume_mean`
- `rsi`
- `alpha_filter_block_short`
- `alpha_risk_flags`
- `v1130_crash_rebound_gate`
- `enter_long`
- `enter_tag`

Suggested read-only probe:

```bash
curl -sS "http://127.0.0.1:<v1130-port>/api/v1/pair_candles?pair=SOL/USDT:USDT&timeframe=15m&limit=20"
```

Do not print credentials. If the API requires auth and credentials are not
already available in a safe session, stop and report.

Acceptance:

- If these columns are present, Task 96S can generate a fresh per-pair decision
  report without strategy changes.
- If these columns are absent, Task 96S must report that the existing API route
  is insufficient.

## Observability Path B: Read Existing Logs

Current log-tail evidence shows heartbeat and zero errors, but no per-candle
decision reasons.

Task 96S may inspect recent logs for these strings:

- `v1130_crash_rebound_gate`
- `enabled_crash_rebound_long`
- `blocked_taker_sell_pressure`
- `blocked_alpha_short`
- `blocked_missing_columns`
- pair names for latest watch-only events

If none are present, logs cannot prove final decision reasons.

Do not increase log level or restart the bot in Task 96S.

## Observability Path C: Read Runtime Pairlocks / Open Trade Constraints

If an analyzed dataframe shows `enter_long = 1` with the V11.30 tag but no
orders, then the next read-only checks should inspect runtime order-blocking
surfaces:

- pairlocks / protections;
- max open trades;
- wallet/stake availability;
- exchange/orderbook error logs.

These are only necessary after we prove a live `enter_long = 1` row existed.

Do not infer wallet/protection blocks from zero orders alone.

## Observability Path D: Future Instrumentation If Existing Sources Are Insufficient

If the API/logs cannot expose the final decision path, a separate explicitly
authorized task should add minimal decision telemetry.

Recommended future task:

```text
Task 96T: V11.30 decision telemetry instrumentation plan
```

Design requirements:

- records decision reasons only;
- does not change `enter_long` logic;
- does not change thresholds;
- does not change stake sizing;
- does not change exit logic;
- does not change protections;
- does not read or print secrets;
- writes to a safe generated report/log path, not SQLite trading tables;
- includes tests proving no trading-behavior change.

Candidate telemetry fields:

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

Do not combine instrumentation with live threshold changes.

## Decision Tree

Use this order:

1. Confirm V11.30 API endpoint and port without reading secrets.
2. Query `pair_candles` for the six V11.30 pairs.
3. Check whether analyzed dataframe includes final strategy columns.
4. If columns are present, produce a read-only `Task 96S` decision-path report.
5. If `enter_long = 0` everywhere, classify zero-trade cause by gate values.
6. If `enter_long = 1` exists but orders remain `0`, move to order-blocking
   checks.
7. If columns are absent, draft `Task 96T` instrumentation plan.

## Stop Conditions

Stop and report if:

- `.env` or `user_data/monitor.env` is required;
- dashboard/API password must be printed;
- bot restart is required;
- strategy changes are required before read-only evidence is exhausted;
- only broad server inspection such as full `docker inspect` can proceed;
- any command would start, stop, restart, or trade.

## Not Allowed In The Next Read-Only Probe

Do not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- install new services or timers;
- change thresholds;
- change pairlist;
- change stake or risk settings;
- decide V11.30 replacement readiness.

## Recommended Next Task

Proceed with:

```text
Task 96S: V11.30 analyzed dataframe read-only probe
```

Expected outputs:

- list of API endpoints/ports probed;
- per-pair latest analyzed dataframe columns observed;
- whether `v1130_crash_rebound_gate`, `alpha_filter_block_short`,
  `alpha_risk_flags`, `enter_long`, and `enter_tag` are present;
- whether latest watch-only pairs `SOL` and `LINK` were blocked by strict range,
  alpha/taker pressure, or another final gate;
- whether any `enabled_crash_rebound_long` row exists in the recent window;
- whether Task 96T instrumentation is needed.
