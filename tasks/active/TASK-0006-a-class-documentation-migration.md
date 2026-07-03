# TASK-0006: A-Class Documentation Migration Plan

状态：已完成计划，未执行复制。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

从原始脏工作区 `D:\code\freqtrade-strategies` 中只读识别 A 类文档、harness、审计、任务基线候选，生成迁移计划和显式白名单。

## 前置条件结果

- 当前目录：通过，位于 `D:\code\freqtrade-strategies-clean`
- 当前分支：通过，位于 `codex/btc-mvp-system-harnessed`
- Task 5：通过，commit `3730ba0 Establish clean harnessed development base`
- `git status --short`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 只读检查范围

已只读检查原始工作区：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
git -C D:\code\freqtrade-strategies diff --name-only -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
```

## 输出

- `reports/audits/task6_a_class_documentation_migration_plan.md`

## 本任务允许修改

- `reports/audits/task6_a_class_documentation_migration_plan.md`
- `tasks/active/TASK-0006-a-class-documentation-migration.md`

## 本任务未执行

- 未复制 `D:\code\freqtrade-strategies` 中的任何文件
- 未提交
- 未清理原始脏工作区
- 未修改 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`
- 未读取或修改 `.env`、`user_data/monitor.env`
- 未触碰 API key、交易所凭证、服务器密钥、dashboard 密码
- 未触碰 V10.8.2、V11.29、live/server 操作面

## 下一步

推荐 Task 7：只复制 Task 6 报告中 `$CopyWhitelist` 的第一批低风险 A 类文档，并继续使用显式 `Copy-Item -LiteralPath` 与显式 `git add -- <paths>` 白名单。不要在 Task 6 中进入 Task 7。
