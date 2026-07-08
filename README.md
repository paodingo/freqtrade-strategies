# Freqtrade 策略仓库

这是一个 BTC/USDT:USDT 合约策略实验和验证仓库。当前 clean worktree 的重点不是继续沿用旧的 V6.5 / V6.6 双 bot 对比叙事，而是维护一个有 guard/readiness 约束的 harness 基座，并围绕 V11.30 做运行诊断、数据新鲜度审计和下一策略候选决策。

## 当前状态

| 对象 | 当前状态 | 说明 |
| --- | --- | --- |
| Clean harness | active | 当前开发应在 clean worktree 中进行，并通过 readiness checks 约束变更面。 |
| V11.30 | current observation candidate | 当前运行中的 crash-rebound shadow；SQLite 仍为 `trades = 0`、`orders = 0`，并发现 15m market data content stale。 |
| V11.29 | previous investigation target | 已完成多轮 insufficient / zero-trade 取证，现在不再是当前主线。 |
| V10.8.2 | benchmark evidence only | snapshot 中存在有限 closed trades / orders，可作为历史对照数据来源，但当前不能和 V11.30 做 same-window execution quality comparison。 |
| V6.5 / V6.6 | historical | 旧 dry-run 对比和文档仍保留作历史参考，不再是本文档定义的当前主线。 |
| Dashboard / deploy / live docs | guarded/high-risk | `DEPLOY.md` 和 `LIVE_TRADING.md` 是历史/边界文档；不要按其中旧命令直接操作当前 V11.30。 |

## 当前验证边界

V11.30 尚未通过真实执行验证，也不能被判断为可以替换 V10.8.2。当前已经确认的是：

- V11.30 当前 SQLite 中 `trades = 0`。
- V11.30 当前 SQLite 中 `orders = 0`。
- V11.30 15m feather 内容存在明显滞后，最新 checked candle 不是当前实时市场。
- V10.8.2 snapshot 中存在有限历史对照样本。
- 当前缺少足够样本验证 slippage、fee quality、latency、filled price、same-window comparison 和 replacement readiness。

后续应优先处理 V11.30 数据刷新链路、live decision trace、运行性能和 zero-trade cause。不要在这些问题解决前直接调整 live 策略参数。

## 策略版本说明

- `RegimeAwareV61`：历史对照版本，趋势入场、关闭震荡入场，并启用 Freqtrade protections。
- `RegimeAwareV62`：历史基线，在 V6.1 信号基础上支持固定额度的保守加仓。
- `RegimeAwareV63`：历史稳定基线；按账户最大亏损百分比反推加仓额度，并检查止损/强平距离、波动、冷却时间和可用余额。
- `RegimeAwareV64`：历史进攻挑战者；15m 趋势版，作为后续版本参考。
- `RegimeAwareV65`：历史进攻基线；曾用于 15m 震荡短线 dry-run 对比。
- `RegimeAwareV66`：历史选择性候选；曾在 V6.5 基础上加入 24h/48h 箱体位置过滤。
- `RegimeAwareV6`、`RegimeAwareV8`、`RegimeAwareV9`：历史或实验参考版本。
- V10.8.2 / V11.29 / V11.30：当前验证链路中的关键版本标签；V11.30 是当前观察候选，任何替换判断必须依赖后续真实执行验证报告。

## 常用只读开发命令

```bash
# 完整本地冒烟测试，需要 Docker 和 Node。
bash scripts/run_tests.sh
```

```powershell
# 当前 harness readiness gate。
.\scripts\run_agent_readiness_checks.ps1
```

不要把旧文档中的 V6.5 / V6.6 dry-run 命令当作当前 V11.30 操作手册。启动、停止、重启 bot，修改策略/config，或执行 server/live 操作，都需要单独授权任务。

## 文档

- 部署和运维：[DEPLOY.md](DEPLOY.md) 当前仍含旧版本运行假设，待单独冻结或重写。
- 实盘准备：[LIVE_TRADING.md](LIVE_TRADING.md) 当前仍含旧版本 live readiness 叙事，待单独冻结或重写。
- 策略说明：[STRATEGY_GUIDE.md](STRATEGY_GUIDE.md)
- V11.30 watch-only telemetry：[reports/v1130_observation/v1130_watch_only_telemetry_report.md](reports/v1130_observation/v1130_watch_only_telemetry_report.md)
- V11.30 decision trace：[reports/v1130_observation/v1130_decision_trace_report.md](reports/v1130_observation/v1130_decision_trace_report.md)
- V11.29 execution schema：[docs/harness/v1129_execution_report_schema.md](docs/harness/v1129_execution_report_schema.md)
- V11.29 insufficient report：[reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md](reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md)

## 风险状态

当前仍处于 dry-run 证据整理和真实执行验证准备阶段。回测、模拟盘和不足样本 snapshot 都不能证明真实成交表现。任何实盘启动或替换判断前，都必须完成数据覆盖、运行性能、真实成交样本、费用/滑点/延迟和同窗对照验证。
