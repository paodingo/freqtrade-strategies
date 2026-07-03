# Task 24F: V11.29 4h Informative Futures Mapping Fix

## Summary

本任务实现 Task 24A 推荐的最小策略代码修复：

- 为 V11.29 继承链注册 4h futures informative pairs；
- 让 `_load_4h()` 显式使用 `candle_type="futures"` 查询 DataProvider；
- 保留现有 local futures feather fallback；
- 不修改 entry / exit / stake / leverage / ROI / stoploss / protection 逻辑。

实际修改文件：

- `strategies/regime_aware_base.py`
- `reports/audits/task24f_v1129_4h_informative_futures_mapping_fix.md`
- `tasks/active/TASK-0024F-v1129-4h-informative-futures-mapping-fix.md`

## Code Changes

Added import:

```python
from freqtrade.enums import CandleType
```

Added informative pair registration:

```python
def informative_pairs(self):
    if not self.dp:
        return []
    return [(pair, "4h", CandleType.FUTURES) for pair in self.dp.current_whitelist()]
```

Changed DataProvider lookup:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"], timeframe="4h", candle_type="futures"
)
```

## Rationale

Task 24A observed:

- `DataProvider.get_pair_dataframe()` supports `candle_type`.
- `PairWithTimeframe = tuple[str, str, CandleType]`.
- `IStrategy.informative_pairs()` defaults to `[]`.
- Current V11.29 strategy did not register 4h futures informative pairs.
- Current `_load_4h()` queried `(pair, 4h, empty candle type)`.

Therefore the remaining `No data found for (..., 4h, )` warning should be fixed at both points:

1. preload `(pair, "4h", CandleType.FUTURES)`;
2. query the same futures candle type explicitly.

## Behavioral Boundary

This task did not modify:

- entry conditions;
- exit conditions;
- stoploss;
- ROI;
- stake sizing;
- leverage;
- max open trades;
- protections;
- pair whitelist;
- bot config;
- server files;
- dashboard;
- deploy scripts.

This task does not claim:

- V11.29 has passed execution validation;
- V11.29 can replace V10.8.2;
- zero trades/orders has been resolved.

## Verification

Local syntax verification:

```powershell
& 'C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile strategies/regime_aware_base.py
```

Result:

```text
pass
```

Readiness note:

`strategies/**` is intentionally blocked while uncommitted. This task modified strategy code only because the user explicitly authorized the implementation step. After commit, clean worktree readiness should pass.

## Expected Server Effect After Separate Deploy

Expected after Task 24V deploy:

- `freqtrade-v1129` should register 4h futures informative pairs.
- Fresh analysis cycle should no longer log `No data found for (..., 4h, )` if exchange/cache data is available.
- If DataProvider still returns empty, the warning should show `futures` as the candle type, making the failure more accurate.
- Local futures feather fallback remains available.

## Required Next Task

Recommended next task:

```text
Task 24V: Deploy V11.29 4h Informative Futures Mapping Fix
```

Task 24V should:

- backup server `regime_aware_base.py`;
- copy only this file into `freqtrade-v1129`;
- restart only `freqtrade-v1129` if necessary;
- keep `freqtrade-v1082` untouched;
- observe fresh logs for 4h warnings, analysis warnings, and `RUNNING` state;
- not infer replacement readiness.

