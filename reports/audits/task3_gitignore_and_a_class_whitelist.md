# Task 3 Gitignore Draft + A-Class Commit Whitelist

日期：2026-07-02

范围：当前 harness worktree `D:\code\freqtrade-strategies-harness`。原始工作区 `D:\code\freqtrade-strategies` 仅做只读 Git 状态检查；本任务不修改原始工作区，不删除、不移动、不 stash、不提交，不读取 secret，不启动 bot，不登录服务器，不运行回测。

## 1. 新增 `.gitignore` 规则说明

本次只新增 generated/log/db/cache/data 类规则：

```gitignore
.tmp_*/
output/
reports/btc_mvp/backtests/
reports/reliable_strategy_search_*/
reports/api_gap_backtest_candidates/
user_data/backtest_results/
user_data/alpha/
*.sqlite
*.sqlite-*
*.db
*.db-*
*.feather
*.parquet
*.zip
*.tgz
*.log
```

这些规则只用于降低回测产物、临时分析产物、行情缓存和数据库/压缩包误入 Git 的概率；不代表可以删除现有文件，也不代表这些文件已完成证据归档。

## 2. 每条规则对应的风险类别

| 规则 | 风险类别 | 说明 |
| --- | --- | --- |
| `.tmp_*/` | C 类 generated/cache | 临时分析目录，容易混入一次性实验产物 |
| `output/` | C 类 generated/output | 截图、脚本输出、打包文件等运行产物 |
| `reports/btc_mvp/backtests/` | B/C 类 backtest evidence | 回测结果应保留为证据，不默认提交 |
| `reports/reliable_strategy_search_*/` | B/C 类 strategy-search evidence | 策略搜索报告、zip、feather、配置快照，易混入 V10.8.2/V11.x 证据 |
| `reports/api_gap_backtest_candidates/` | B/C 类 generated reports | API gap 候选回测产物，不默认提交 |
| `user_data/backtest_results/` | C 类 data/cache | Freqtrade 回测输出和行情数据缓存 |
| `user_data/alpha/` | C 类 data/cache | open interest / alpha 数据缓存 |
| `*.sqlite` | C 类 db | 本地数据库产物 |
| `*.sqlite-*` | C 类 db journal | SQLite journal/WAL/SHM 产物 |
| `*.db` | C 类 db | 本地数据库产物 |
| `*.db-*` | C 类 db journal | DB journal/WAL/SHM 产物 |
| `*.feather` | C 类 data/cache | 行情、wallet、market_change 等列式数据产物 |
| `*.parquet` | C 类 data/cache | 行情或 alpha 数据缓存 |
| `*.zip` | C 类 archive | 回测压缩包或导出产物 |
| `*.tgz` | C 类 archive | rollout/export 打包产物 |
| `*.log` | C 类 log | 运行日志 |

## 3. 为什么不 ignore 文档和审计路径

不 ignore `reports/audits/*.md`：审计基线、工作区分流记录、readiness 证据属于 A 类可审查文档，需要能被显式提交。

不 ignore `tasks/**/*.md`：任务记录用于约束后续 agent 行为，是 harness 管理面的一部分，需要能被显式提交。

不 ignore `docs/**/*.md`：计划、spec、架构说明和人工决策记录属于 A 类文档；它们是后续分流、审查和复盘的主要依据。

同时不 ignore `AGENTS.md`、`README.md`、`STRATEGY_GUIDE.md`。这些是仓库行为、入口说明和策略说明的人工文档，必须保留可审查性。

## 4. 原始工作区 A 类建议提交白名单

只读检查显示，原始工作区 A 类候选包括：

- `AGENTS.md`
- `README.md`
- `STRATEGY_GUIDE.md`
- `docs/Phase 2.5.md`
- `docs/agent_operating_playbook.md`
- `docs/architecture/2026-06-13-btc-mvp-trading-system.md`
- `docs/opensource_reference_audit.md`
- `docs/phase1_remediation_official.md`
- `docs/phase2_dry_run_checklist.md`
- `docs/phase2_experiment_matrix.md`
- `docs/phase2_implementation_plan.md`
- `docs/phase2_plan.md`
- `docs/phase2_server_frontend_cleanup_spec.md`
- `docs/superpowers/plans/2026-06-13-btc-mvp-trading-system-plan.md`
- `docs/superpowers/plans/2026-06-14-btc-phase1-remediation.md`
- `docs/superpowers/plans/2026-06-14-phase1-server-dashboard-rollout.md`
- `docs/superpowers/plans/2026-06-25-reliable-strategy-search.md`
- `docs/superpowers/plans/2026-07-01-v1119-tail-risk-cooldown.md`
- `docs/superpowers/plans/2026-07-01-v1124-position-sizing.md`
- `docs/superpowers/plans/2026-07-02-v1125-chop-drag-sizer.md`
- `docs/superpowers/plans/2026-07-02-v1126-core-recoil-micro-sizer.md`
- `docs/superpowers/plans/2026-07-02-v1127-dual-trap-micro-sizer.md`
- `docs/superpowers/plans/2026-07-02-v1128-selective-drag-pruner.md`
- `docs/superpowers/specs/2026-06-25-reliable-strategy-search-design.md`
- `docs/superpowers/specs/2026-07-01-v1119-tail-risk-cooldown-design.md`
- `docs/superpowers/specs/2026-07-02-v1125-chop-drag-sizer-design.md`
- `docs/superpowers/specs/2026-07-02-v1126-core-recoil-micro-sizer-design.md`
- `docs/superpowers/specs/2026-07-02-v1127-dual-trap-micro-sizer-design.md`
- `docs/superpowers/specs/2026-07-02-v1128-selective-drag-pruner-design.md`
- `docs/第二阶段.md`
- `docs/验收报告格式.md`
- `reports/audits/git_worktree_inventory.md`
- `reports/audits/harness_readiness_audit.md`

