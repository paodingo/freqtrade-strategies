# Task 33: V11.29 Alpha Filter And Short-Core Gate Audit

## Summary

This task read only alpha-risk samples and runtime dataframe summaries to determine why V11.29 final entries remain zero.

Conclusion:

- V11.29 runtime data is available and fresh enough for signal evaluation.
- Over the available V11.29 runtime API window, `2026-06-30 23:15Z` to `2026-07-06 06:45Z`, V11.29 had 6132 dataframe rows across 12 pairs.
- V11.29 final entries were zero across that full window:
  - `enter_long_rows=0`
  - `enter_short_rows=0`
- V11.29 still produced non-empty `enter_tag` labels on 1226 rows, mostly `trending_long`.
- The alpha-risk sample DB is current through `2026-07-06T07:09:34.780Z`.
- Recent alpha samples explain why long candidates are broadly blocked:
  - `topTraderAccountLongCrowding=96/96` recent alpha samples;
  - `alpha_filter_block_long` was true for almost every V11.29 dataframe row.
- Recent alpha samples also explain part of short blocking:
  - `takerSellPressure=52/96` recent alpha samples;
  - `alpha_filter_block_short` was true for about one third of V11.29 rows.
- However, alpha-risk is not the only explanation for zero shorts: over the longer V11.29 runtime window, there were no surviving `trending_short` or `v102_trending_short_core` rows.
- V11.18/V11.29 gate-specific blockers were not the primary observed cause:
  - `v1118_block_rows=0`
  - `v1129_gate_nonpass_rows=0`

Most precise current diagnosis:

```text
V11.29 is producing analyzed dataframe rows and intermediate tags, but the observed runtime window has no surviving short-core entry candidates. Long-like tags are intentionally blocked by the short-core architecture and alpha long-risk flags. Short-side final entries are absent because no observable trending-short short-core candidate survives to V10.2/V11 retag layers; alpha short-risk flags also block part of the window.
```

This task did not modify strategies, bot configs, dashboard, deploy scripts, secrets, SQLite files, or server runtime state.

## Scope And Safety

Read-only server actions performed:

- Read-only SQLite connection to:

```text
/freqtrade/project/user_data/monitor_history.sqlite
```

- Read-only API calls to:

```text
http://localhost:8122/api/v1/pair_candles
http://localhost:8091/api/v1/pair_candles
```

Forbidden actions not performed:

- no `.env` read;
- no `user_data/monitor.env` read;
- no secret material printed;
- no `docker inspect`;
- no bot start/stop/restart;
- no `freqtrade trade`;
- no backtest;
- no SQLite write;
- no strategy/config/dashboard/deploy modification.

## Alpha Risk DB Evidence

SQLite path:

```text
/freqtrade/project/user_data/monitor_history.sqlite
```

Tables discovered:

```text
alpha_risk_samples
history_samples
monitor_events
regime_router_samples
trade_supervisor_decisions
```

`alpha_risk_samples` schema:

```text
id
sampled_at
generated_at
symbol
period
status
risk_level
risk_score
risk_summary
payload
```

Alpha sample range:

| Metric | Value |
| --- | --- |
| count | 25053 |
| min sampled_at | `2026-06-06T07:15:00.000Z` |
| max sampled_at | `2026-07-06T07:09:34.780Z` |

Recent 96 sample summary:

| Field | Value |
| --- | --- |
| risk levels | `neutral=80`, `good=16` |
| risk score min/max | `10.0` / `34.0` |
| `topTraderAccountLongCrowding` | 96 |
| `takerSellPressure` | 52 |
| `takerBuyPressure` | 28 |

Latest sanitized examples:

```text
2026-07-06T07:09:34.780Z neutral score=34 flags=topTraderAccountLongCrowding,takerSellPressure
2026-07-06T07:08:34.810Z neutral score=34 flags=topTraderAccountLongCrowding,takerSellPressure
2026-07-06T07:07:34.742Z neutral score=34 flags=topTraderAccountLongCrowding,takerSellPressure
2026-07-06T07:06:34.748Z neutral score=34 flags=topTraderAccountLongCrowding,takerSellPressure
2026-07-06T07:05:34.761Z neutral score=34 flags=topTraderAccountLongCrowding,takerSellPressure
```

