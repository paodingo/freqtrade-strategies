# Freqtrade 策略仓库

这是一个 BTC/USDT:USDT 合约策略实验和验证仓库。当前 clean worktree 的重点不是继续沿用旧的 V6.5 / V6.6 双 bot 对比叙事，而是维护一个有 guard/readiness 约束的 harness 基座，并围绕 V11.29 做真实执行验证准备。

## 当前状态

| 对象 | 当前状态 | 说明 |
| --- | --- | --- |
| Clean harness | active | 当前开发应在 clean worktree 中进行，并通过 readiness checks 约束变更面。 |
| V11.29 | validation insufficient | 已有 SQLite snapshot 取证，但 V11.29 `trades = 0`、`orders = 0`，不能验证执行质量。 |
| V10.8.2 | benchmark evidence only | snapshot 中存在有限 closed trades / orders，可作为对照数据来源，但当前不能和 V11.29 做 same-window execution quality comparison。 |
| V6.5 / V6.6 | historical | 旧 dry-run 对比和文档仍保留作历史参考，不再是本文档定义的当前主线。 |
| Dashboard / deploy / live docs | stale/high-risk | `DEPLOY.md` 和 `LIVE_TRADING.md` 仍可能包含旧版本运行假设，未完成当前化前不要按其中内容推断 V11.29 操作方式。 |

## 当前验证边界

V11.29 尚未通过真实执行验证，也不能被判断为可以替换 V10.8.2。当前已经确认的是：

- V11.29 snapshot 中 `trades = 0`。
- V11.29 snapshot 中 `orders = 0`。
- V10.8.2 snapshot 中存在有限对照样本。
- 当前缺少足够样本验证 slippage、fee quality、latency、filled price、same-window comparison 和 replacement readiness。

后续应继续做 V11.29 数据覆盖和运行性能审计，尤其是 4h informative data availability、策略分析耗时、信号链路和 zero-trade cause。

## 策略版本说明

- `RegimeAwareV61`：历史对照版本，趋势入场、关闭震荡入场，并启用 Freqtrade protections。
- `RegimeAwareV62`：历史基线，在 V6.1 信号基础上支持固定额度的保守加仓。
- `RegimeAwareV63`：历史稳定基线；按账户最大亏损百分比反推加仓额度，并检查止损/强平距离、波动、冷却时间和可用余额。
- `RegimeAwareV64`：历史进攻挑战者；15m 趋势版，作为后续版本参考。
- `RegimeAwareV65`：历史进攻基线；曾用于 15m 震荡短线 dry-run 对比。
- `RegimeAwareV66`：历史选择性候选；曾在 V6.5 基础上加入 24h/48h 箱体位置过滤。
- `RegimeAwareV6`、`RegimeAwareV8`、`RegimeAwareV9`：历史或实验参考版本。
- V10.8.2 / V11.29：当前验证链路中的关键版本标签；任何替换判断必须依赖后续真实执行验证报告。

## 常用只读开发命令

```bash
# 完整本地冒烟测试，需要 Docker 和 Node。
bash scripts/run_tests.sh
```

```powershell
# 当前 harness readiness gate。
.\scripts\run_agent_readiness_checks.ps1
```

不要把旧文档中的 V6.5 / V6.6 dry-run 命令当作当前 V11.29 操作手册。启动、停止、重启 bot，修改策略/config，或执行 server/live 操作，都需要单独授权任务。

## 文档

- 部署和运维：[DEPLOY.md](DEPLOY.md) 当前仍含旧版本运行假设，待单独冻结或重写。
- 实盘准备：[LIVE_TRADING.md](LIVE_TRADING.md) 当前仍含旧版本 live readiness 叙事，待单独冻结或重写。
- 策略说明：[STRATEGY_GUIDE.md](STRATEGY_GUIDE.md)
- V11.29 execution schema：[docs/harness/v1129_execution_report_schema.md](docs/harness/v1129_execution_report_schema.md)
- V11.29 insufficient report：[reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md](reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md)

## 风险状态

当前仍处于 dry-run 证据整理和真实执行验证准备阶段。回测、模拟盘和不足样本 snapshot 都不能证明真实成交表现。任何实盘启动或替换判断前，都必须完成数据覆盖、运行性能、真实成交样本、费用/滑点/延迟和同窗对照验证。
