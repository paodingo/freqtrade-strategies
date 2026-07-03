# Task 20F: Deploy and Live Docs Historical Freeze Plan

状态：已完成。只生成 `DEPLOY.md` / `LIVE_TRADING.md` 的 historical freeze 计划，未修改这两个高风险文档正文。

## Summary

`DEPLOY.md` 和 `LIVE_TRADING.md` 仍包含旧版本 dry-run、deploy、live readiness 和 bot lifecycle 示例。它们不能再被当作当前 V11.29 操作手册，也不能直接替换成 V11.29 可执行部署或 live 指令。

推荐做法是先将两份文档明确冻结为 historical / not-current，再另建只读验证 runbook。任何 V11.29 deploy、start、stop、restart、live 或 server 操作步骤，都必须另起人工授权任务。

## Current repository state

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 进入任务前 `git status --short --untracked-files=all`：empty
- 进入任务前 readiness：pass
- Task 20D 已提交：文档时效审计
- Task 20E 已提交：`README.md` / `STRATEGY_GUIDE.md` 当前状态刷新

## Read-only findings

### DEPLOY.md

`DEPLOY.md` 当前仍写作“当前 dry-run 部署的标准手册”，并包含：

- 服务器、用户、SSH key 路径、仓库路径等 server 操作面信息。
- `freqtrade-v65` / `freqtrade-v66` 容器和 `8081` / `8082` API 端口。
- `RegimeAwareV65` / `RegimeAwareV66` 策略名。
- `docker stop` / `docker rm` / `docker run` / `curl /api/v1/start` 示例。
- `user_data/monitor.env` 创建示例和 dashboard credential placeholder。
- health check、trade alert、rollback 示例。

风险：该文档包含可复制执行的部署和 bot lifecycle 命令。如果直接改写为 V11.29，可能制造未经验证的 V11.29 运行手册。

### LIVE_TRADING.md

`LIVE_TRADING.md` 当前仍围绕 V6.3 / V6.5 live readiness，并包含：

- live API key 环境变量示例。
- `dry_run=false` 参数示例。
- `preflight_live.sh` 示例。
- `docker run ... trade` live container 示例。
- `/api/v1/start`、`/api/v1/stopentry`、`docker stop` 应急命令。

风险：这是 live 操作面文档，涉及真实交易边界。它不能自动改写成 V11.29 live 指南，也不能在当前证据不足时暗示 V11.29 进入实盘准备。

## Recommended freeze model

### Option A: Historical freeze banner

在两份文档开头加入明显警示：

```text
Historical document. Not current V11.29 operating guidance.
Do not use this document to start, stop, restart, deploy, or operate V11.29 bots.
```

适用场景：希望最小化改动，保留旧命令用于历史审计。

### Option B: Move current-safe content to docs/harness

保留 `DEPLOY.md` / `LIVE_TRADING.md` 为 historical，并新建只读验证文档，例如：

```text
docs/harness/v1129_readonly_execution_validation_runbook.md
```

该 runbook 只允许包含：

- read-only evidence checks
- SQLite snapshot inspection
- log review boundaries
- data coverage audit steps
- prohibited operations

不允许包含：

- `docker start`
- `docker stop`
- `docker restart`
- `freqtrade trade`
- live config write steps
- API keys or credential handling beyond generic warnings

### Option C: Split deploy/live docs after manual approval

人工确认后，将旧文档拆成：

- historical V6 deploy record
- general live safety principles
- V11.29 read-only validation runbook
- future live deployment checklist, only after V11.29 has sufficient real execution evidence

这是最干净但改动最大的方案。

## Recommended next action

推荐下一步执行 `Task 20G: Mark Deploy and Live Docs as Historical`。

允许文件：

- `DEPLOY.md`
- `LIVE_TRADING.md`
- `reports/audits/task20g_deploy_live_docs_historical_marking.md`
- `tasks/active/TASK-0020G-deploy-live-docs-historical-marking.md`

目标：

- 仅在 `DEPLOY.md` / `LIVE_TRADING.md` 顶部加入 historical / not-current warning。
- 不删除旧命令。
- 不新增 V11.29 deploy/live/start/stop/restart 指令。
- 不修改策略、配置、dashboard、deploy、secret 或 server。

## Forbidden automatic changes

后续自动文档同步不得：

- 将 V6.5 / V6.6 命令直接替换为 V11.29 命令。
- 添加 V11.29 `docker run trade` 示例。
- 添加 V11.29 start/stop/restart 命令。
- 添加 live V11.29 配置模板。
- 读取或写入 `.env`、`user_data/monitor.env`、API key、交易所凭证、server key、dashboard 密码。
- 修改 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`。
- 声称 V11.29 已通过真实执行验证。
- 声称 V11.29 可以替换 V10.8.2。

## Technical track remains separate

文档冻结不替代技术调查。V11.29 zero-trade 分支仍应继续：

1. Task 20: `V11.29 Data Coverage and Runtime Performance Audit`
2. Task 21: 如果确认 4h 数据缺失，制定安全补数据计划
3. Task 22: 如果确认分析耗时过长，做性能瓶颈审计
4. Task 23: 重新观察 V11.29 是否产生真实 trades/orders

## Verification

最终验证命令：

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

预期最终可见变更：

```text
reports/audits/task20f_deploy_live_docs_historical_freeze_plan.md
tasks/active/TASK-0020F-deploy-live-docs-historical-freeze-plan.md
```
