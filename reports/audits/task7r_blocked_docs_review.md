# Task 7R: Blocked A-Class Docs Review

结论：Task 7 中被阻断的 4 个 `docs/*` 文件建议进入后续 Task 7S，但必须先以精确文件路径扩展 `guard_harness_diff.js` 的 docs 安全白名单，再迁移文件。不要放开 `docs/**`，不要迁移其他 docs 目录或版本化策略文档。

## 1. 执行边界

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 最新 Task 7 commit：`77cfdeb Migrate approved audit documentation`
- 本任务只读查看：
  - `reports/audits/task6r_a_class_whitelist_review.md`
  - `reports/audits/task7_a_class_documentation_migration_result.md`
  - `tasks/active/TASK-0007-a-class-documentation-migration.md`
- 本任务未复制 docs 文件，未迁移 docs 文件，未修改 guard，未读取 secret，未启动 bot，未登录服务器，未运行回测，未修改策略或 bot 配置。

## 2. Task 7 被 guard 阻断的 4 个 docs 文件

| 文件路径 | Task 6R 分类 | Task 7 阻断原因 | 建议动作 |
|---|---|---|---|
| `docs/agent_operating_playbook.md` | 可以迁移 | `guard_harness_diff` 当前只允许 `docs/harness/**`，不允许普通 `docs/*` 路径；Task 7 预检报告显示该路径会被判为未授权低风险文档面。 | 可以迁移 |
| `docs/agent_operating_playbook.html` | 可以迁移 | 同上。该文件是 `docs/agent_operating_playbook.md` 的 HTML 阅读版，但普通 `docs/*` 路径仍未在 guard 允许面内。 | 可以迁移 |
| `docs/opensource_reference_audit.md` | 可以迁移 | 同上。虽然 Task 6R 把它列为开源参考审计文档候选，但 guard 当前未允许该精确路径。 | 可以迁移 |
| `docs/验收报告格式.md` | 可以迁移 | 同上。Task 7 报告说明中文路径也被同一 guard 规则阻断，PowerShell/Git 输出中可能显示为 quoted path。 | 可以迁移 |

## 3. 为什么不是直接迁移

Task 7 的失败点不是文档内容审查失败，而是 guard 允许面与 Task 6R 白名单不一致：

- Task 6R 已把上述 4 个文件列入 Task 7 复制白名单；
- Task 7 实际复制预检时，`guard_harness_diff` 只允许 `docs/harness/**`；
- 上述 4 个文件都位于普通 `docs/*`；
- 为保持 clean worktree readiness 通过，Task 7 已撤回这些 docs 文件，只保留 guard 当时允许的 `reports/audits/**` 审计基线迁移。

因此，后续不应绕过 guard，也不应手工复制后强行提交；应先用一个更窄的 guard 白名单任务把允许面修正到 Task 6R 已批准的精确文件集合。

## 4. 是否建议扩展 docs 安全白名单

建议扩展，但只能扩展以下精确文件路径：

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`

不建议允许：

- `docs/**`
- `docs/*.md`
- `docs/*.html`
- `docs/superpowers/plans/**`
- `docs/superpowers/specs/**`
- 任何涉及 live/server rollout、策略版本、bot 配置、回测产物、dashboard、deploy 或 secret-adjacent 内容的路径。

## 5. Task 7S 推荐

推荐新开 Task 7S：只针对上述 4 个已批准 docs 文件进行 guard 白名单扩展和迁移。

Task 7S 建议边界：

- 允许修改 `scripts/guard_harness_diff.js`，但只加入上述 4 个精确路径；
- 允许迁移上述 4 个 docs 文件；
- 允许新增或更新针对 guard 白名单的静态测试；
- 禁止扩大到 `docs/**`；
- 禁止进入 Task 8；
- 完成后必须运行 readiness checks，并确保最终 diff 只包含 Task 7S 明确允许的文件。

## 6. 本任务停止点

Task 7R 只产出复核报告和任务记录，不进入 Task 7S 或 Task 8。

