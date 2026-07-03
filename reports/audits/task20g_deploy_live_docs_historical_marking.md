# Task 20G: Deploy and Live Docs Historical Marking

状态：已完成。仅在 `DEPLOY.md` 和 `LIVE_TRADING.md` 顶部加入 historical / not-current warning，并增加精确根文档 guard 例外。

## Summary

本任务执行 Task 20F 的最小冻结方案：保留旧文档内容用于历史审计，但在顶部明确标注它们不是当前 V11.29 操作手册。

本任务没有新增 V11.29 deploy、start、stop、restart、live 或 server 操作指令，也没有删除旧命令。

## Files changed

- `DEPLOY.md`
- `LIVE_TRADING.md`
- `scripts/guard_harness_diff.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task20g_deploy_live_docs_historical_marking.md`
- `tasks/active/TASK-0020G-deploy-live-docs-historical-marking.md`

## DEPLOY.md marking

已在顶部加入 warning，说明：

- 该文档是旧 V6.x dry-run 部署记录。
- 该文档不是当前 V11.29 操作手册。
- 不应依据该文档启动、停止、重启、部署或操作 V11.29 bot。
- V11.29 当前真实执行验证仍为 `insufficient`。
- V11.29 deploy/live/server 操作需要单独人工授权任务。

## LIVE_TRADING.md marking

已在顶部加入 warning，说明：

- 该文档是旧 V6.x live readiness 记录。
- 该文档不是当前 V11.29 实盘或部署手册。
- 不应依据该文档启动实盘、启动 V11.29、修改 live config 或执行 server 操作。
- V11.29 当前真实执行验证仍为 `insufficient`。
- V11.29 live/server 操作需要单独人工授权任务。

## Guard update

`scripts/guard_harness_diff.js` 增加两个精确根文档例外：

```text
DEPLOY.md
LIVE_TRADING.md
```

这不是通配规则，不允许：

```text
deploy/**
strategies/**
user_data/**
configs/**
dashboard/**
scripts/start_bot.sh
scripts/ensure_dry_run_bots_started.sh
scripts/refresh_data.sh
scripts/check_system_health.sh
scripts/check_trades.sh
```

## What was not changed

本任务没有：

- 修改 `strategies/**`
- 修改 `user_data/**`
- 修改 `configs/**`
- 修改 `dashboard/**`
- 修改 `deploy/**`
- 修改 bot lifecycle scripts
- 读取 `.env`
- 读取 `user_data/monitor.env`
- 读取或暴露 API key、交易所凭证、server key、dashboard 密码
- 登录服务器
- 启动、停止、重启 bot
- 运行回测
- 声称 V11.29 已通过真实执行验证
- 声称 V11.29 可以替换 V10.8.2

## When to rewrite these docs

`DEPLOY.md` / `LIVE_TRADING.md` 早晚需要重写，但不应现在直接改成 V11.29 runbook。推荐时机：

1. Task 20 完成 V11.29 data coverage and runtime performance audit。
2. Task 21 / Task 22 完成必要的数据补齐计划或性能瓶颈审计。
3. Task 23 重新观察并确认是否产生真实 trades/orders。
4. 如果 V11.29 有足够真实执行样本，再做只读验证 runbook。
5. 只有在人工明确授权后，才生成新的 deploy/live 操作手册。

## Recommended next task

推荐回到技术主线：

```text
Task 20: V11.29 Data Coverage and Runtime Performance Audit
```

该任务应继续调查 V11.29 zero-trade 的数据覆盖、4h informative data、策略分析耗时、信号链路和 runtime warning。

## Verification

最终验证命令：

```powershell
node --check scripts/guard_harness_diff.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

预期最终可见变更：

```text
DEPLOY.md
LIVE_TRADING.md
scripts/guard_harness_diff.js
docs/harness/change_surface_matrix.md
reports/audits/task20g_deploy_live_docs_historical_marking.md
tasks/active/TASK-0020G-deploy-live-docs-historical-marking.md
```
