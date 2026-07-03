# Task 22R: V11.29 4h Regime Performance Fix Plan

状态：已完成。只生成 V11.29 4h regime 性能修复计划；未修改策略代码、bot 配置或服务器。

## Summary

Task 22 已定位：V11.29 的主要性能风险在 `regime_aware_base.py` 的 4h regime 计算路径，尤其是：

```python
for index in range(len(informative_4h)):
    if index < self.startup_candle_count:
        regimes.append(RegimeDetector.RANGING)
    else:
        regimes.append(
            self.regime_detector.detect(informative_4h.iloc[: index + 1])
        )
```

这个写法对每根 4h candle 都传入从开头到当前行的切片，形成近似 O(N²) 的全历史重算。Task 22 的只读 micro-benchmark 显示，仅 12 个 pair 的 4h fallback / indicator / regime loop 就约 `15.64s`。

推荐后续实施分两步：

1. Task 22F：在 clean worktree 中实现一个最小性能修复，只改 `strategies/regime_aware_base.py` 和对应测试/审计文件。
2. Task 22V：部署/同步到服务器并重启 V11.29 前，先做明确授权和备份；本 Task 22R 不做服务器写操作。

## Non-goals

本计划不允许：

- 直接修改服务器策略文件；
- 修改 V11.29 config；
- 重启 bot；
- 下载数据；
- 改变 pair whitelist；
- 改变 stake / leverage / stoploss / ROI；
- 声称 V11.29 已通过真实执行验证；
- 声称 V11.29 可以替换 V10.8.2。

## Recommended implementation scope

推荐 `Task 22F: Implement V11.29 4h Regime Performance Fix`。

允许修改：

- `strategies/regime_aware_base.py`
- narrowly scoped tests if present / feasible
- `reports/audits/task22f_v1129_4h_regime_performance_fix.md`
- `tasks/active/TASK-0022F-v1129-4h-regime-performance-fix.md`

禁止修改：

- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- server files
- live/server operation surface

## Fix option A: bounded 4h lookback

最小可行修复：

- 在 `populate_indicators()` 中，只对最近一段 4h 数据计算 regime。
- 保留足够 lookback，建议：

```text
lookback = max(startup_candle_count + 300, 600)
```

理由：

- `startup_candle_count = 200`；
- 4h indicator windows 主要是 EMA55、rolling 50、ADX/ATR 14；
- 600 根 4h candle 约 100 天，远大于指标 warmup；
- 从 5486 行降到 600 行，理论上显著减少 O(N²) loop 成本。

注意：

- bounded lookback 可能改变很早以前的 regime hysteresis carried state；
- 但 live decision 只依赖当前窗口，且 600 根 4h 已覆盖足够历史；
- 实现后必须验证最后若干根 regime 与旧算法在相同窗口上的差异。

## Fix option B: incremental regime calculation

更干净但风险略高：

- 改造 `RegimeDetector` 或新增 helper，让 `detect()` 只接收当前 row 或最小状态；
- 避免每步传 `df.iloc[: index + 1]`；
- 保留 hysteresis state。

优点：

- 从结构上消除 O(N²)。

风险：

- 需要理解 `RegimeDetector.detect()` 的状态语义；
- 更容易引入行为变化；
- 不建议作为第一刀，除非测试覆盖足够。

## Fix option C: per-pair 4h cache

可作为第二阶段：

- 缓存 fallback feather 的 processed informative dataframe；
- cache key 包含 pair、file path、mtime、latest candle；
- 如果 file mtime / latest candle 未变，则复用 processed 4h indicators/regime。

优点：

- 避免每轮重复 read/indicator/loop。

风险：

- Freqtrade strategy instance 生命周期和多 pair 调用时序要谨慎；
- 必须避免跨 pair 污染；
- cache invalidation 错误会导致 stale signal。

建议：先做 bounded lookback，再做 cache。

## Fix option D: candle type mapping cleanup

Task 21A 显示 `informative_pairs()` 和 `get_pair_dataframe()` 没有指定 futures candle type，导致 DataProvider warning。

这可以另起任务处理：

- 如果 Freqtrade 当前版本支持 informative tuple 携带 candle type，则改为显式 futures candle type；
- 如果不支持，则减少或跳过无效 DataProvider 查询，直接使用本地 futures fallback；
- 需要先确认 Freqtrade 2026.5.1 的接口约定。

建议：不要把 candle type mapping cleanup 和 O(N²) 性能修复混在同一任务里，避免行为面过大。

## Recommended first patch

首个实施任务建议只做：

1. 在 `regime_aware_base.py` 增加一个小 helper，例如：

```python
def _bounded_informative_4h(self, informative_4h: DataFrame) -> DataFrame:
    lookback = max(self.startup_candle_count + 300, 600)
    if len(informative_4h) <= lookback:
        return informative_4h.copy()
    return informative_4h.tail(lookback).copy()
```

2. 在 compute indicators / regime loop 前调用它。

3. 保持现有 fallback / merge 语义不变。

4. 不改 entry rules、stake sizing、risk manager、pairlist、config。

## Verification plan for Task 22F

必须验证：

1. Syntax:

```powershell
python -m py_compile strategies/regime_aware_base.py
```

如果系统 `python` 不可用，使用项目已有可用 Python 或容器方式。

2. Micro-benchmark:

- 同一 12 pair 4h benchmark；
- 对比 patch 前 `15.64s`；
- 目标：4h path 明显低于 patch 前，最好低于 `3s`。

3. Behavioral sanity:

- 对至少 BTC / ETH / SOL 的最后 50 根 4h candle，比较 old vs bounded 的关键列是否存在：
  - `regime`
  - `ema21`
  - `ema55`
  - `plus_di`
  - `minus_di`
  - `bb_width`
  - `bb_width_mean`
- 若 regime 值不同，需要报告差异，不能隐瞒。

4. Harness:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

注意：当前 guard 默认阻断 `strategies/**`。因此 Task 22F 若要修改 `strategies/regime_aware_base.py`，必须先有明确授权，并可能需要一个精确 guard exception 或临时任务边界更新。不能用 `git add -A` 或 `git add .`。

## Deployment plan after code fix

不要在 Task 22F 中直接部署。后续应单独执行：

```text
Task 22V: Deploy V11.29 4h Performance Fix to Server
```

该任务应：

- 明确用户授权；
- 备份服务器当前策略文件；
- 只同步已审查的目标文件；
- 重启 only `freqtrade-v1129`；
- 不触碰 `freqtrade-v1082`；
- 验证 logs 中是否不再出现 225s analysis；
- 验证 trades/orders 是否仍为 observed state，不做替换结论。

## Recommended next task

推荐下一步：

```text
Task 22F: Implement V11.29 4h Regime Performance Fix
```

但这将触碰 `strategies/regime_aware_base.py`，属于策略代码面。需要你明确授权后再执行。

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task22r_v1129_4h_regime_performance_fix_plan.md
tasks/active/TASK-0022R-v1129-4h-regime-performance-fix-plan.md
```
