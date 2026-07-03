# Task 7S: Approved Docs Migration

结论：已根据 `reports/audits/task7r_blocked_docs_review.md` 迁移 Task 7R 明确建议迁移的 4 个 `docs/*` 文件，并在 `scripts/guard_harness_diff.js` 中加入 4 个精确路径白名单。未使用 `docs/**`、`docs/*.md` 或 `docs/*.html` 泛化规则。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 7R commit：`486df3d Review blocked A-class docs`
- 白名单来源：`reports/audits/task7r_blocked_docs_review.md`
- 原始工作区：`D:\code\freqtrade-strategies`

前置 gate：

```text
git status --short
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

## 2. Task 7R 批准迁移的 4 个 docs 路径

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`

## 3. 实际迁移路径

| 文件 | 来源路径 | 目标路径 |
|---|---|---|
| `docs/agent_operating_playbook.md` | `D:\code\freqtrade-strategies\docs\agent_operating_playbook.md` | `D:\code\freqtrade-strategies-clean\docs\agent_operating_playbook.md` |
| `docs/agent_operating_playbook.html` | `D:\code\freqtrade-strategies\docs\agent_operating_playbook.html` | `D:\code\freqtrade-strategies-clean\docs\agent_operating_playbook.html` |
| `docs/opensource_reference_audit.md` | `D:\code\freqtrade-strategies\docs\opensource_reference_audit.md` | `D:\code\freqtrade-strategies-clean\docs\opensource_reference_audit.md` |
| `docs/验收报告格式.md` | `D:\code\freqtrade-strategies\docs\验收报告格式.md` | `D:\code\freqtrade-strategies-clean\docs\验收报告格式.md` |

## 4. `guard_harness_diff.js` 新增的精确白名单

新增低风险路径仅限：

```js
{ path: "docs/agent_operating_playbook.md" },
{ path: "docs/agent_operating_playbook.html" },
{ path: "docs/opensource_reference_audit.md" },
{ path: "docs/\u9a8c\u6536\u62a5\u544a\u683c\u5f0f.md" },
```

同时将 guard 内部 Git 路径输出固定为 `core.quotepath=false`，用于确保中文路径按真实精确路径匹配，而不是按 Git quoted octal 输出误判。该调整不扩大允许面。

## 5. 没有使用 `docs/**`

本任务没有使用以下泛化规则：

- 未使用 `docs/**`
- 未使用 `docs/*.md`
- 未使用 `docs/*.html`
- 未允许 `docs/superpowers/plans/**`
- 未允许 `docs/superpowers/specs/**`

`docs/harness/change_surface_matrix.md` 已记录 Task 7S 只允许 4 个精确 docs 路径。

## 6. Readiness check 结果

迁移和 guard 更新后预检结果：

```text
guard_harness_diff: pass (6 changed path(s) checked)
guard_no_secret_material: pass (6 changed path(s) checked)
guard_trading_surface: pass (6 changed path(s) checked)
```

最终验证命令：

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

最终 readiness 结果：

```text
guard_harness_diff: pass (8 changed path(s) checked)
guard_no_secret_material: pass (8 changed path(s) checked)
guard_trading_surface: pass (8 changed path(s) checked)
```

最终 `git diff --name-only`：

```text
docs/harness/change_surface_matrix.md
scripts/guard_harness_diff.js
```

最终 `git status --short --untracked-files=all` 预期只包含：

```text
 M docs/harness/change_surface_matrix.md
 M scripts/guard_harness_diff.js
?? docs/agent_operating_playbook.html
?? docs/agent_operating_playbook.md
?? docs/opensource_reference_audit.md
?? docs/验收报告格式.md
?? reports/audits/task7s_approved_docs_migration.md
?? tasks/active/TASK-0007S-approved-docs-migration.md
```

## 7. 是否触碰禁止路径

未触碰禁止路径：

- 未修改 `strategies/**`
- 未修改 `user_data/**`
- 未修改 `configs/**`
- 未修改 `dashboard/**`
- 未修改 `deploy/**`
- 未修改 `.env`
- 未修改 `user_data/monitor.env`
- 未读取 API key、交易所凭证、服务器密钥或 dashboard 密码
- 未触碰 V10.8.2
- 未触碰 V11.29
- 未触碰 live/server 操作面
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`

执行边界：

- 未删除原始工作区文件
- 未移动原始工作区文件
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略或 bot 配置
- 未进入 Task 8

## 8. 后续 Task 8 推荐

推荐 Task 8：在 clean worktree 中整理已迁移 A 类文档的索引或阅读入口，只引用当前已迁移并通过 guard 的文档。Task 8 不应扩大 docs 允许面，不应迁移 Task 7R 暂缓、人工复核或禁止迁移的文件。
