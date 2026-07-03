# Task 24A: V11.29 DataProvider API Signature Inspection

## Summary

本任务只读检查了 `freqtrade-v1129` 容器内 Freqtrade 2026.5.1 的 DataProvider API、informative pair 类型定义，以及当前 V11.29 策略代码的 4h lookup 路径。

结论：

- `DataProvider.get_pair_dataframe()` 支持 `candle_type` 参数。
- 当前 Freqtrade 的 `PairWithTimeframe` 类型定义是三元组：`tuple[str, str, CandleType]`。
- `IStrategy.informative_pairs()` 默认返回 `[]`。
- 当前 V11.29 继承链未覆盖 `informative_pairs()`。
- 当前 `regime_aware_base.py` 调用 `get_pair_dataframe(pair, timeframe="4h")`，没有显式 `candle_type="futures"`。
- 因此，剩余 `No data found for (..., 4h, )` warning 的安全修复应同时处理：
  - 注册 4h futures informative pairs；
  - 显式用 futures candle type 查询 4h dataframe。

本任务没有修改策略、bot 配置、dashboard、deploy、server 文件，也没有启动、停止或重启 bot。

## Server Context

Server:

```text
hostname: VM-0-8-ubuntu
date -u: Fri Jul  3 04:06:05 PM UTC 2026
```

Container state:

```text
freqtrade-v1129   Up 36 minutes   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days       127.0.0.1:8091->8091/tcp
```

Freqtrade version:

```text
Freqtrade Version: freqtrade 2026.5.1
Python Version: Python 3.14.5
CCXT Version: 4.5.55
```

## DataProvider Signature

Observed:

```text
DataProvider.get_pair_dataframe(self, pair: str, timeframe: str | None = None, candle_type: str = '') -> pandas.DataFrame
```

Observed source:

```python
def get_pair_dataframe(
    self, pair: str, timeframe: str | None = None, candle_type: str = ""
) -> DataFrame:
    timeframe = self.__fix_funding_rate_timeframe(pair, timeframe, candle_type)
    if self.runmode in (RunMode.DRY_RUN, RunMode.LIVE):
        data = self.ohlcv(pair=pair, timeframe=timeframe, candle_type=candle_type)
    else:
        timeframe = timeframe or self._config["timeframe"]
        data = self.historic_ohlcv(pair=pair, timeframe=timeframe, candle_type=candle_type)
    if len(data) == 0:
        logger.warning(f"No data found for ({pair}, {timeframe}, {candle_type}).")
    return data
```

Implication:

- Passing `candle_type="futures"` is API-supported.
- If `candle_type=""`, the warning message still prints an empty third field, even if lower-level default candle type handling exists.

## DataProvider OHLCV Behavior

Observed:

```text
DataProvider.ohlcv(self, pair: str, timeframe: str | None = None, copy: bool = True, candle_type: str = '') -> pandas.DataFrame
```

Relevant behavior:

```python
_candle_type = (
    CandleType.from_string(candle_type)
    if candle_type != ""
    else self._config["candle_type_def"]
)
return self._exchange.klines(
    (pair, timeframe or self._config["timeframe"], _candle_type), copy=copy
)
```

Observed `CandleType` values:

```text
spot
futures
mark
index
premiumIndex
funding_rate
```

Implication:

- `candle_type="futures"` maps to `CandleType.FUTURES`.
- The live cache key ultimately uses `(pair, timeframe, CandleType.FUTURES)` for futures candles.

## Informative Pair Type

Observed in `/freqtrade/freqtrade/constants.py`:

```python
PairWithTimeframe = tuple[str, str, CandleType]
ListPairsWithTimeframes = list[PairWithTimeframe]
```

Observed in exchange refresh loop:

```python
for pair, timeframe, candle_type in set(pair_list):
    ...
```

Observed `IStrategy.informative_pairs()` default:

```python
def informative_pairs(self) -> ListPairsWithTimeframes:
    return []
```

Implication:

- Current Freqtrade internals expect informative pair entries as 3-tuples containing `CandleType`.
- The docstring sample still shows 2-tuples, but runtime type and exchange refresh code use 3-tuples.
- Current V11.29 strategy must explicitly register 4h futures informative pairs if it wants DataProvider to cache those live OHLCV frames.

## Current Strategy Finding

Observed current V11.29 shared base:

```text
/freqtrade/project/strategies/regime_aware_base.py
```

Only current 4h DataProvider call:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"], timeframe="4h"
)
```

No `informative_pairs()` override was found in:

```text
/freqtrade/project/strategies/regime_aware_base.py
/freqtrade/project/strategies/RegimeAwareV1129ResidualDragMicroSizer.py
/freqtrade/project/strategies/RegimeAwareV1127DualTrapMicroSizer.py
```

Implication:

- The 4h futures pair/timeframe/candle type combination may not be preloaded into the live DataProvider cache.
- The current lookup asks for 4h with no explicit candle type.
- The remaining warning is expected until informative pair registration and explicit futures lookup are fixed.

## Runtime Warning Confirmation

Recent logs still show V11.29 running and emitting 4h warnings:

```text
2026-07-03 16:00:12,682 - freqtrade.data.dataprovider - WARNING - No data found for (SOL/USDT:USDT, 4h, ).
2026-07-03 16:00:31,113 - freqtrade.data.dataprovider - WARNING - No data found for (BNB/USDT:USDT, 4h, ).
...
2026-07-03 16:00:55,482 - freqtrade.data.dataprovider - WARNING - No data found for (TRX/USDT:USDT, 4h, ).
2026-07-03 16:05:37,939 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
```

No `Strategy analysis took ...` warning was observed in this inspection window.

## Recommended Task 24F Implementation

Recommended implementation:

1. Import `CandleType`:

```python
from freqtrade.enums import CandleType
```

2. Add `informative_pairs()` to `RegimeAwareBaseMixin`:

```python
def informative_pairs(self):
    if not self.dp:
        return []
    return [(pair, "4h", CandleType.FUTURES) for pair in self.dp.current_whitelist()]
```

3. Change `_load_4h()` DataProvider call:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"],
    timeframe="4h",
    candle_type="futures",
)
```

4. Keep local futures feather fallback unchanged.

5. Do not modify entry/exit/stake/risk logic.

## Expected Effect

Expected:

- DataProvider should preload `(pair, "4h", CandleType.FUTURES)` combinations.
- `_load_4h()` should query the same futures candle type explicitly.
- The warning should change from `(pair, 4h, )` to no warning if data is cached.

Not guaranteed:

- This does not guarantee trades/orders appear.
- This does not prove V11.29 can replace V10.8.2.
- This does not replace longer runtime observation.

## Verification Plan For Task 24F

Local:

```powershell
& 'C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile strategies/regime_aware_base.py
.\scripts\run_agent_readiness_checks.ps1
```

Server deploy should be separate:

```text
Task 24V: Deploy V11.29 4h Informative Futures Mapping Fix
```

Post-deploy observation:

- `freqtrade-v1129` remains `RUNNING`.
- `freqtrade-v1082` remains untouched.
- Fresh analysis cycle does not show `No data found for (..., 4h, )`.
- No `4h data unavailable, using safe defaults`.
- No `Strategy analysis took ...` regression.
- SQLite `trades/orders` are observed but not interpreted as replacement proof.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- print secrets;
- start, stop, or restart bots;
- run backtests;
- claim V11.29 replacement readiness.

## Recommended Next Task

Recommended next task:

```text
Task 24F: Implement V11.29 4h Informative Futures Mapping Fix
```

This task will touch `strategies/regime_aware_base.py`, so it needs explicit strategy-code authorization.

