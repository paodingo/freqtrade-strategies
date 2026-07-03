# Task 6R: A-Class Migration Whitelist Review

结论：Task 7 只允许迁移 Task 6 计划中已列入低风险 `$CopyWhitelist` 的 6 个路径。其余候选必须暂缓、人工阅读后决定，或禁止迁移。本任务未复制、未移动、未删除任何文件，未修改原始工作区 `D:\code\freqtrade-strategies`。

## 1. 审查基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 6 commit：`9b29b11 Add A-class documentation migration plan`
- 审查来源：`reports/audits/task6_a_class_documentation_migration_plan.md`

前置 gate：

```text
git status --short
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

## 2. 审查原则

- Task 7 只迁移低风险 A 类文档、harness 说明、审计基线。
- 不复制策略、bot 配置、runtime 数据、dashboard、deploy、回测产物、报告原始数据、secret、V10.8.2、V11.29、live/server 操作面。
- 不直接覆盖 clean worktree 中已有的根文档。
- 不把 `docs/superpowers/plans/**` 或 `docs/superpowers/specs/**` 放入 Task 7 自动迁移白名单。
- 原始工作区只作为只读来源，不 commit、不清理、不移动、不删除。

## 3. 可以迁移

以下 6 个路径可以进入 Task 7 实际复制白名单：

| 路径 | 原因 |
|---|---|
| `docs/agent_operating_playbook.md` | agent 操作手册，属于 harness/操作约束文档 |
| `docs/agent_operating_playbook.html` | agent 操作手册 HTML 阅读版 |
| `docs/opensource_reference_audit.md` | 开源参考审计文档 |
| `docs/验收报告格式.md` | 验收报告格式模板 |
| `reports/audits/git_worktree_inventory.md` | 工作区盘点审计基线 |
| `reports/audits/harness_readiness_audit.md` | harness readiness 审计基线 |

## 4. 暂缓迁移

以下路径暂缓进入 Task 7。它们可能有文档价值，但名称或主题接近策略设计、版本化实验、策略搜索或已有根文档合并，不能自动迁移：

- `README.md`
- `STRATEGY_GUIDE.md`
- `docs/superpowers/plans/2026-06-25-reliable-strategy-search.md`
- `docs/superpowers/plans/2026-07-01-v1119-tail-risk-cooldown.md`
- `docs/superpowers/plans/2026-07-01-v1124-position-sizing.md`
- `docs/superpowers/plans/2026-07-02-v1125-chop-drag-sizer.md`
- `docs/superpowers/plans/2026-07-02-v1126-core-recoil-micro-sizer.md`
- `docs/superpowers/plans/2026-07-02-v1127-dual-trap-micro-sizer.md`
- `docs/superpowers/plans/2026-07-02-v1128-selective-drag-pruner.md`
- `docs/superpowers/specs/2026-06-25-reliable-strategy-search-design.md`
- `docs/superpowers/specs/2026-07-01-v1119-tail-risk-cooldown-design.md`
- `docs/superpowers/specs/2026-07-01-v1119-tail-risk-cooldown-design.html`
- `docs/superpowers/specs/2026-07-02-v1125-chop-drag-sizer-design.md`
- `docs/superpowers/specs/2026-07-02-v1125-chop-drag-sizer-design.html`
- `docs/superpowers/specs/2026-07-02-v1126-core-recoil-micro-sizer-design.md`
- `docs/superpowers/specs/2026-07-02-v1126-core-recoil-micro-sizer-design.html`
- `docs/superpowers/specs/2026-07-02-v1127-dual-trap-micro-sizer-design.md`
- `docs/superpowers/specs/2026-07-02-v1127-dual-trap-micro-sizer-design.html`
- `docs/superpowers/specs/2026-07-02-v1128-selective-drag-pruner-design.md`
- `docs/superpowers/specs/2026-07-02-v1128-selective-drag-pruner-design.html`

暂缓项后续如需迁移，应另开人工复核任务，并逐文件确认是否包含策略行为、参数、回测解释、版本化策略证据或 live/server 操作内容。

## 5. 必须人工阅读后决定

以下路径必须人工阅读全文后才能决定是否迁移；Task 7 不应包含它们：

- `AGENTS.md`
- `docs/Phase 2.5.md`
- `docs/architecture/2026-06-13-btc-mvp-trading-system.md`
- `docs/phase1_remediation_official.md`
- `docs/phase2_dry_run_checklist.md`
- `docs/phase2_experiment_matrix.md`
- `docs/phase2_implementation_plan.md`
- `docs/phase2_plan.md`
- `docs/phase2_server_frontend_cleanup_spec.md`
- `docs/第二阶段.md`
- `docs/superpowers/plans/2026-06-13-btc-mvp-trading-system-plan.md`
- `docs/superpowers/plans/2026-06-14-btc-phase1-remediation.md`

人工阅读时必须检查：

- 是否包含 API key、交易所凭证、服务器密钥、dashboard 密码或其他 secret。
- 是否包含 live/server 操作步骤。
- 是否包含策略实现、bot 配置、runtime 数据、回测产物或报告原始数据。
- 是否涉及 V10.8.2 或 V11.29。
- 是否会覆盖 clean worktree 中更严格的 agent/harness 指令。

## 6. 禁止迁移

以下路径不得进入 Task 7：

- `LIVE_TRADING.md`
- `DEPLOY.md`
- `docs/superpowers/plans/2026-06-14-phase1-server-dashboard-rollout.md`

以下范围也一律禁止迁移：

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key、交易所凭证、服务器密钥、dashboard 密码
- V10.8.2
- V11.29
- live/server 操作面

## 7. Task 7 显式复制白名单

Task 7 只允许执行以下复制草案。Task 6R 不执行复制。

```powershell
$SourceRoot = 'D:\code\freqtrade-strategies'
$DestRoot = 'D:\code\freqtrade-strategies-clean'

$CopyWhitelist = @(
  'docs/agent_operating_playbook.md',
  'docs/agent_operating_playbook.html',
  'docs/opensource_reference_audit.md',
  'docs/验收报告格式.md',
  'reports/audits/git_worktree_inventory.md',
  'reports/audits/harness_readiness_audit.md'
)

foreach ($Path in $CopyWhitelist) {
  $Source = Join-Path $SourceRoot $Path
  $Destination = Join-Path $DestRoot $Path
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
  Copy-Item -LiteralPath $Source -Destination $Destination
}
```

Task 7 只允许使用以下显式 stage 白名单：

```powershell
git add -- `
  docs/agent_operating_playbook.md `
  docs/agent_operating_playbook.html `
  docs/opensource_reference_audit.md `
  docs/验收报告格式.md `
  reports/audits/git_worktree_inventory.md `
  reports/audits/harness_readiness_audit.md
```

明确禁止：

```powershell
git add -A
git add .
```

## 8. Task 7 进入条件

Task 7 进入前必须重新确认：

- 当前目录是 `D:\code\freqtrade-strategies-clean`。
- 当前分支是 `codex/btc-mvp-system-harnessed`。
- Task 6R 已 commit。
- `git status --short` 输出为空。
- `.\scripts\run_agent_readiness_checks.ps1` 通过。
- 原始工作区只读，不修改、不 commit、不清理。

Task 7 完成后必须运行：

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```
