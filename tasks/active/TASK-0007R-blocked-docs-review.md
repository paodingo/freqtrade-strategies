# TASK-0007R: Review Blocked A-Class Docs and Safe Docs Surface

状态：已完成，未进入 Task 7S 或 Task 8。

执行目录：`D:\code\freqtrade-strategies-clean`

## 目标

复核 Task 7 中被 `guard_harness_diff` 阻断的 4 个 `docs/*` A 类候选文件，判断是否应该迁移，以及是否需要对 docs 安全白名单做更窄扩展。

## 前置条件结果

- Task 7 已 commit：`77cfdeb Migrate approved audit documentation`
- `git status --short`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 只读来源

- `reports/audits/task6r_a_class_whitelist_review.md`
- `reports/audits/task7_a_class_documentation_migration_result.md`
- `tasks/active/TASK-0007-a-class-documentation-migration.md`

## 复核结论

Task 7 被阻断的 4 个文件为：

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`

阻断原因：Task 7 报告显示 `guard_harness_diff` 当前只允许 `docs/harness/**`，上述普通 `docs/*` 路径不是已授权低风险 harness/documentation surface。

建议动作：4 个文件均可进入后续 Task 7S，但必须先以精确文件路径扩展 guard，再迁移；不得建议或实现 `docs/**`。

## 推荐后续任务

推荐 Task 7S：只针对以下精确路径扩展 guard 白名单并迁移文件：

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`

Task 7S 不应进入 Task 8。

## 本任务未执行

- 未复制任何文件
- 未迁移任何 docs 文件
- 未修改 `scripts/guard_harness_diff.js`
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略或 bot 配置
- 未修改原始工作区 `D:\code\freqtrade-strategies`

## 输出

- `reports/audits/task7r_blocked_docs_review.md`
- `tasks/active/TASK-0007R-blocked-docs-review.md`

