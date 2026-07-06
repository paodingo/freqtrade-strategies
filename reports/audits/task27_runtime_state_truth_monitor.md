# Task 27: Runtime State Truth Monitor

## Summary

本任务修复一个核心可观测性问题：`container Up`、`API readable`、`bot state=running`、`trades/orders observed` 过去容易被混在一起，导致我们误以为 V11.29 已经真实运行多天。

本次只增强交易监控 state 输出，不修改策略、不修改 bot 配置、不启动/停止/restart bot、不运行回测。

## Root-Cause Context

只读服务器检查显示：

```text
SERVER_DATE Mon Jul  6 14:24:54 CST 2026
freqtrade-v1129 Up 2 days
freqtrade-v1082 Up 5 days
```

但 V11.29 日志显示它在今天才从 `STOPPED` 切换到 `RUNNING`：

```text
2026-07-06 03:53:30 UTC - Changing state from STOPPED to: RUNNING
```

换算为北京时间：

```text
2026-07-06 11:53:30 CST
```

SQLite 只读证据：

```text
V11.29:
trades = 0
orders = 0
open_trades = 0
closed_trades = 0
DB mtime = 2026-07-02 17:25:44 CST

V10.8.2:
trades = 6
orders = 12
closed_trades = 6
min_open_date = 2026-06-26 06:15:33.352116
max_open_date = 2026-07-01 02:16:09.203505
max_close_date = 2026-07-01 10:27:37.736000
```

结论：V11.29 的容器 uptime 不能代表 bot 的真实交易运行时长。

## Changes

更新 `scripts/check_trades.sh`，在 monitor state 中新增真实运行状态字段：

- `observed_at`
- `state_changed_at`
- `runtime_status`
- `execution_status`

新增状态含义：

| Field | Meaning |
| --- | --- |
| `api_probe_ok` | 当前 Freqtrade API 是否完整可观测 |
| `runtime_status=api_unobservable` | API 连续读取失败或无法完整观测 |
| `runtime_status=bot_not_running` | API 可读，但 bot state 不是 `running` |
| `runtime_status=bot_running` | API 可读，且 bot state 是 `running` |
| `execution_status=not_trading_bot_not_running` | bot 未运行，不能视作正在交易 |
| `execution_status=bot_running_no_trades_observed` | bot 在运行，但当前 API 未观测到任何 trades |
| `execution_status=bot_running_open_trades_observed` | bot 在运行，当前有 open trades |
| `execution_status=bot_running_closed_or_historical_trades_observed` | bot 在运行，API/DB 侧存在 closed 或历史 trades |

`state_changed_at` 只在 bot state 变化时更新；单纯轮询不会刷新该时间。

## Verification

本地验证：

```text
bash -n scripts/check_trades.sh
.\scripts\run_agent_readiness_checks.ps1
```

结果：通过。

服务器临时脚本 dry-run，使用临时 state 文件，不发送通知、不改 bot：

```text
output_bytes=0
```

生成的 runtime truth state：

```json
{
  "V11.29 Current Research Candidate": {
    "ok": true,
    "api_probe_ok": true,
    "runtime_status": "bot_running",
    "execution_status": "bot_running_no_trades_observed",
    "state": "running",
    "open": 0,
    "total": 0,
    "closed": 0
  },
  "V10.8.2 Historical Profit Benchmark": {
    "ok": true,
    "api_probe_ok": true,
    "runtime_status": "bot_running",
    "execution_status": "bot_running_closed_or_historical_trades_observed",
    "state": "running",
    "open": 0,
    "total": 6,
    "closed": 6
  }
}
```

第二次 dry-run 验证 `state_changed_at` 不随轮询刷新：

```text
V11.29 observed_at=2026-07-06T14:30:35+08:00 state_changed_at=2026-07-06T14:30:15+08:00
V10.8.2 observed_at=2026-07-06T14:30:35+08:00 state_changed_at=2026-07-06T14:30:15+08:00
```

## Server Deployment

本任务将更新后的 `scripts/check_trades.sh` 部署到服务器：

```text
/home/ubuntu/freqtrade-strategies/scripts/check_trades.sh
```

部署不需要重启交易 bot，也不修改 bot 配置。

## Boundary Confirmation

本任务没有：

- 修改 `strategies/**`
- 修改 `user_data/config*.json`
- 修改 `configs/**`
- 修改 dashboard 代码
- 修改 deploy 代码
- 读取 `.env`
- 读取或打印 `user_data/monitor.env`
- 打印 API key、交易所凭证、服务器密钥或 dashboard 密码
- 启动、停止或重启交易 bot
- 运行回测
- 修改 V10.8.2 或 V11.29 策略/config
- 得出 V11.29 替换 V10.8.2 的结论

## Current Assessment

V11.29 当前真实状态应表述为：

```text
container up, API readable, bot running since observed state transition, no trades/orders observed
```

而不是：

```text
V11.29 has been trading/running for days with no trades
```

## Recommended Next Task

推荐下一步：

```text
Task 28: V11.29 Zero-Trade Signal Audit
```

目标：

- 只读分析 V11.29 在 `RUNNING` 后是否产生 entry signals；
- 区分无信号、信号被 protection/pairlist/filter 阻断、策略条件过严、或数据仍不完整；
- 不改策略、不改 bot 配置、不重启 bot。
