# Task 6: A-Class Documentation Migration Plan

结论：本任务只读检查了原始脏工作区 `D:\code\freqtrade-strategies` 的文档、harness、审计和任务基线路径，生成迁移计划与显式白名单草案。未复制文件，未提交，未清理原始工作区。

## 1. 执行基线

- clean 工作区：`D:\code\freqtrade-strategies-clean`
- clean 分支：`codex/btc-mvp-system-harnessed`
- Task 5 commit：`3730ba0 Establish clean harnessed development base`
- 原始工作区：`D:\code\freqtrade-strategies`
- 原始工作区分支：`codex/btc-mvp-system`
- 原始工作区 commit：`5a5d426`

前置 gate：

```text
git status --short
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

## 2. 只读检查命令

已运行：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
git -C D:\code\freqtrade-strategies diff --name-only -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
```

只读检查结果要点：

- 已修改 tracked 文档：`DEPLOY.md`、`LIVE_TRADING.md`、`README.md`、`STRATEGY_GUIDE.md`
- 未跟踪候选：`AGENTS.md`、`docs/**` 下若干文档、`reports/audits/git_worktree_inventory.md`、`reports/audits/harness_readiness_audit.md`
- `tasks` 路径在原始工作区本次查询中无候选输出
- `diff --name-only` 仅返回四个已修改根文档：`DEPLOY.md`、`LIVE_TRADING.md`、`README.md`、`STRATEGY_GUIDE.md`

## 3. A 类候选路径清单与建议动作

