# Task 7: A-Class Documentation Migration Result

结论：本任务只从 Task 6R 明确批准的白名单中迁移了当前 harness guard 允许的 A 类审计基线文件。Task 6R 白名单中的 4 个 `docs/*` 文件在复制预检后触发 `guard_harness_diff` 阻断；为保持 clean worktree readiness 通过，这 4 个文件已从当前 clean worktree 撤回，未作为本任务最终迁移结果保留。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 6R commit：`11f8734 Review A-class documentation migration whitelist`
- 白名单来源：`reports/audits/task6r_a_class_whitelist_review.md`
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

## 2. 实际迁移文件清单

| 文件 | 来源路径 | 目标路径 | 结果 |
|---|---|---|---|
| `reports/audits/git_worktree_inventory.md` | `D:\code\freqtrade-strategies\reports\audits\git_worktree_inventory.md` | `D:\code\freqtrade-strategies-clean\reports\audits\git_worktree_inventory.md` | 已迁移 |
| `reports/audits/harness_readiness_audit.md` | `D:\code\freqtrade-strategies\reports\audits\harness_readiness_audit.md` | `D:\code\freqtrade-strategies-clean\reports\audits\harness_readiness_audit.md` | 已迁移 |

## 3. 未迁移文件及原因

以下文件属于 Task 6R 白名单，但当前 `scripts/guard_harness_diff.js` 只允许 `docs/harness/**`，不允许普通 `docs/*` 路径。复制后预检输出显示这些路径会导致 readiness 失败，因此已从 clean worktree 撤回，未作为最终迁移结果保留。

| 文件 | 来源路径 | 目标路径 | 未迁移原因 |
|---|---|---|---|
| `docs/agent_operating_playbook.md` | `D:\code\freqtrade-strategies\docs\agent_operating_playbook.md` | `D:\code\freqtrade-strategies-clean\docs\agent_operating_playbook.md` | `guard_harness_diff` 当前不允许 `docs/*` |
| `docs/agent_operating_playbook.html` | `D:\code\freqtrade-strategies\docs\agent_operating_playbook.html` | `D:\code\freqtrade-strategies-clean\docs\agent_operating_playbook.html` | `guard_harness_diff` 当前不允许 `docs/*` |
| `docs/opensource_reference_audit.md` | `D:\code\freqtrade-strategies\docs\opensource_reference_audit.md` | `D:\code\freqtrade-strategies-clean\docs\opensource_reference_audit.md` | `guard_harness_diff` 当前不允许 `docs/*` |
| `docs/验收报告格式.md` | `D:\code\freqtrade-strategies\docs\验收报告格式.md` | `D:\code\freqtrade-strategies-clean\docs\验收报告格式.md` | `guard_harness_diff` 当前不允许 `docs/*` |

触发的 readiness 预检要点：

```text
guard_harness_diff: blocked high-risk diff
- docs/agent_operating_playbook.html: path is not an authorized low-risk harness/documentation surface
- docs/agent_operating_playbook.md: path is not an authorized low-risk harness/documentation surface
- docs/opensource_reference_audit.md: path is not an authorized low-risk harness/documentation surface
```

中文路径 `docs/验收报告格式.md` 也被同一 guard 规则阻断，PowerShell/Git 输出中显示为 quoted path。

## 4. 是否触碰禁止路径

未触碰禁止路径：

- 未修改 `strategies/**`
- 未修改 `user_data/**`
- 未修改 `configs/**`
- 未修改 `dashboard/**`
- 未修改 `deploy/**`
- 未修改 bot lifecycle 或 server/trade monitor 脚本
- 未修改 `reports/btc_mvp/backtests/**`
- 未修改 `reports/reliable_strategy_search_*/**`
- 未修改 `reports/api_gap_backtest_candidates/**`
- 未修改 `output/**`
- 未修改 `.tmp_*/**`
- 未修改 `.env`
- 未修改 `user_data/monitor.env`
- 未触碰 V10.8.2、V11.29、live/server 操作面

## 5. 是否读取 secret

未读取 secret。未访问 `.env`、`user_data/monitor.env`、API key、交易所凭证、服务器密钥或 dashboard 密码。

## 6. 验证结果

最终验证命令：

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

最终 readiness 结果：

```text
guard_harness_diff: pass (4 changed path(s) checked)
guard_no_secret_material: pass (4 changed path(s) checked)
guard_trading_surface: pass (4 changed path(s) checked)
```

最终预期变更面：

- `reports/audits/git_worktree_inventory.md`
- `reports/audits/harness_readiness_audit.md`
- `reports/audits/task7_a_class_documentation_migration_result.md`
- `tasks/active/TASK-0007-a-class-documentation-migration.md`

## 7. 后续 Task 8 推荐

推荐 Task 8：修正 A 类文档迁移策略与 guard 规则之间的不一致。建议二选一：

- 保守路径：只允许后续迁移 `reports/audits/**` 和 `docs/harness/**`，把普通 `docs/*` 继续保留为人工阅读候选。
- 扩展路径：另开 guard 变更任务，显式允许一小组经过审查的普通 `docs/*` 文件，并加入对应 readiness 验证。

Task 8 不应自动复制剩余 4 个 `docs/*` 文件，除非先解决 `guard_harness_diff` 允许面与 Task 6R 白名单的冲突。
