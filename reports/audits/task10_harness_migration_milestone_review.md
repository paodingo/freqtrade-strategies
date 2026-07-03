# Task 10: Harness Migration Milestone Review

结论：当前 harness migration 阶段已经形成可继续开发的 clean worktree、静态 readiness guard、A 类文档迁移基线和 generated/report ignore 防污染规则。原始脏工作区仍保持 quarantine-only，不应自动清理、移动、删除、stash 或提交。Task 9R 已关闭 Task 8/9 发现的 generated report ignore gap，下一阶段可以进入只读审查类任务，但不能降低策略、bot 配置、secret、V10.8.2、V11.29、live/server 操作面的边界。

## 1. 当前分支、commit、工作区状态

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 当前 commit：`018394b Patch generated artifact ignore gaps`
- `git status --short`：输出为空

## 2. Task 1 到 Task 9R 已完成清单

| 任务 | 状态 | 主要结果 |
|---|---|---|
| Task 1 | 已完成于早期 harness 阶段 | 建立 clean worktree/branch/clean status 前置门禁原则；错误目录或脏状态必须停止 |
| Task 2 | 已完成 | 形成原始脏工作区 triage/quarantine 思路，不自动清理原始目录 |
| Task 3 | 已完成 | 建立 `.gitignore` 与 A 类白名单基线，禁止 `git add -A` / `git add .` |
| Task 4 | 已完成 | 集成 static harness guard，并验证 integration test 记录 |
| Task 4R | 已完成 | 增加 Windows PowerShell readiness 入口 `scripts/run_agent_readiness_checks.ps1` |
| Task 5 | 已完成 | 确认 `D:\code\freqtrade-strategies-clean` 可作为后续正式开发 base |
| Task 6 | 已完成 | 从原始脏工作区只读识别 A 类文档、harness、审计、任务候选，生成迁移计划 |
| Task 6R | 已完成 | 审查 A 类迁移白名单，收紧 Task 7 可迁移文件 |
| Task 7 | 已完成 | 迁移 guard 当时允许的审计基线，记录普通 `docs/*` 被 guard 阻断原因 |
| Task 7R | 已完成 | 复核被阻断的 4 个 `docs/*`，建议精确路径 allowlist |
| Task 7S | 已完成 | 精确扩展 4 个 docs 白名单并迁移 approved docs，没有放开 `docs/**` |
| Task 8 | 已完成 | 验证 generated ignore 覆盖，发现 361 个报告类路径未覆盖 |
| Task 9 | 已完成 | closure 确认 Task 8 gap 需要 Task 9R，不修改 `.gitignore` |
| Task 9R | 已完成 | 最小修补 generated/report ignore gap，原始 988 候选中 986 个会被 ignore，剩余 2 个为应保留的 `reports/audits/**` |

## 3. 当前 harness 能力清单

- `scripts/run_agent_readiness_checks.ps1`：Windows 本地 readiness 入口，执行 guard 语法检查和运行态检查。
- `scripts/run_agent_readiness_checks.sh`：Linux/Git Bash/CI readiness 入口。
- `scripts/guard_harness_diff.js`：只允许低风险 harness、审计、任务、`.gitignore`、精确 docs 白名单等路径变更；阻断策略、bot 配置、dashboard、deploy、server/live、secret-adjacent 路径。
- `scripts/guard_no_secret_material.js`：阻断 `.env`、`user_data/monitor.env`、key material，并扫描变更文件中的常见 secret 模式。
- `scripts/guard_trading_surface.js`：阻断 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`、bot lifecycle 脚本、V10.8.2/V11.29 相关路径。
- `.gitignore`：覆盖 generated/cache/data/report/backtest 产物，同时保留 `reports/audits/**`、`tasks/**`、`docs/**` 等审计/任务/文档基线可提交。
- `docs/harness/change_surface_matrix.md`：记录允许面和阻断面，包括 Task 7S 的精确 docs 白名单。
- `reports/audits/**` 与 `tasks/active/**`：形成可追溯任务证据链。

## 4. Readiness checks 结果

Task 10 进入前 readiness：

```text
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

Task 10 完成后还需运行：

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## 5. 原始脏工作区仍未处理的风险

原始脏工作区 `D:\code\freqtrade-strategies` 仍未被清理，也不应被自动清理。剩余风险包括：

- 策略候选、策略版本和实验文件仍可能混杂在工作区状态中。
- bot 配置、runtime 数据、监控状态、历史 backtest/report 产物仍可能混杂。
- V10.8.2、V11.29、live/server/dashboard/deploy 相关证据仍必须冻结处理。
- secret-adjacent 路径仍必须禁止自动读取。
- 原始目录历史状态仍只能作为证据来源，不能作为自动迁移来源。

## 6. 仍禁止 Codex 自动处理的事项

仍禁止自动执行：

- 修改 `strategies/**`
- 修改 `user_data/**`、`configs/**` 或 bot 配置
- 修改 `dashboard/**`、`deploy/**`
- 读取 `.env`、`user_data/monitor.env` 或任何 credential/key/password/token
- 启动、停止或重启 bot
- 登录服务器或触碰 live/server 操作面
- 运行回测
- 自动清理、删除、移动、stash 或 commit 原始脏工作区
- 自动处理 V10.8.2、V11.29 相关路径
- 使用 `git add -A` 或 `git add .`

## 7. 推荐后续任务顺序

下一阶段建议按以下顺序推进：

1. 策略候选只读盘点：只读列出原始脏工作区中可能属于策略候选的文件，分类为候选、版本证据、禁止迁移、需人工复核；不读取 secret，不改策略。
2. bot 配置只读盘点：只读列出 bot 配置和 runtime-adjacent 文件，区分 config、runtime state、secret-adjacent、禁止读取；不打开 `.env` 或 credential 文件。
3. V11.29 真实执行验证准备：只准备验证计划和数据需求，明确 server-authoritative 证据、dashboard/API 入口、禁止自动登录和禁止改 live 面的边界。

## 8. 是否可以进入策略候选只读审查

可以进入，但仅限单独任务、只读、显式路径范围，并继续禁止修改策略。

建议 Task 11 采用以下边界：

- 只读使用 `git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- strategies docs reports tasks` 等 Git metadata 级观察。
- 不修改 `strategies/**`。
- 不复制策略文件。
- 不运行回测。
- 不碰 V10.8.2/V11.29 除非任务明确是只读分类且不打开敏感内容。

## 9. 是否可以进入 bot 配置只读审查

可以进入，但风险高于策略候选盘点，必须采用更窄边界。

建议 Task 12 采用以下边界：

- 只读列出配置路径和状态，优先用 Git metadata，不直接读取 secret-adjacent 文件内容。
- 禁止读取 `.env`、`user_data/monitor.env`、API key、交易所凭证、服务器密钥、dashboard 密码。
- 禁止修改 `user_data/**`、`configs/**`、bot lifecycle 脚本。
- 禁止启动 bot、登录服务器或调用 live API。

## 10. Task 10 停止点

Task 10 只做阶段性复盘，不进入 Task 11，不拆 Task 10R。

下一阶段 3 个高价值任务：

- 策略候选只读盘点
- bot 配置只读盘点
- V11.29 真实执行验证准备
