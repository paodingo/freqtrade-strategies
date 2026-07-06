# Task 32: V11.29 Entry Signal Semantics Audit

## Summary

This task read only server strategy code and runtime dataframe summaries to explain why V11.29 can show non-empty `enter_tag` rows while final `enter_long` / `enter_short` remain `0`.

Conclusion:

- `enter_tag` is not the order trigger. Final entry signals are `enter_long == 1` or `enter_short == 1`.
- V11.29 currently has fresh runtime dataframe data, but in the observed 24h window all 12 whitelist pairs had `enter_long=0` and `enter_short=0`.
- Non-empty `enter_tag` rows are expected under this strategy family because filters can clear `enter_long` / `enter_short` while leaving diagnostic or historical tags in place.
- The most important observed mechanism is the alpha-risk filter: `apply_alpha_filter()` explicitly sets `enter_long` or `enter_short` to `0` when directional risk blocks an entry, but it does not clear `enter_tag`.
- The V10.2 short-core layer also blocks long, ranging, and non-core short entries by clearing final entry columns; it does not require clearing every tag.
- V11.22 / V11.24 / V11.27 / V11.29 mostly retag or resize existing short entries. They do not create new entries from tags by themselves.

Therefore, the zero-trade condition should be framed as:

```text
V11.29 has current runtime data, but final entry signals are zero. Non-empty tags are not sufficient evidence of tradable signals.
```

This task does not prove V11.29 failed, and does not prove V11.29 can or cannot replace V10.8.2.

## Scope And Safety

Read-only server actions performed:

- read V11.29 container strategy source files with `docker exec ... cat`;
- read runtime dataframe summaries through local Freqtrade API `/api/v1/pair_candles`;
- compared V11.29 and V10.8.2 dataframe signal/tag summaries.

Forbidden actions not performed:

- no strategy modification;
- no bot config modification;
- no dashboard/deploy modification;
- no `.env` or `user_data/monitor.env` read;
- no API key, exchange credential, server key, dashboard password, or token printed;
- no `docker inspect`;
- no bot start/stop/restart;
- no `freqtrade trade`;
- no backtest;
- no SQLite write/copy/delete.

## Source Files Read

Read from the running V11.29 container:

```text
/freqtrade/project/strategies/RegimeAwareV1129ResidualDragMicroSizer.py
/freqtrade/project/strategies/RegimeAwareV1127DualTrapMicroSizer.py
/freqtrade/project/strategies/RegimeAwareV1124ReboundChaseSizer.py
/freqtrade/project/strategies/RegimeAwareV1122AdaCapitulationHalfSizer.py
/freqtrade/project/strategies/RegimeAwareV1118VolatilityShockSmallShortPruner.py
/freqtrade/project/strategies/RegimeAwareV1116SelectiveAltRecoverySizer.py
/freqtrade/project/strategies/RegimeAwareV102ReliableShortCoreAlpha.py
/freqtrade/project/strategies/RegimeAwareV66AlphaRisk.py
/freqtrade/project/strategies/alpha_risk_filter.py
/freqtrade/project/strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py
/freqtrade/project/strategies/RegimeAwareV108PairTieredShortCoreAlpha.py
/freqtrade/project/strategies/RegimeAwareV66.py
/freqtrade/project/strategies/regime_aware_base.py
```

The clean worktree only contains older local strategy files through V9. The V11.29 source of truth for this task was the running server container, read-only.

## Entry Semantics

Freqtrade entry semantics in this strategy family:

| Column | Meaning |
| --- | --- |
| `enter_long` | final long entry signal; must be `1` to produce a long entry candidate |
| `enter_short` | final short entry signal; must be `1` to produce a short entry candidate |
| `enter_tag` | label/metadata for a row; not sufficient to trigger an entry |

Important implication:

```text
enter_tag != "" and enter_long == 0 and enter_short == 0 means tagged but not tradable.
```

## Code Path Findings

### Base Strategy

`regime_aware_base.py` initializes:

```text
enter_long = 0
enter_short = 0
```

It then sets `enter_long/enter_tag` or `enter_short/enter_tag` only when base trend/range conditions pass.

### V6.6 Range Layer

`RegimeAwareV66.py` can create range-edge tags:

```text
v66_ranging_long_edge
v66_ranging_short_edge
```

These tags explain the small number of `v66_ranging_*` rows observed in Task 31/32 runtime data.

### Alpha Risk Filter

`RegimeAwareV66AlphaRisk.py` applies:

```text
apply_alpha_filter(...)
```

`alpha_risk_filter.py` then clears final entry columns:

```text
result.loc[(result.get("enter_long", 0) == 1) & result["alpha_filter_block_long"], "enter_long"] = 0
result.loc[(result.get("enter_short", 0) == 1) & result["alpha_filter_block_short"], "enter_short"] = 0
```

It does not clear `enter_tag`.

This is a direct, code-level explanation for non-empty tag rows with final `enter_* = 0`.

### V10.2 Short-Core Layer

`RegimeAwareV102ReliableShortCoreAlpha.py` keeps only the profitable trend-short core:

```text
_block_entries(result, result.get("enter_long", 0) == 1)
_block_entries(result, tag contains "ranging")
_block_entries(result, enter_short == 1 and not core_short)
```

It retags surviving short core entries:

```text
enter_tag = "v102_trending_short_core"
```