Interpretation:

- Alpha data is not stale; it is being updated.
- The risk level is not `danger`, but the directional flags still block entries under `alpha_filter_mode=directional`.
- `topTraderAccountLongCrowding` is in `LONG_HOSTILE_FLAGS`, so it can block long entries even with `neutral` risk level.
- `takerSellPressure` is in `SHORT_HOSTILE_FLAGS`, so it can block short entries for matching rows.

## Code Semantics Used

From `alpha_risk_filter.py`:

```text
LONG_HOSTILE_FLAGS includes topTraderAccountLongCrowding and takerBuyPressure
SHORT_HOSTILE_FLAGS includes takerSellPressure
```

Directional mode:

```text
alpha_filter_block_long = danger OR any LONG_HOSTILE_FLAGS
alpha_filter_block_short = danger OR any SHORT_HOSTILE_FLAGS
```

Then:

```text
enter_long = 0 when enter_long == 1 and alpha_filter_block_long
enter_short = 0 when enter_short == 1 and alpha_filter_block_short
```

The filter does not clear `enter_tag`.

## V11.29 Runtime Window

Read-only API window:

```text
timeframe=15m
limit=672
observed_at_utc=2026-07-06T07:10:16Z
available data window=2026-06-30 23:15Z to 2026-07-06 06:45Z
```

Aggregate V11.29 totals:

| Metric | Value |
| --- | ---: |
| rows | 6132 |
| enter_long_rows | 0 |
| enter_short_rows | 0 |
| nonempty_enter_tag_rows | 1226 |
| alpha_filter_block_long rows | 6108 |
| alpha_filter_block_short rows | 2040 |
| short_core_tag_rows | 0 |
| trending_short_tag_rows | 0 |
| v1129_gate_nonpass_rows | 0 |
| v1118_block_rows | 0 |

V11.29 tag totals:

| Tag | Rows |
| --- | ---: |
| `trending_long` | 1098 |
| `v66_ranging_short_edge` | 111 |
| `v66_ranging_long_edge` | 17 |

Per-pair V11.29 summary:

| Pair | Rows | enter_long | enter_short | tags | alpha long block | alpha short block | short core | trending short |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 511 | 0 | 0 | 103 | 509 | 170 | 0 | 0 |
| ETH/USDT:USDT | 511 | 0 | 0 | 148 | 509 | 170 | 0 | 0 |
| SOL/USDT:USDT | 511 | 0 | 0 | 88 | 509 | 170 | 0 | 0 |
| BNB/USDT:USDT | 511 | 0 | 0 | 102 | 509 | 170 | 0 | 0 |
| XRP/USDT:USDT | 511 | 0 | 0 | 102 | 509 | 170 | 0 | 0 |
| DOGE/USDT:USDT | 511 | 0 | 0 | 74 | 509 | 170 | 0 | 0 |
| ADA/USDT:USDT | 511 | 0 | 0 | 118 | 509 | 170 | 0 | 0 |
| LINK/USDT:USDT | 511 | 0 | 0 | 134 | 509 | 170 | 0 | 0 |
| AVAX/USDT:USDT | 511 | 0 | 0 | 53 | 509 | 170 | 0 | 0 |
| LTC/USDT:USDT | 511 | 0 | 0 | 74 | 509 | 170 | 0 | 0 |
| TRX/USDT:USDT | 511 | 0 | 0 | 77 | 509 | 170 | 0 | 0 |
| BCH/USDT:USDT | 511 | 0 | 0 | 153 | 509 | 170 | 0 | 0 |

Interpretation:

- V11.29 has broad long-like tagging, but long entries are not part of the short-core architecture and are also blocked by alpha long-risk flags.
- V11.29 has no observed surviving `trending_short` / `v102_trending_short_core` candidate in this runtime window.
- Later V11 retag gates did not appear to be the blocker because they only operate after short entries exist, and `v1129_gate_nonpass_rows=0`.

## V10.8.2 Runtime Window

