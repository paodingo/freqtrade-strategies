# Task 22: V11.29 Strategy Analysis Performance Bottleneck Audit

状态：已完成。只读审计 V11.29 strategy analysis 性能瓶颈；未修改策略、配置、服务器文件，未重启 bot。

## Summary

V11.29 曾出现：

```text
Strategy analysis took 225.62s, more than 25% of the timeframe (225.00s). This can lead to delayed orders and missed signals.
```

本任务只读审计后判断：最可能的瓶颈不是 15m 指标本身，而是 `regime_aware_base.py` 的 `4h` informative fallback / regime 计算路径：

1. 对每个 pair 先调用 `self.dp.get_pair_dataframe(pair, timeframe="4h")`，该调用缺少 futures candle type，产生大量 `No data found for (..., 4h, )` warning。
2. DataProvider 查询失败后，每个 pair fallback 到本地 `data/futures/*-4h-futures.feather`。
3. fallback 后对完整 `4h` 历史数据运行 indicator 和逐行 regime detection。
4. 逐行 regime detection 使用 `detector.detect(df.iloc[: index + 1])`，每一行都传入从开头到当前行的切片，形成近似 O(N²) 计算形态。

只读 micro-benchmark 显示，单独对 12 个 pair 的 `4h` fallback + indicator + full-history regime loop 就需要约 `15.64s`。这还没有计算 Freqtrade 自身 DataProvider 路径、15m 指标、多层 V11 子类 entry/exit 逻辑、运行时 I/O、交易所/API 交互和服务器资源竞争。因此它是合理的主要瓶颈候选。

本任务没有得出 V11.29 替换结论，也没有把 0 trades/orders 解释为策略失败。

## Boundary confirmation

本任务执行了：

- read-only local report/code grep；
- read-only SSH；
- `docker logs --tail`；
- `docker stats --no-stream`；
- `docker exec -i freqtrade-v1129 python -` 做只读 micro-benchmark；
- read-only server strategy code inspection。

本任务没有：

- 修改策略；
- 修改 config；
- 修改服务器文件；
- 读取 `.env`；
- 读取 `user_data/monitor.env`；
- 打印 API key、交易所凭证、server key、dashboard password、token；
- 下载数据；
- 启动、停止、重启 bot；
- 运行回测；
- 生成替换结论。

## Server state

检查时间：

```text
host: VM-0-8-ubuntu
date: 2026-07-03T23:08:41+08:00
```

运行容器：

| Container | Status | Port |
|---|---|---|
| `freqtrade-v1129` | `Up 6 hours` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1082` | `Up 3 days` | `127.0.0.1:8091->8091/tcp` |

Resource snapshot after stopping legacy containers:

| Container | CPU | Memory | Memory % | PIDs |
|---|---:|---:|---:|---:|
| `freqtrade-v1129` | `0.19%` | `378.3MiB / 1.922GiB` | `19.23%` | `14` |
| `freqtrade-v1082` | `0.15%` | `427.3MiB / 1.922GiB` | `21.72%` | `18` |

## Runtime log evidence

`docker logs --tail 2000 freqtrade-v1129` contained one slow-analysis warning:

```text
2026-07-03 08:49:57,599 - freqtrade.freqtradebot - WARNING - Strategy analysis took 225.62s, more than 25% of the timeframe (225.00s). This can lead to delayed orders and missed signals.
```

Recent heartbeat logs after legacy container stop show V11.29 still running:

```text
Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
```

## Code hotspot evidence

V11.29 strategy inheritance:

```text
RegimeAwareV1129ResidualDragMicroSizer
  -> RegimeAwareV1127DualTrapMicroSizer
  -> RegimeAwareV1124ReboundChaseSizer
  -> ...
  -> regime_aware_base.py
```

Key hotspot in `regime_aware_base.py`:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"], timeframe="4h"
)
```

This first DataProvider call lacks explicit futures candle type and correlates with:

```text
No data found for (PAIR/USDT:USDT, 4h, ).
```

Fallback path:

```python
raw = pd.read_feather(path)
```

Full-history regime loop:

```python
for index in range(len(informative_4h)):
    if index < self.startup_candle_count:
        regimes.append(RegimeDetector.RANGING)
    else:
        regimes.append(
            self.regime_detector.detect(informative_4h.iloc[: index + 1])
        )
```

This loop repeatedly slices from row 0 to current row for every 4h candle. With about `5486` rows per pair and 12 pairs, this is a strong structural bottleneck.

## Micro-benchmark evidence

Executed inside `freqtrade-v1129` container, read-only:

- read each futures `4h` feather file;
- compute indicators using the same `RegimeDetector` / TA path;
- run the same full-history regime loop;
- do not trade, do not read config, do not write files.