This means V11.29 inherits a short-only core after V10.2. Long tags such as `trending_long` can remain visible as labels, but they are intentionally not tradable after the short-core layer.

### V11.18 And Later

Later V11 layers mostly operate on already-existing short entries:

| Layer | Behavior |
| --- | --- |
| V11.18 | can block residual small shorts during volatility shocks |
| V11.22 | retags/sizes ADA capitulation shorts if `enter_short == 1` |
| V11.24 | retags/sizes ADA/LTC/DOGE rebound risk shorts if `enter_short == 1` |
| V11.27 | retags/sizes DOGE/LTC trap shorts if `enter_short == 1` |
| V11.29 | retags/sizes specific residual drag short clusters if `enter_short == 1` |

V11.29 does not convert a non-empty `enter_tag` into an entry. Its retag logic starts from:

```text
short_entry = result.get("enter_short", 0) == 1
```

So if `enter_short` is already `0`, V11.29's retag rules do not create a trade.

## Runtime Evidence

Observed at:

```text
2026-07-06T07:01:53Z to 2026-07-06T07:02:17Z
```

V11.29 24h runtime dataframe:

| Pair | Rows | Data stop | Final long rows | Final short rows | Non-empty tag rows | Alpha long block rows | Alpha short block rows |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 29 | 96 | 28 |
| ETH/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 43 | 96 | 28 |
| SOL/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 1 | 96 | 28 |
| BNB/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 49 | 96 | 28 |
| XRP/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 40 | 96 | 28 |
| DOGE/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 32 | 96 | 28 |
| ADA/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 37 | 96 | 28 |
| LINK/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 35 | 96 | 28 |
| AVAX/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 1 | 96 | 28 |
| LTC/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 45 | 96 | 28 |
| TRX/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 50 | 96 | 28 |
| BCH/USDT:USDT | 96 | 2026-07-06 06:45Z | 0 | 0 | 47 | 96 | 28 |

V11.29 tag distribution examples:

| Pair | Top tags |
| --- | --- |
| BTC | `trending_long=25`, `v66_ranging_short_edge=4` |
| ETH | `trending_long=43` |
| BNB | `trending_long=49` |
| LTC | `trending_long=45` |
| TRX | `trending_long=50` |
| BCH | `trending_long=47` |

Notably:

```text
short_core_tag_rows=0 for all V11.29 pairs
trending_short_tag_rows=0 for all V11.29 pairs
```

So the observed window contains no surviving V10.2 short-core tags and no final short entries.

## V10.8.2 Same-Window Context

V10.8.2 same-window runtime dataframe also had:

```text
enter_long_rows=0
enter_short_rows=0
```

for the observable pairs in the same probe window. Some V10.8.2 pairs also showed non-empty tags, but no final entries.

This matters because the current 24h no-entry state is not unique proof that V11.29 alone is broken. It may reflect current market/alpha-filter conditions across the short-core family.

However, historical SQLite evidence still shows V10.8.2 has prior closed trades and orders while V11.29 snapshot had none. That historical difference remains unresolved by this task.

## Most Likely Explanation

The strongest evidence-backed explanation is:

```text
V11.29 receives runtime data and computes strategy dataframe columns. In the observed 24h window, base/intermediate labels were assigned on many rows, but final tradable entry columns were zeroed or never set to 1 after alpha/short-core/V11 gate processing.
```

More specifically:

- many V11.29 tags are `trending_long`, but V10.2 short-core intentionally blocks long entries;
- `alpha_filter_block_long` was true for all 96 rows per pair in the observed V11.29 window;
- `alpha_filter_block_short` was true for 28 rows per pair;
- no observed rows had surviving `v102_trending_short_core`;
- V11.29 retagging only applies after `enter_short == 1`, so it cannot create an entry from a tag-only row.

## Ruled Out Or Lowered Likelihood

Lower likelihood based on Task 31/32:

- no runtime data at all: runtime `15m` dataframe is available;
- no `4h` context at all: `date_4h` and `*_4h` columns exist inside `15m` dataframe;
- V11.29 creating signals but stake sizing reducing all orders: current observed window has no final entry rows, so stake callback is not yet reached for these rows;
- V11.29 retag layer alone blocking all entries: V11.29 retag layer only operates on existing `enter_short == 1`.

## Still Unknown

- Whether older windows contain surviving `v102_trending_short_core` before filters.
- Whether alpha-risk samples are too aggressive, stale, or misaligned for current runtime.
- Whether the short-core conditions are simply not appearing in current market conditions.
- Whether V11.29's inherited gates make it materially less active than V10.8.2 over longer windows.
- Whether current `alpha_filter_block_long=96/96` and `alpha_filter_block_short=28/96` are intended.
- Whether the historical V10.8.2 trades happened during windows with materially different alpha-risk state.

## Recommended Task 33

Recommended next task:

```text
Task 33: V11.29 Alpha Filter And Short-Core Gate Audit
```

Scope:

- Read-only inspect alpha-risk samples and the directional block flags that feed `alpha_filter_block_long` / `alpha_filter_block_short`.
- Compare V11.29 and V10.8.2 over a longer runtime/API dataframe window if available.
- Determine whether no-entry is mainly due to alpha filter, lack of `trending_short`, V10.2 short-core pruning, or later V11 gates.
- Do not modify strategy.
- Do not modify bot config.
- Do not read secrets.
- Do not restart bots.
- Do not run backtests.

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
