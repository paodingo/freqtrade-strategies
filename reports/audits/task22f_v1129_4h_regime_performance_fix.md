# Task 22F: V11.29 4h Regime Performance Fix

## Summary

本任务已按 Task 22R 的建议，在 clean worktree 中实现最小 4h regime 性能修复。

实际修改仅限：

- `strategies/regime_aware_base.py`
- `reports/audits/task22f_v1129_4h_regime_performance_fix.md`
- `tasks/active/TASK-0022F-v1129-4h-regime-performance-fix.md`

本任务没有修改 bot 配置、dashboard、deploy、secret、服务器文件，也没有启动、停止、重启任何 bot。

## Change Implemented

在 `RegimeAwareBaseMixin` 中新增：

```python
def _bounded_informative_4h(self, informative_4h: DataFrame) -> DataFrame:
    lookback = max(self.startup_candle_count + 300, 600)
    if len(informative_4h) <= lookback:
        return informative_4h.copy()
    return informative_4h.tail(lookback).copy()
```

并在 `populate_indicators()` 的 4h indicator / regime loop 之前调用：

```python
informative_4h = self._bounded_informative_4h(informative_4h)
```

## Rationale

Task 22 已确认主要性能瓶颈来自 `regime_aware_base.py` 中对完整 4h 历史的逐行重算：

```python
for index in range(len(informative_4h)):
    self.regime_detector.detect(informative_4h.iloc[: index + 1])
```

服务器 V11.29 4h 数据约 5486 根 candle，完整历史逐行切片会形成近似 O(N^2) 成本。当前修复把 live 决策所需的 4h 输入窗口限制到 600 根 candle，覆盖约 100 天 4h 数据，并保留明显超过 `startup_candle_count = 200` 和主要指标 warmup 需求的空间。

## Behavioral Boundary

本任务没有修改：

- entry rule
- exit rule
- stoploss
- ROI
- stake sizing
- leverage
- pair whitelist
- bot config
- database
- server runtime

本任务不声称：

- V11.29 已通过真实执行验证；
- V11.29 可以替换 V10.8.2；
- 0 trades / 0 orders 已被解决。

## Expected Performance Effect

预期效果：

- 4h regime loop 输入从约 5486 rows 降至最多 600 rows；
- 大幅降低 `detect(informative_4h.iloc[: index + 1])` 的重复切片和计算成本；
- 降低 V11.29 出现 `Strategy analysis took ...` 超长耗时的风险。

需要后续 Task 22V 或 Task 23 在服务器上观察：

- V11.29 是否仍出现 225s 级别 analysis warning；
- V11.29 是否能按周期完成分析；
- SQLite 是否仍为 0 trades / 0 orders；
- 日志中是否还出现 4h data / no signal / protection / filter 相关问题。

## Verification

已执行：

```powershell
& 'C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile strategies/regime_aware_base.py
```

通过。

说明：本机 `python` 命令当前解析到 WindowsApps 占位符，不能用于本任务验证；因此使用 Codex bundled Python。

未在本任务执行：

- server deployment；
- bot restart；
- backtest；
- live trade validation；
- V11.29 / V10.8.2 replacement comparison。

## Guard Note

`strategies/**` 默认由 readiness guard 阻断，这是正确的高风险边界。本任务基于用户对 Task 22F 的明确执行授权修改了单个策略共享基础文件，但没有永久放宽 guard 规则，也没有把 `strategies/**` 加入 harness allowlist。

因此，未提交状态下的 readiness guard 会按设计阻断该策略 diff；提交后 clean worktree readiness 可以通过。

## Risk

主要风险：

- 早期历史回测结果可能因只保留最后 600 根 4h candle 而不同；
- 如果后续需要精确复现完整历史 regime 序列，应另起任务做 incremental regime calculation 或测试专用 full-history mode；
- 本修复只解决 4h full-history loop 性能问题，不解决 4h candle type warning 或交易信号缺失问题。

## Recommended Next Task

推荐下一步：

```text
Task 22V: Deploy V11.29 4h Performance Fix to Server
```

Task 22V 应该单独授权，并且只做：

- 备份服务器当前 V11.29 策略文件；
- 同步 `strategies/regime_aware_base.py`；
- 只重启 `freqtrade-v1129`；
- 不触碰 `freqtrade-v1082`；
- 观察 analysis 耗时、日志错误和 SQLite trades/orders。
