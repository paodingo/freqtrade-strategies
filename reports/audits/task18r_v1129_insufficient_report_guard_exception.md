# Task 18R: Allow V11.29 Insufficient Report Exact Paths

状态：已完成，未进入 Task 18。

## Summary

本任务只为 Task 18 的 snapshot-based insufficient report 生成器和两个报告输出增加精确 guard 例外。没有放宽真实 V11.29 策略、配置、交易数据、SQLite、dashboard、server 或 live 操作面。

## Preconditions

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 17 commit：`d9ee980 Inspect V11.29 SQLite snapshot schema`
- 初始 `git status --short --untracked-files=all`：empty
- 初始 readiness：pass

## Exact Allowlist Added

`scripts/guard_harness_diff.js` 新增精确允许：

- `scripts/build_v1129_snapshot_insufficient_report.js`
- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json`
- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md`

`scripts/guard_trading_surface.js` 新增精确允许：

- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json`
- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md`

## Explicit Non-Expansion

- 未允许 `reports/v1129_execution_validation/**`
- 未允许 `reports/*v1129*`
- 未允许 `scripts/build_v1129_*`
- 未允许 SQLite snapshot 进入 Git
- 未允许真实 execution report 的任意通配路径
- 未新增全局 bypass
- 未降低 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**` 的阻断

## Blocking Self-Test Results

运行结果：

- `node --check scripts/guard_harness_diff.js`：pass
- `node --check scripts/guard_trading_surface.js`：pass
- `.\scripts\run_agent_readiness_checks.ps1`：pass
- 临时 `scripts/build_v1129_snapshot_insufficient_report.js`：guard allowed
- 临时 `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json`：guard allowed
- 临时 `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md`：guard allowed
- 临时 `reports/v1129_execution_validation/v1129_real_execution_report.json`：guard blocked
- 临时 `reports/v1129_execution_validation/snapshots/should_not_commit.sqlite`：Git ignored / not a commit target
- 临时 `strategies/RegimeAwareV1129GuardSelfTest.py`：guard blocked
- 临时 `user_data/config_multi_futures_v1129_guard_selftest.json`：guard blocked
- 所有临时文件已清理

## Boundary Confirmation

- 未修改策略
- 未修改 bot 配置
- 未修改 dashboard
- 未修改 deploy
- 未修改 SQLite snapshot
- 未读取 secret
- 未登录服务器
- 未启动、停止或重启 bot
- 未运行回测
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 18

## Verification

最终运行：

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git status --short --untracked-files=all
```

最终 Git 可见变更只包含本 Task 18R 授权文件。
