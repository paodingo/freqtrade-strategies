# Task 21A: V11.29 Non-Secret Config and Informative Mapping Audit

状态：已完成。只读检查 V11.29 非 secret config 字段和 strategy informative mapping；未修改策略、配置、服务器文件，未重启 bot。

## Summary

Task 21A 解释了为什么 V11.29 日志会反复出现：

```text
No data found for (PAIR/USDT:USDT, 4h, ).
```

核心发现：V11.29 继承的 `regime_aware_base.py` 里，`informative_pairs()` 返回的是二元组：

```python
return [(pair, "4h") for pair in whitelist]
```

并且 `_load_4h()` 先调用：

```python
self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="4h")
```

这里没有显式传入 futures candle type。因此 Freqtrade DataProvider 日志里的第三个字段为空：`(pair, 4h, )`。这与磁盘上的文件命名 `*-4h-futures.feather` 不一致。

但同一个 `_load_4h()` 还有本地 futures feather fallback：

```text
/freqtrade/project/user_data/data/futures/<PAIR>_USDT_USDT-4h-futures.feather
```

Task 21 已证明这些 futures `4h` 文件存在且可读。因此当前更准确的判断是：

- DataProvider 的第一阶段 `4h` 查询大概率存在 candle type mismatch。
- 但 fallback 可能仍能成功读取本地 futures feather。
- 日志中的 `No data found` 不能单独证明 V11.29 没有 4h 数据进入策略。
- 仍需 Task 22 审计性能瓶颈，因为 fallback 每轮读 feather + 逐行 regime detection 可能是 `Strategy analysis took 225.62s` 的重要原因。

## Boundary confirmation

本任务只执行只读操作：

- 读取 Task 21 报告；
- 只读 grep 服务器 config 的非 secret 字段；
- 只读查看 V11.29 strategy mapping 相关代码片段；
- 只读查看 V11.29 logs 中的 4h warning / fallback warning。

本任务没有：

- 读取 `.env`
- 读取 `user_data/monitor.env`
- 打印 API key、交易所凭证、server key、dashboard password、token
- 修改策略
- 修改 config
- 修改 dashboard
- 修改 deploy
- 下载数据
- 启动、停止、重启 bot
- 运行回测
- 生成替换结论

## Non-secret config findings

只读检查 `config_multi_futures_v1129.json` 的非 secret 字段：

| Field | Observed |
|---|---|
| `max_open_trades` | `4` |
| `stake_currency` | `USDT` |
| `stake_amount` | `2500` |
| `dry_run` | `true` |
| `db_url` | `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite` |
| `trading_mode` | `futures` |
| `margin_mode` | `isolated` |
| `pairlists.method` | `StaticPairList` |
| `pairlists.allow_inactive` | `false` |

Observed pair whitelist:

```text
BTC/USDT:USDT
ETH/USDT:USDT
SOL/USDT:USDT
BNB/USDT:USDT
XRP/USDT:USDT
DOGE/USDT:USDT
ADA/USDT:USDT
LINK/USDT:USDT
AVAX/USDT:USDT
LTC/USDT:USDT
TRX/USDT:USDT
BCH/USDT:USDT
```

No `dataformat_ohlcv` or `candle_type_def` line was observed in the safe grep output.

## Strategy mapping findings

V11.29 strategy file:

```text
RegimeAwareV1129ResidualDragMicroSizer.py
```

Inheritance:

```text
RegimeAwareV1129ResidualDragMicroSizer
  -> RegimeAwareV1127DualTrapMicroSizer
  -> ...
  -> regime_aware_base.py
```

Relevant base mapping:

```python
def informative_pairs(self):
    if not self.dp:
        return []
    whitelist = self.dp.current_whitelist()
    return [(pair, "4h") for pair in whitelist]
```

Relevant DataProvider query:

```python
informative_4h = self.dp.get_pair_dataframe(
    pair=metadata["pair"], timeframe="4h"
)
```

Relevant fallback file candidates:

```python
data_dir / "binance" / f"{pair_slug}-4h.feather"
data_dir / f"{pair_slug}-4h.feather"
data_dir / "futures" / f"{pair_slug_futures}-4h-futures.feather"
```

Relevant fallback failure log:

```python
logger.warning("Failed to load 4h feather: %s", error)
```

Relevant final failure log:

```python
logger.warning("4h data unavailable, using safe defaults")
```

## Log interpretation

Read-only logs showed many DataProvider warnings:

```text
No data found for (..., 4h, ).
```

But targeted grep did not find corresponding `Failed to load 4h feather` or `4h data unavailable, using safe defaults` lines in the checked window.

Interpretation:

- The warning likely comes from the first `self.dp.get_pair_dataframe(..., timeframe="4h")` path.
- The third log field is empty, consistent with missing explicit futures candle type.
- The fallback may still be reading local futures feather successfully.
- Therefore, the repeated warning is real, but it may be a noisy symptom rather than the direct cause of zero trades.

## Root-cause classification

| Hypothesis | Current status | Notes |
|---|---|---|
| Complete absence of 4h files | unlikely | Task 21 found all 12 futures 4h files. |
| Stale 4h files | possible but not sufficient | Files end at `2026-07-03 04:00:00+00:00`; still does not fully explain DataProvider empty candle type warnings. |
| Candle type mismatch in DataProvider call | likely | `informative_pairs()` and `get_pair_dataframe()` do not specify futures candle type. |
| Fallback failure | not observed in checked logs | No `Failed to load 4h feather` / `4h data unavailable` lines found in targeted window. |
| Performance bottleneck from fallback/regime loop | likely enough for Task 22 | Fallback reads feather and computes indicators/regime repeatedly per pair. |
| Zero trades caused solely by 4h missing data | not proven | Need signal/performance audit. |

## Safe fix options, not executed

No fix was executed in this task.

Potential future fix paths:

1. `Task 22`: Performance bottleneck audit first.
   - Inspect whether repeated local feather reads and full-history regime loop cause 225s analysis.
   - This is now the highest-value next step.

2. Future mapping fix task, only after review:
   - Make informative pair registration candle-type aware, if Freqtrade supports the required tuple form for futures candle type.
   - Or remove/avoid the noisy DataProvider call if the local futures fallback is intended authority.
   - Or cache local 4h data per pair instead of reading feather every analysis cycle.

3. Future data refresh task only if needed:
   - Refresh futures `15m` / `4h` files after confirming stale files matter.
   - Do not treat refresh as a complete fix for the warning until candle type mapping is resolved.

## Recommended next task

推荐 `Task 22: V11.29 Strategy Analysis Performance Bottleneck Audit`。

Reason:

- Data files exist.
- DataProvider warning likely comes from candle type mismatch.
- Fallback may still succeed.
- The observed `Strategy analysis took 225.62s` warning is now a stronger actionable risk.

Task 22 should remain read-only unless a later task explicitly authorizes code changes.

## GitHub / remote note

During this task, local git remote state was also checked:

```text
origin = https://github.com/paodingo/freqtrade-strategies.git
remote heads checked: master exists
remote head codex/btc-mvp-system-harnessed: not found
current local branch: codex/btc-mvp-system-harnessed
upstream tracking: none observed
```

This means the current harness branch commits are local unless pushed later.

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task21a_v1129_non_secret_config_informative_mapping_audit.md
tasks/active/TASK-0021A-v1129-non-secret-config-informative-mapping-audit.md
```