Read-only API window:

```text
timeframe=15m
limit=672
observed_at_utc=2026-07-06T07:10:16Z
available data window=2026-06-29 07:00Z to 2026-07-06 06:45Z for the visible V10.8.2 pairs
```

Aggregate V10.8.2 totals:

| Metric | Value |
| --- | ---: |
| rows | 4032 |
| enter_long_rows | 0 |
| enter_short_rows | 0 |
| nonempty_enter_tag_rows | 520 |
| alpha_filter_block_long rows | 4020 |
| alpha_filter_block_short rows | 1356 |
| short_core_tag_rows | 0 |
| trending_short_tag_rows | 3 |

V10.8.2 visible tag totals:

| Tag | Rows |
| --- | ---: |
| `trending_long` | 275 |
| `v66_ranging_short_edge` | 236 |
| `v66_ranging_long_edge` | 6 |
| `trending_short` | 3 |

Interpretation:

- V10.8.2 also has zero final entries in the observed runtime window.
- V10.8.2 has historical closed trades/orders in SQLite, but current runtime dataframe does not show current final entry candidates.
- The current no-entry state therefore affects the short-core family generally in this observation window, not only V11.29.

## Root Cause Assessment

Evidence-supported causes:

1. Long-side labels do not become orders by design.
   - V10.2 short-core blocks long entries.
   - Alpha flags also currently block long entries broadly.

2. Ranging tags do not become V11.29 short-core orders.
   - V10.2 blocks ranging entries and non-core shorts.
   - `v66_ranging_short_edge` tags remain as labels, not surviving final entries.

3. Short-core candidates are absent in the observed V11.29 runtime window.
   - `trending_short_tag_rows=0`
   - `short_core_tag_rows=0`
   - `enter_short_rows=0`

4. Alpha short-risk blocks part of the window.
   - `takerSellPressure` appears in 52 of recent 96 alpha samples.
   - V11.29 `alpha_filter_block_short` appears in 2040 of 6132 rows.
   - This is a partial short-side blocker, not the sole explanation for zero shorts.

5. V11.29-specific late gates are not the observed primary blocker.
   - V11.29 retag/stake gates require existing `enter_short == 1`.
   - `v1129_gate_nonpass_rows=0`.
   - `v1118_block_rows=0`.

## What Is Ruled Out Or Lowered

Lowered likelihood:

- stale local feather data as the direct runtime cause;
- V11.29 late retag layer as the sole blocker;
- stake sizing as the immediate cause in the observed window;
- trade supervisor as the immediate V11.29 blocker, since V11.29 dataframe did not expose supervisor columns in the checked runtime dataframe.

Not ruled out:

- short-core conditions may be too restrictive for recent market conditions;
- alpha filter may be too aggressive or too broad for live dry-run observation;
- V11.29 may still be less active than V10.8.2 over historical windows;
- historical V10.8.2 trades may have occurred in conditions not present in the current runtime dataframe.

## Answer To Current Investigation Question

The current best answer is:

```text
V11.29 is not failing because it lacks live candle data. It is not reaching final entries because the inherited short-core stack has no surviving short-core candidates in the observed runtime window, while long/ranging/intermediate tags are either intentionally blocked by short-core design or directionally blocked by alpha-risk flags.
```

## Recommended Task 34

Recommended next task:

```text
Task 34: V11.29 Pre-Filter Signal Reconstruction Plan
```

Scope:

- Define a safe, read-only way to reconstruct pre-filter signals for V11.29:
  - base trend/range raw signals;
  - alpha-filter effects;
  - V10.2 short-core pruning;
  - V11 gate effects.
- Prefer report-only instrumentation or offline dataframe replay from API-returned analyzed columns.
- Do not change live strategy behavior.
- Do not change bot config.
- Do not restart bots.
- Do not run live trading commands.

The purpose of Task 34 is to decide whether the next actual fix should be:

- alpha filter calibration;
- short-core condition calibration;
- pair universe adjustment;
- or simply longer observation.

No such fix should be applied until pre-filter signal reconstruction identifies the exact layer that suppresses entries.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.
