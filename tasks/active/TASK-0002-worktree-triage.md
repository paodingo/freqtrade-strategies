# TASK-0002 Worktree Triage / Evidence Quarantine Plan

状态：完成计划，未执行清理。

当前工作区：

- 执行目录：`D:\code\freqtrade-strategies-harness`
- 原始工作区：`D:\code\freqtrade-strategies`

## 目标

为原始脏工作区制定安全分流方案，但不清理、不删除、不移动、不 stash、不 commit 原始工作区中的任何文件。

## 只读证据

已运行：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all
git -C D:\code\freqtrade-strategies diff --name-only
git -C D:\code\freqtrade-strategies diff --stat
git -C D:\code\freqtrade-strategies ls-files --others --exclude-standard
```

摘要：

- `diff --name-only` 显示 27 个 tracked modified 文件。
- `diff --stat` 显示 `27 files changed, 7297 insertions(+), 208 deletions(-)`。
- untracked 输出很大，包含文档、`btc_system/**`、`reports/**`、`scripts/**`、`strategies/**`、`tests/**`、`user_data/**`、`output/**` 和临时分析目录。

## 已生成文件

- `reports/audits/worktree_triage_plan.md`
- `tasks/active/TASK-0002-worktree-triage.md`

## 本任务未执行的动作

- 未修改 `D:\code\freqtrade-strategies`。
- 未删除、移动、stash、commit 原始工作区文件。
- 未读取 `.env`、`user_data/monitor.env`、API key、交易所凭证或服务器密钥。
- 未启动、停止、重启 bot。
- 未登录服务器。
- 未运行回测。
- 未修改策略、bot 配置、V10.8.2 或 V11.29。

## 后续建议

Task 3 建议只做 `.gitignore` 草案与 A 类文档提交白名单审查；不要把策略、bot 配置、V10.8.2、V11.29、live/server 操作面纳入同一任务。