Results:

| Pair | Rows | Read seconds | Indicator seconds | Loop seconds | Total seconds |
|---|---:|---:|---:|---:|---:|
| BTC | 5486 | 0.0231 | 0.0117 | 1.1841 | 1.2189 |
| ETH | 5486 | 0.0111 | 0.0152 | 1.2665 | 1.2928 |
| SOL | 5486 | 0.0056 | 0.0130 | 1.2531 | 1.2718 |
| BNB | 5486 | 0.0050 | 0.0107 | 1.2003 | 1.2160 |
| XRP | 5486 | 0.0049 | 0.0107 | 1.2054 | 1.2210 |
| DOGE | 5486 | 0.0066 | 0.0147 | 1.2960 | 1.3173 |
| ADA | 5486 | 0.0051 | 0.0112 | 1.2507 | 1.2669 |
| LINK | 5486 | 0.0068 | 0.0105 | 1.2207 | 1.2381 |
| AVAX | 5486 | 0.0051 | 0.0110 | 1.2382 | 1.2542 |
| TRX | 5486 | 0.0100 | 0.0181 | 1.8772 | 1.9053 |
| LTC | 5486 | 0.0057 | 0.0122 | 1.2051 | 1.2230 |
| BCH | 5486 | 0.0047 | 0.0103 | 1.1955 | 1.2104 |

Total for the 12-pair `4h` path:

```text
15.6357 seconds
```

Interpretation:

- `pd.read_feather` is not the dominant cost in this isolated test.
- TA indicator computation is also not dominant.
- The full-history `for index in range(len(informative_4h))` loop dominates.
- The loop cost is currently about `1.2s` per pair, before accounting for the rest of Freqtrade analysis.

## Bottleneck ranking

| Rank | Bottleneck candidate | Evidence | Severity |
|---:|---|---|---|
| 1 | Full-history regime loop with repeated `.iloc[: index + 1]` | observed code + benchmark; dominates per-pair 4h path | high |
| 2 | Repeated fallback path per pair / analysis cycle | observed code; likely repeats reading and full recomputation | high |
| 3 | DataProvider futures candle type mismatch | observed Task 21A; causes repeated no-data warning before fallback | medium-high |
| 4 | Too many pairs for current per-pair full-history logic | 12 pairs x 5486 rows x full loop | medium-high |
| 5 | 15m indicators / rolling calculations | observed code, mostly vectorized | medium-low |
| 6 | Legacy container resource contention | reduced after stopping V1127/V1116 | lower now |

## Safe optimization plan, not executed

Recommended future Task 22R / Task 22F scope:

1. Replace full-history regime recomputation with incremental or vectorized logic.
   - Avoid `detect(df.iloc[: index + 1])` for every row.
   - Compute regime from current row and minimal carried state where possible.

2. Limit 4h history used in live analysis.
   - Live mode does not need all `5486` 4h rows every cycle.
   - Use a bounded lookback sufficient for `startup_candle_count` plus indicator windows.

3. Cache 4h fallback data per pair.
   - Avoid repeated `pd.read_feather` and full indicator recompute every analysis cycle.
   - Cache should be carefully invalidated by file mtime / latest candle.

4. Fix or avoid the DataProvider candle type mismatch.
   - If Freqtrade supports futures candle type in `informative_pairs`, use explicit mapping.
   - Or avoid the initial noisy DataProvider query if local futures fallback is intended source.

5. Reduce pair count only as a last resort.
   - Pair reduction would reduce cost but changes strategy opportunity surface.
   - Prefer code-path efficiency before changing trading surface.

## Risks of optimizing incorrectly

Future code changes must preserve:

- `RegimeDetector` hysteresis semantics;
- `startup_candle_count` behavior;
- no lookahead bias;
- correct forward-fill into 15m timeframe;
- futures pair naming and candle type behavior;
- dry-run safety boundaries.

Any code change must be followed by a controlled dry-run observation and no replacement claim.

## Whether Task 23 can proceed

Task 23 can proceed as a read-only re-observation only, but it will likely still show `trades/orders = 0` unless the performance/data path is fixed or enough new market conditions occur.

Recommended next step is a fix-plan task before code edits:

```text
Task 22R: V11.29 4h Regime Performance Fix Plan
```

Then a separately authorized implementation task can patch the strategy or helper code.

## GitHub note

The branch was previously pushed, but this Task 22 commit will be local until pushed again after completion.

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task22_v1129_strategy_analysis_performance_bottleneck_audit.md
tasks/active/TASK-0022-v1129-strategy-analysis-performance-bottleneck-audit.md
```
