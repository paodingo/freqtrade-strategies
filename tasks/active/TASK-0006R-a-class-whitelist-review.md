# TASK-0006R: Review A-Class Migration Whitelist

状态：已完成审查，未执行复制。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

审查 `reports/audits/task6_a_class_documentation_migration_plan.md` 中的 A 类迁移白名单，确认 Task 7 可以实际迁移的文件，以及必须暂缓、人工复核或禁止迁移的文件。

## 前置条件结果

- Task 6：通过，commit `9b29b11 Add A-class documentation migration plan`
- `git status --short`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 审查来源

- `reports/audits/task6_a_class_documentation_migration_plan.md`

## 输出

- `reports/audits/task6r_a_class_whitelist_review.md`

## Task 7 复制白名单

Task 7 只允许复制：

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`
- `reports/audits/git_worktree_inventory.md`
- `reports/audits/harness_readiness_audit.md`

## 本任务允许修改

- `reports/audits/task6r_a_class_whitelist_review.md`
- `tasks/active/TASK-0006R-a-class-whitelist-review.md`

## 本任务未执行

- 未复制任何文件
- 未移动任何文件
- 未删除任何文件
- 未 commit 原始工作区
- 未读取 secret
- 未修改 `D:\code\freqtrade-strategies` 中的任何文件
- 未修改 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`
- 未触碰 `.env`、`user_data/monitor.env`
- 未触碰 V10.8.2、V11.29、live/server 操作面
- 未触碰 API key、交易所凭证、服务器密钥、dashboard 密码

## 禁止

Task 7 仍然禁止：

```powershell
git add -A
git add .
```

不要在 Task 6R 中进入 Task 7。
