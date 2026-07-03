# Task 24: V11.29 4h Candle Type Mapping Fix Plan

## Summary

本任务只生成 V11.29 4h candle type mapping / fallback cleanup 修复计划；没有修改策略、bot 配置、dashboard、deploy、server 文件，也没有重启 bot。

当前问题：

```text
No data found for (BTC/USDT:USDT, 4h, ).
No data found for (ETH/USDT:USDT, 4h, ).
...
No data found for (BCH/USDT:USDT, 4h, ).
```

Task 21A / Task 23 已确认：

- V11.29 is running after Task 22X.
- Task 22F bounded 4h lookback reduced the immediate performance risk.
- The 4h DataProvider warning remains.
- V11.29 SQLite still has `trades=0`, `orders=0`.
- The warning alone does not prove 4h data is unavailable to the strategy, because local futures feather fallback may still succeed.

## Current Evidence

Current strategy path:

```text
strategies/regime_aware_base.py
```

Current DataProvider lookup:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"], timeframe="4h"
)
```

The call does not explicitly specify futures candle type. The log's third tuple field is empty:

```text
(PAIR/USDT:USDT, 4h, )
```

Current fallback candidates:

```python
data_dir / "binance" / f"{pair_slug}-4h.feather"
data_dir / f"{pair_slug}-4h.feather"
data_dir / "futures" / f"{pair_slug_futures}-4h-futures.feather"
```

Task 21 found the futures `4h` files exist for all 12 whitelist pairs. Therefore the warning is likely caused by an unnecessary or incorrectly typed DataProvider lookup before fallback.

## What This Warning Can And Cannot Prove

Observed:

- DataProvider lookup for `(pair, 4h, empty candle type)` returns no data.
- The strategy then attempts local futures feather fallback.
- Recent checked logs did not show `4h data unavailable, using safe defaults`.

Cannot conclude:

- V11.29 has no 4h data.
- V11.29 zero trades are caused by missing 4h data.
- V11.29 strategy failed.
- V11.29 can or cannot replace V10.8.2.

## Fix Option A: Explicit Futures Candle Type

Goal:

- Make DataProvider lookup explicitly request futures candles if Freqtrade 2026.5.1 supports it.

Candidate implementation shape:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"],
    timeframe="4h",
    candle_type="futures",
)
```

Potential informative pair shape if supported:

```python
return [(pair, "4h", "futures") for pair in whitelist]
```

Pros:

- Keeps DataProvider as first authority.
- Removes mismatch between futures bot config and empty candle type lookup.
- May allow Freqtrade's internal analyzed data cache to work correctly.

Risks:

- Need to confirm exact Freqtrade 2026.5.1 API signature.
- If `get_pair_dataframe()` does not accept `candle_type`, this patch would break runtime.
- If informative tuple form differs by version, it may create resolver errors.

Required pre-check:

```text
docker exec freqtrade-v1129 python -c "import inspect; from freqtrade.data.dataprovider import DataProvider; print(inspect.signature(DataProvider.get_pair_dataframe))"
```

This is safe because it inspects function signature only and does not read secrets.

## Fix Option B: Skip Noisy DataProvider Lookup And Use Verified Futures Feather Fallback

Goal:

- Avoid the known bad `(pair, 4h, empty candle type)` lookup entirely for futures pairs.
- Use the local futures feather fallback as the intended 4h source.

Candidate implementation shape:

```python
def _load_4h(self, metadata):
    return self._load_4h_from_feather(metadata)
```

Or, more conservative:

```python
if ":" in metadata["pair"]:
    return self._load_4h_from_feather(metadata)
```

Pros:

- Removes the warning without depending on Freqtrade DataProvider API support.
- Uses already verified local futures files.
- Keeps trading rules unchanged.

Risks:

- Bypasses DataProvider cache.
- Requires local data files to remain fresh.
- If data refresh fails, fallback can become stale without DataProvider rescue.

Required guardrail:

- Add explicit freshness logging for selected feather path and latest candle.
- If fallback fails, keep existing safe defaults.
- Do not silently convert missing data to zeros without warning.

## Fix Option C: Hybrid Probe With Fallback

Goal:

- First try explicit futures DataProvider if supported.
- Fall back to local futures feather path if unavailable.

Candidate behavior:

1. Inspect support in code with `try/except TypeError`.
2. Call `get_pair_dataframe(..., candle_type="futures")`.
3. If it fails or returns empty, use local futures feather fallback.
4. Log only one concise warning if both fail.

Pros:

- Most robust across environments.
- Preserves DataProvider path when available.
- Avoids noisy empty candle type warning.

Risks:

- Slightly more code than Option B.
- Must avoid broad exception swallowing that hides real errors.

## Recommended Path

Recommended sequence:

```text
Task 24A: V11.29 4h DataProvider API Signature Inspection
```

Read-only:

- Inspect `DataProvider.get_pair_dataframe` signature inside `freqtrade-v1129`.
- Inspect whether informative pair tuples support candle type in current Freqtrade version docs/source inside the installed package.
- Do not modify strategy or config.

Then:

```text
Task 24F: Implement V11.29 4h Candle Type Mapping Fix
```

If signature supports `candle_type`, implement Option C with explicit futures DataProvider first and fallback second.

If signature does not support it, implement Option B and skip the known bad DataProvider lookup for futures pairs.

## Proposed Task 24F Scope

Allowed files:

- `strategies/regime_aware_base.py`
- `reports/audits/task24f_v1129_4h_candle_type_mapping_fix.md`
- `tasks/active/TASK-0024F-v1129-4h-candle-type-mapping-fix.md`

Forbidden:

- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- strategy entry/exit rule changes
- stake, leverage, ROI, stoploss, protection changes
- V10.8.2 changes
- unaudited server operations

## Verification Plan For Implementation

Local syntax:

```powershell
& 'C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile strategies/regime_aware_base.py
```

Server deploy task should be separate and explicitly authorized:

```text
Task 24V: Deploy V11.29 4h Candle Type Mapping Fix
```

Post-deploy observations:

- `freqtrade-v1129` remains `RUNNING`.
- No `No data found for (..., 4h, )` warning in a fresh analysis cycle.
- No `4h data unavailable, using safe defaults`.
- No `Strategy analysis took ...` regression.
- V11.29 `trades/orders` remain observed values; do not infer strategy success/failure.
- `freqtrade-v1082` untouched.

## Stop Conditions

Stop immediately if:

- API signature is unknown and cannot be inspected.
- Proposed patch requires bot config changes.
- Proposed patch requires secret reads.
- Proposed patch would alter entry/exit/stake/risk logic.
- Readiness guard blocks because strategy changes are not explicitly authorized.

## Recommended Next Task

Recommended next task:

```text
Task 24A: V11.29 4h DataProvider API Signature Inspection
```

This should remain read-only and should not deploy or modify files other than its audit report and task record.

