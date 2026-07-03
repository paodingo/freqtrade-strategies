# Task 20D: Repository Documentation Currency Audit

状态：已完成。仅做只读文档时效审计，未修改 `README.md`、`DEPLOY.md`、`LIVE_TRADING.md`、`STRATEGY_GUIDE.md`。

## Summary

当前 harness 基座已经可承载后续 clean worktree 开发，但仓库入口文档明显滞后。`README.md`、`DEPLOY.md`、`LIVE_TRADING.md`、`STRATEGY_GUIDE.md` 仍把 `V6.5` / `V6.6` 描述为当前主线或运行对象，而当前实际工作流已经进入 `V11.29` 真实执行验证链路，并且 Task 17 / 18 / 19 已确认 V11.29 当前状态为 `insufficient`，不是已通过验证的替代版本。

本任务没有修改任何文档正文，只生成文档时效审计和后续白名单修正文案建议。

## Current repository state

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 进入任务前 `git status --short --untracked-files=all`：empty
- 进入任务前 readiness：pass
- 当前阶段事实来源：
  - Task 10：harness migration 基座完成，原始脏工作区继续 quarantine-only。
  - Task 17：V11.29 SQLite snapshot `trades = 0`、`orders = 0`。
  - Task 18：生成 V11.29 snapshot-based `insufficient` execution report。
  - Task 19：只读调查 V11.29 zero-trade 原因，建议后续做 signal/data availability audit。

## Stale entry documents

| File | Current stale content | Risk | Recommended action |
|---|---|---|---|
| `README.md` | 把当前重点写成 `V6.5` / `V6.6` dry-run 对比；表格列出 `RegimeAwareV65`、`RegimeAwareV66`、端口 `8081` / `8082`；命令注释写“启动当前 V6.5 dry-run bot”。 | 高：入口文档误导当前主线和运行状态。 | 可自动修正文档叙事，但不能声称 V11.29 已通过验证。应改为：当前 clean harness 主线是 V11.29 真实执行验证准备，V11.29 当前为 `insufficient`。V6.5/V6.6 移到历史/旧文档段落。 |
| `DEPLOY.md` | 把当前云端主对比写成 `V6.5` / `V6.6`；包含 `freqtrade-v65` / `freqtrade-v66` 容器、`RegimeAwareV65` / `RegimeAwareV66` 策略、端口 `8081` / `8082`、stop/rm/start 命令、dashboard env 示例。 | 很高：包含部署/运行命令和 server 操作面，若直接改成 V11.29 可能误导真实操作。 | 先人工确认目标：是废弃旧部署手册、标记为 historical，还是另建 V11.29 只读验证手册。禁止直接替换为可执行 V11.29 deploy 命令。 |
| `LIVE_TRADING.md` | 仍写 `V6.3` / `V6.5` dry-run 观察，模板和示例围绕旧 live config / `RegimeAwareV63`。 | 很高：live 相关文档，涉及真实交易边界。 | 标记为 historical / not current，或拆成“live readiness principles”。任何 V11.29 live 相关内容必须另起人工确认任务，不能自动生成 live 启动指令。 |
| `STRATEGY_GUIDE.md` | 当前目标仍描述 `V6.5` / `V6.6` 双 bot 对比，策略差异表和观察指标围绕旧版本。 | 中高：策略叙事滞后，但不直接启动 bot。 | 可自动修为“历史策略指南”，并增加当前 V11.29 状态引用；不评价 V11.29 替换能力。 |
| `docs/backtests/2026-06-11-v66-alpha-risk-backtest.md` | 历史 V6.6 backtest 文档。 | 低：文件名和内容均是历史回测记录。 | 保留，不需要更新为当前状态，只可加历史说明索引。 |

## Confirmed stale patterns

只读扫描确认：

```text
README.md: current focus still says V6.5 / V6.6
README.md: current running table still uses RegimeAwareV65 / RegimeAwareV66 / 8081 / 8082
DEPLOY.md: current deployment manual still uses V6.5 / V6.6 containers and commands
DEPLOY.md: dashboard env example still uses BOT_V65_* / BOT_V66_*
LIVE_TRADING.md: live readiness still references V6.3 / V6.5
STRATEGY_GUIDE.md: current target still describes V6.5 / V6.6 comparison
```

## Documentation truth model

建议后续统一文档口径：

- `Current harness state`: clean worktree + readiness guards + quarantine policy are operational.
- `Current validation state`: V11.29 is under real-execution validation, but current evidence is `insufficient`.
- `Current execution evidence`: V11.29 server DB has `trades = 0` and `orders = 0`; V10.8.2 has limited benchmark rows but no same-window V11.29 comparison.
- `Current next work`: Task 20 should audit V11.29 data coverage and runtime performance before any repair or replacement decision.
- `Historical versions`: V6.5 / V6.6 / V6.3 should be clearly labeled as historical docs unless a future task proves they are current operational targets.

## Files that can be updated automatically later

These can be updated in a narrow docs-only task, provided the task explicitly allows them:

- `README.md`
- `STRATEGY_GUIDE.md`

Allowed content style:

- Replace “current V6.5/V6.6” language with “historical V6.5/V6.6”.
- Add a concise current-state section pointing to V11.29 `insufficient` validation reports.
- Add a warning that V11.29 has not passed real execution validation and cannot be considered a replacement yet.

## Files requiring manual confirmation before edits

These should not be auto-edited without a separate task and explicit scope:

- `DEPLOY.md`
- `LIVE_TRADING.md`

Reason:

- They contain live/server/deploy commands, bot lifecycle commands, API examples, env examples, and operational assumptions.
- Rewriting them to V11.29 could accidentally create a plausible but unverified runbook.
- If updated, they should first be converted to “historical/deprecated” or split into a new `docs/harness` or audit-only V11.29 verification runbook.

## Explicitly forbidden for automatic docs sync

Future docs sync must not:

- modify `strategies/**`
- modify `user_data/**`
- modify `configs/**`
- modify `dashboard/**`
- modify `deploy/**`
- read `.env` or `user_data/monitor.env`
- add or expose API keys, exchange credentials, server keys, dashboard passwords, or tokens
- generate V11.29 live/deploy/start/stop/restart instructions without explicit human approval
- claim V11.29 passed real execution validation
- claim V11.29 can replace V10.8.2

## Recommended next documentation tasks

1. Task 20E: `README and Strategy Guide Current-State Refresh`
   - Allowed files: `README.md`, `STRATEGY_GUIDE.md`, audit/task record.
   - Goal: remove stale “current V6.5/V6.6” language and point to current V11.29 `insufficient` validation state.

2. Task 20F: `Deploy and Live Docs Historical Freeze Plan`
   - Allowed files initially: audit/task record only.
   - Goal: decide whether `DEPLOY.md` / `LIVE_TRADING.md` should be marked historical, split, or rewritten under manual approval.

3. Task 20: `V11.29 Data Coverage and Runtime Performance Audit`
   - Remains the main technical next task for the V11.29 zero-trade branch.

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task20d_repository_documentation_currency_audit.md
tasks/active/TASK-0020D-repository-documentation-currency-audit.md
```
