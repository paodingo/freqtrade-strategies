# TASK-0007: Execute A-Class Documentation Migration

状态：已完成部分迁移，未进入 Task 8。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只从原始工作区 `D:\code\freqtrade-strategies` 迁移 Task 6R 明确批准的 A 类文档、harness、审计、任务基线文件到当前 clean worktree。

## 前置条件结果

- Task 6R：通过，commit `11f8734 Review A-class documentation migration whitelist`
- `git status --short`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过
- 已先读取 `reports/audits/task6r_a_class_whitelist_review.md`

## 实际迁移

已迁移：

- `reports/audits/git_worktree_inventory.md`
- `reports/audits/harness_readiness_audit.md`

未迁移：

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`

未迁移原因：当前 `scripts/guard_harness_diff.js` 只允许 `docs/harness/**`，上述普通 `docs/*` 路径会导致 readiness 失败。复制预检发现该冲突后，已从 clean worktree 撤回这些文件。

## 本任务未执行

- 未删除原始工作区文件
- 未移动原始工作区文件
- 未 stash
- 未 commit 原始工作区
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未扩大 Task 6R 白名单
- 未使用 `git add -A`
- 未使用 `git add .`

## 输出

- `reports/audits/task7_a_class_documentation_migration_result.md`

## 下一步

推荐 Task 8：处理 Task 6R 白名单和 `guard_harness_diff` 文档允许面之间的不一致。不要在 Task 7 中进入 Task 8。