| 原始路径 | 状态 | 建议动作 | 理由 |
|---|---:|---|---|
| `AGENTS.md` | `??` | 人工阅读后迁移 | agent 指令可能影响后续行为，需人工确认与 clean worktree 规则兼容 |
| `docs/Phase 2.5.md` | `??` | 人工阅读后迁移 | 阶段文档可作为 A 类候选，但文件名含空格，迁移前需确认内容不含策略/live/server 操作细节 |
| `docs/agent_operating_playbook.md` | `??` | 迁移 | agent 操作手册，属于 harness/操作约束文档候选 |
| `docs/agent_operating_playbook.html` | `??` | 迁移 | 上述手册的 HTML 阅读版，属于文档候选 |
| `docs/architecture/2026-06-13-btc-mvp-trading-system.md` | `??` | 人工阅读后迁移 | 架构文档候选，但标题涉及 trading system，需确认不引入策略或 live 操作面 |
| `docs/opensource_reference_audit.md` | `??` | 迁移 | 开源参考审计，属于审计/文档候选 |
| `docs/phase1_remediation_official.md` | `??` | 人工阅读后迁移 | 阶段修复说明候选，需确认不携带策略行为或 secret |
| `docs/phase2_dry_run_checklist.md` | `??` | 人工阅读后迁移 | dry-run checklist 可能涉及 bot/runtime 状态，需人工确认边界 |
| `docs/phase2_experiment_matrix.md` | `??` | 人工阅读后迁移 | 实验矩阵可能涉及策略参数或回测语义，需人工确认 |
| `docs/phase2_implementation_plan.md` | `??` | 人工阅读后迁移 | 实施计划候选，需确认不包含 live/server 操作步骤 |
| `docs/phase2_plan.md` | `??` | 人工阅读后迁移 | 阶段计划候选，需人工确认内容边界 |
| `docs/phase2_server_frontend_cleanup_spec.md` | `??` | 人工复核 | 文件名涉及 server/frontend cleanup，可能触及 dashboard/server 面，不进自动白名单 |
| `docs/第二阶段.md` | `??` | 人工阅读后迁移 | 阶段文档候选，需人工确认内容边界 |
| `docs/验收报告格式.md` | `??` | 迁移 | 验收报告格式，属于文档模板候选 |
| `reports/audits/git_worktree_inventory.md` | `??` | 迁移 | 工作区盘点审计，属于 A 类审计基线 |
| `reports/audits/harness_readiness_audit.md` | `??` | 迁移 | harness readiness 审计，属于 A 类审计基线 |
| `README.md` | `M` | 人工复核 | clean base 已有 README 时不应直接覆盖；需人工 diff 后决定合并 |
| `STRATEGY_GUIDE.md` | `M` | 暂缓 | 策略指南属于策略语义文档，可能影响 strategy surface |
| `LIVE_TRADING.md` | `M` | 禁止迁移 | 文件名和语义直接触及 live 操作面 |
| `DEPLOY.md` | `M` | 禁止迁移 | 文件名和语义直接触及 deploy/server 操作面 |
| `docs/superpowers/plans/2026-06-13-btc-mvp-trading-system-plan.md` | `??` | 人工复核 | 计划文档涉及 trading system，需确认是否只保留开发计划证据 |
| `docs/superpowers/plans/2026-06-14-btc-phase1-remediation.md` | `??` | 人工复核 | 需确认是否包含策略/live/server 操作 |
| `docs/superpowers/plans/2026-06-14-phase1-server-dashboard-rollout.md` | `??` | 禁止迁移 | 文件名涉及 server/dashboard rollout |
| `docs/superpowers/plans/2026-06-25-reliable-strategy-search.md` | `??` | 暂缓 | 涉及 strategy search，需人工确认是否为纯计划证据 |
| `docs/superpowers/plans/2026-07-01-v1119-tail-risk-cooldown.md` | `??` | 暂缓 | 版本化策略计划，需避免误迁移策略行为证据 |
| `docs/superpowers/plans/2026-07-01-v1124-position-sizing.md` | `??` | 暂缓 | 版本化策略计划，需避免误迁移策略行为证据 |
| `docs/superpowers/plans/2026-07-02-v1125-chop-drag-sizer.md` | `??` | 暂缓 | 版本化策略计划，需避免误迁移策略行为证据 |
| `docs/superpowers/plans/2026-07-02-v1126-core-recoil-micro-sizer.md` | `??` | 暂缓 | 版本化策略计划，需避免误迁移策略行为证据 |
| `docs/superpowers/plans/2026-07-02-v1127-dual-trap-micro-sizer.md` | `??` | 暂缓 | 版本化策略计划，需避免误迁移策略行为证据 |
| `docs/superpowers/plans/2026-07-02-v1128-selective-drag-pruner.md` | `??` | 暂缓 | 版本化策略计划，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-06-25-reliable-strategy-search-design.md` | `??` | 暂缓 | 涉及 strategy search design，需人工确认是否迁移 |
| `docs/superpowers/specs/2026-07-01-v1119-tail-risk-cooldown-design.md` | `??` | 暂缓 | 版本化策略规格，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-01-v1119-tail-risk-cooldown-design.html` | `??` | 暂缓 | 版本化策略规格 HTML，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1125-chop-drag-sizer-design.md` | `??` | 暂缓 | 版本化策略规格，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1125-chop-drag-sizer-design.html` | `??` | 暂缓 | 版本化策略规格 HTML，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1126-core-recoil-micro-sizer-design.md` | `??` | 暂缓 | 版本化策略规格，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1126-core-recoil-micro-sizer-design.html` | `??` | 暂缓 | 版本化策略规格 HTML，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1127-dual-trap-micro-sizer-design.md` | `??` | 暂缓 | 版本化策略规格，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1127-dual-trap-micro-sizer-design.html` | `??` | 暂缓 | 版本化策略规格 HTML，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1128-selective-drag-pruner-design.md` | `??` | 暂缓 | 版本化策略规格，需避免误迁移策略行为证据 |
| `docs/superpowers/specs/2026-07-02-v1128-selective-drag-pruner-design.html` | `??` | 暂缓 | 版本化策略规格 HTML，需避免误迁移策略行为证据 |

## 4. 明确排除范围

本迁移计划明确排除：

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `reports/btc_mvp/backtests/**`
- `reports/reliable_strategy_search_*/**`
- `reports/api_gap_backtest_candidates/**`
- `.env`
- `user_data/monitor.env`
- API key、交易所凭证、服务器密钥、dashboard 密码
- V10.8.2、V11.29
- live/server 操作面
- 回测产物、报告原始数据、策略实现、bot 配置和 runtime 数据

即使上述内容以文档引用形式出现，也必须在人工阅读阶段标记并从迁移白名单中移除。

## 5. 显式复制白名单命令草案

以下命令只是 Task 7 草案；Task 6 不执行复制。

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

以下文件可在人工阅读通过后追加到 `$CopyWhitelist`：

```powershell
$HumanApprovedWhitelist = @(
  'AGENTS.md',
  'docs/Phase 2.5.md',
  'docs/architecture/2026-06-13-btc-mvp-trading-system.md',
  'docs/phase1_remediation_official.md',
  'docs/phase2_dry_run_checklist.md',
  'docs/phase2_experiment_matrix.md',
  'docs/phase2_implementation_plan.md',
  'docs/phase2_plan.md',
  'docs/第二阶段.md'
)
```

不得把 `README.md`、`STRATEGY_GUIDE.md`、`LIVE_TRADING.md`、`DEPLOY.md`、`docs/superpowers/plans/**` 或 `docs/superpowers/specs/**` 放入自动复制白名单。

## 6. 显式 `git add -- <paths>` 白名单草案

以下命令只是 Task 7 草案；Task 6 不执行 stage。

```powershell
git add -- `
  docs/agent_operating_playbook.md `
  docs/agent_operating_playbook.html `
  docs/opensource_reference_audit.md `
  docs/验收报告格式.md `
  reports/audits/git_worktree_inventory.md `
  reports/audits/harness_readiness_audit.md
```

人工阅读通过后，才允许显式追加：

```powershell
git add -- `
  AGENTS.md `
  "docs/Phase 2.5.md" `
  docs/architecture/2026-06-13-btc-mvp-trading-system.md `
  docs/phase1_remediation_official.md `
  docs/phase2_dry_run_checklist.md `
  docs/phase2_experiment_matrix.md `
  docs/phase2_implementation_plan.md `
  docs/phase2_plan.md `
  docs/第二阶段.md
```

禁止使用：

```powershell
git add -A
git add .
```

## 7. 需要人工阅读后才能迁移的文件

以下文件必须先人工阅读，再决定是否进入 Task 7 复制白名单：

- `AGENTS.md`
- `README.md`
- `STRATEGY_GUIDE.md`
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
- `docs/superpowers/plans/2026-06-25-reliable-strategy-search.md`
- all `docs/superpowers/plans/2026-07-*-v*.md`
- all `docs/superpowers/specs/2026-07-*-v*.md`
- all `docs/superpowers/specs/2026-07-*-v*.html`

以下文件本计划建议禁止迁移，除非另开单独的人工作业：

- `LIVE_TRADING.md`
- `DEPLOY.md`
- `docs/superpowers/plans/2026-06-14-phase1-server-dashboard-rollout.md`

## 8. 后续 Task 7 推荐

推荐 Task 7：执行 A 类文档迁移的第一批低风险白名单复制，只复制第 5 节 `$CopyWhitelist` 中的六个路径。Task 7 应继续满足：

- 进入前确认 clean worktree 当前目录、分支、干净状态和 readiness gate。
- 复制前再次只读确认原始路径存在。
- 只使用显式 `Copy-Item -LiteralPath` 白名单。
- 只使用显式 `git add -- <paths>` 白名单。
- 完成后运行 `.\scripts\run_agent_readiness_checks.ps1`、`git diff --name-only`、`git status --short --untracked-files=all`。
- 不复制、不 stage、不提交任何策略、bot 配置、secret、回测产物、报告原始数据、V10.8.2、V11.29、live/server 操作面。