暂不放入默认白名单：

- `DEPLOY.md`：已 modified，但属于 server/deploy 邻近文档，需人工复核。
- `LIVE_TRADING.md`：已 modified，但属于 live 操作邻近文档，需人工复核。
- `docs/*.html` 和 `docs/superpowers/specs/*.html`：可能是生成的阅读版，需人工确认是否应提交。

## 5. `git add -- <explicit paths>` 白名单命令草案

人工确认后，可只用显式路径 stage A 类文档：

```powershell
git -C D:\code\freqtrade-strategies add -- `
  AGENTS.md `
  README.md `
  STRATEGY_GUIDE.md `
  "docs/Phase 2.5.md" `
  docs/agent_operating_playbook.md `
  docs/architecture/2026-06-13-btc-mvp-trading-system.md `
  docs/opensource_reference_audit.md `
  docs/phase1_remediation_official.md `
  docs/phase2_dry_run_checklist.md `
  docs/phase2_experiment_matrix.md `
  docs/phase2_implementation_plan.md `
  docs/phase2_plan.md `
  docs/phase2_server_frontend_cleanup_spec.md `
  docs/superpowers/plans/2026-06-13-btc-mvp-trading-system-plan.md `
  docs/superpowers/plans/2026-06-14-btc-phase1-remediation.md `
  docs/superpowers/plans/2026-06-14-phase1-server-dashboard-rollout.md `
  docs/superpowers/plans/2026-06-25-reliable-strategy-search.md `
  docs/superpowers/plans/2026-07-01-v1119-tail-risk-cooldown.md `
  docs/superpowers/plans/2026-07-01-v1124-position-sizing.md `
  docs/superpowers/plans/2026-07-02-v1125-chop-drag-sizer.md `
  docs/superpowers/plans/2026-07-02-v1126-core-recoil-micro-sizer.md `
  docs/superpowers/plans/2026-07-02-v1127-dual-trap-micro-sizer.md `
  docs/superpowers/plans/2026-07-02-v1128-selective-drag-pruner.md `
  docs/superpowers/specs/2026-06-25-reliable-strategy-search-design.md `
  docs/superpowers/specs/2026-07-01-v1119-tail-risk-cooldown-design.md `
  docs/superpowers/specs/2026-07-02-v1125-chop-drag-sizer-design.md `
  docs/superpowers/specs/2026-07-02-v1126-core-recoil-micro-sizer-design.md `
  docs/superpowers/specs/2026-07-02-v1127-dual-trap-micro-sizer-design.md `
  docs/superpowers/specs/2026-07-02-v1128-selective-drag-pruner-design.md `
  docs/第二阶段.md `
  docs/验收报告格式.md `
  reports/audits/git_worktree_inventory.md `
  reports/audits/harness_readiness_audit.md
```

stage 后必须人工检查：

```powershell
git -C D:\code\freqtrade-strategies diff --cached --name-only
```

## 6. 明确禁止使用

禁止：

```powershell
git -C D:\code\freqtrade-strategies add -A
git -C D:\code\freqtrade-strategies add .
```

原因：原始工作区混有 `strategies/**`、`user_data/**`、dashboard、scripts、deploy、reports、回测数据、V10.8.2/V11.29 相关路径和 secret-adjacent 路径。宽泛 stage 会破坏分流边界。

## 7. 仍需人工确认的路径

- `DEPLOY.md`
- `LIVE_TRADING.md`
- `docs/**/*.html`
- `btc_system/**`
- `tests/**`
- `scripts/**`
- `dashboard/**`
- `strategies/**`
- `configs/**`
- `user_data/config*.json`
- `user_data/config_multi_futures_*.json`
- `reports/btc_mvp/backtests/**`
- `reports/reliable_strategy_search_*/**`
- `reports/api_gap_backtest_candidates/**`
- `.tmp_*/`
- `output/**`
- `.env`
- `user_data/monitor.env`
- 任何 API key、交易所凭证、服务器密钥、dashboard 密码、token 或 private key 路径

## 8. 后续 Task 4 推荐

推荐 Task 4：只做原始工作区 A 类文档提交的 staged whitelist 审查。

建议边界：

- 不运行 `git add -A` 或 `git add .`。
- 只允许执行上面的 `git add -- <explicit paths>` 草案，且执行前再次展示路径。
- stage 后只运行 `git diff --cached --name-only` 和 `git status --short --untracked-files=all`。
- 不提交原始工作区，除非用户在 Task 4 中明确授权 commit。
- 不处理 D/E/F/G 类，不碰策略、bot 配置、V10.8.2、V11.29、server/live 操作面或 secret。
