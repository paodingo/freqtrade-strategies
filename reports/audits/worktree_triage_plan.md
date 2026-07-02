# Worktree Triage / Evidence Quarantine Plan

日期：2026-07-02

范围：为原始脏工作区 `D:\code\freqtrade-strategies` 制定安全分流方案。本文只基于只读 Git 路径/统计命令，不读取 `.env`、`user_data/monitor.env`、API key、交易所凭证、服务器密钥，不启动/停止/重启 bot，不登录服务器，不运行回测。

## 1. 当前原始工作区风险摘要

只读检查命令：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all
git -C D:\code\freqtrade-strategies diff --name-only
git -C D:\code\freqtrade-strategies diff --stat
git -C D:\code\freqtrade-strategies ls-files --others --exclude-standard
```

观察结果：

- tracked modified：27 个文件。
- tracked diff 规模：`27 files changed, 7297 insertions(+), 208 deletions(-)`。
- untracked：输出约 1275 行，包含文档、`btc_system/**`、`reports/**`、`scripts/**`、`strategies/**`、`tests/**`、`user_data/**`、`output/**`、临时分析目录等。
- 高风险混杂面：策略候选、bot 配置、dashboard、server/deploy 操作面、回测产物、行情数据、报告产物、live/phase2 配置与 V10.8.2/V11.29 相关路径交织在同一个原始工作区。
- 直接风险：任何自动 `add -A`、stash、清理、移动、删除、格式化或大范围 commit 都可能混入策略行为、bot 配置、V10.8.2/V11.29 证据、server 操作脚本或 secret-adjacent 路径。

结论：原始工作区只能人工分批确认，不能由 Codex 自动清理。

## 2. 路径分类规则

按路径和用途先分流，后看内容；需要看内容时只能由人工或在明确授权的后续任务中处理。

| 类别 | 默认动作 | 路径规则 |
| --- | --- | --- |
| A | 建议提交 | 文档、harness、审计基线、任务记录、只读说明，不触碰交易行为 |
| B | 保留但不提交 | 回测结果、报告快照、压缩包、图片、原始产物 |
| C | 建议加入 `.gitignore` | generated/log/db/cache/data 文件、临时目录、SQLite/feather/parquet/zip 等 |
| D | 人工确认 | `strategies/**` 策略候选或策略修改 |
| E | 人工确认 | `user_data/config*.json`、`configs/**` bot/实验配置 |
| F | 默认冻结 | V10.8.2、V11.29、live、deploy、server 操作面 |
| G | 禁止自动读取或处理 | `.env`、`user_data/monitor.env`、key、credential、password、token、pem 等 |

## 3. A 类：建议提交的文档 / harness / 审计基线

候选路径：

- `AGENTS.md`
- `docs/**/*.md`
- `docs/**/*.html`，仅当是人工编写的可读说明而非生成报告。
- `docs/superpowers/plans/*.md`
- `docs/superpowers/specs/*.md`
- `reports/audits/*.md`
- `tasks/**/*.md`
- `README.md`
- `STRATEGY_GUIDE.md`
- `LIVE_TRADING.md`
- `DEPLOY.md`，但涉及 server/live 命令时必须人工复核。

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
git -C D:\code\freqtrade-strategies diff --name-only -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
git -C D:\code\freqtrade-strategies add -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md LIVE_TRADING.md DEPLOY.md
git -C D:\code\freqtrade-strategies diff --cached --name-only
git -C D:\code\freqtrade-strategies commit -m "Add worktree audit documentation"
```

限制：

- 不要把 `reports/btc_mvp/backtests/**`、`reports/reliable_strategy_search_*/**`、`.tmp_*` 混入 A 类。
- `DEPLOY.md`、`LIVE_TRADING.md` 如包含 live 操作步骤，应单独人工复核后再提交。

## 4. B 类：建议保留但不提交的回测/报告/原始产物

候选路径：

- `reports/btc_mvp/backtests/**`
- `reports/reliable_strategy_search_v*/**`
- `reports/api_gap_backtest_candidates/**`
- `reports/*.html`
- `reports/*.json`
- `output/**/*.png`
- `output/**/*.tgz`
- `.tmp_v1127_analysis/**`
- `.tmp_v1128_analysis/**`

处理建议：

- 保留作为证据，不直接 commit。
- 如果需要长期保留，人工复制到外部证据归档目录，并记录来源路径、生成时间、对应策略版本和命令。
- 不要让 Codex 自动移动或删除这些文件。

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- reports output .tmp_v1127_analysis .tmp_v1128_analysis
git -C D:\code\freqtrade-strategies ls-files --others --exclude-standard -- reports output .tmp_v1127_analysis .tmp_v1128_analysis
```

## 5. C 类：建议加入 `.gitignore` 的 generated/log/db/cache 类路径

候选 ignore 规则：

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

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- .gitignore
git -C D:\code\freqtrade-strategies check-ignore -n user_data/backtest_results/reliable_strategy_search_v11_data/BTC_USDT-1h.feather
git -C D:\code\freqtrade-strategies check-ignore -n reports/btc_mvp/backtests/latest.json
git -C D:\code\freqtrade-strategies diff -- .gitignore
```

限制：

- 不要 ignore `reports/audits/*.md`。
- 不要 ignore 需要人工提交的计划/spec 文档。
- 不要自动删除已生成文件；只在人工确认后调整 ignore。

## 6. D 类：必须人工确认的策略候选

modified 策略：

- `strategies/RegimeAwareV661AlphaRisk.py`
- `strategies/RegimeAwareV66AlphaRisk.py`
- `strategies/RegimeAwareV67AlphaRisk.py`
- `strategies/trade_supervisor_filter.py`

untracked 策略候选示例：

- `strategies/RegimeAwarePhase2CoreCombo.py`
- `strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py`
- `strategies/RegimeAwareV1129ResidualDragMicroSizer.py`
- `strategies/RegimeAwareV1119TailRiskCooldown.py`
- `strategies/RegimeAwareV1120*` 到 `strategies/RegimeAwareV1128*`
- `strategies/RegimeAwareV68*` 到 `strategies/RegimeAwareV119*`

人工确认问题：

- 该策略是否是研究候选、生产候选、还是回测副产物？
- 是否修改了当前 live/challenger 策略行为？
- 是否有配套测试和独立 config？
- 是否碰到 V10.8.2 或 V11.29 冻结面？

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- strategies
git -C D:\code\freqtrade-strategies diff --name-only -- strategies
```

限制：

- Codex 不得自动 stage、commit、格式化、删除、移动任何 `strategies/**`。

## 7. E 类：必须人工确认的 bot 配置

候选路径：

- `configs/btc_mvp/config.yaml`
- `user_data/config_btc_futures_phase2.json`
- `user_data/config_btc_futures_v67.json` 到 `user_data/config_btc_futures_v106.json`
- `user_data/config_multi_futures_v107.json` 到 `user_data/config_multi_futures_v1129.json`
- 任何 `user_data/config*.json`

人工确认问题：

- 是否包含 exchange、pair、stake、dry-run、API server、DB、port、strategy 映射变化？
- 是否属于 live/challenger bot 配置？
- 是否绑定 V10.8.2、V11.29 或 server 端观测面？
- 是否包含 credential-adjacent 字段，需要人工脱敏检查？

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- configs user_data/config*.json user_data/config_multi_futures_*.json
git -C D:\code\freqtrade-strategies diff --name-only -- configs user_data/config*.json user_data/config_multi_futures_*.json
```

限制：

- Codex 不得自动读取、修改、stage、commit 这些配置。
- 如需内容审查，必须先建立明确的 secret-safe 审查任务。

## 8. F 类：默认冻结的 V10.8.2 / V11.29 / live 配置

冻结路径/关键词：

- `strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py`
- `user_data/config_multi_futures_v1082.json`
- `reports/reliable_strategy_search_v1129/**`
- `strategies/RegimeAwareV1129ResidualDragMicroSizer.py`
- `user_data/config_multi_futures_v1129.json`
- `scripts/start_bot.sh`
- `scripts/ensure_dry_run_bots_started.sh`
- `scripts/check_system_health.sh`
- `scripts/check_trades.sh`
- `scripts/refresh_data.sh`
- `deploy/**`
- `dashboard/server.js`
- `dashboard/lib/config.js`
- `dashboard/public/**`
- `LIVE_TRADING.md`
- `DEPLOY.md`

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py strategies/RegimeAwareV1129ResidualDragMicroSizer.py user_data/config_multi_futures_v1082.json user_data/config_multi_futures_v1129.json reports/reliable_strategy_search_v1129 scripts deploy dashboard LIVE_TRADING.md DEPLOY.md
git -C D:\code\freqtrade-strategies diff --name-only -- scripts deploy dashboard LIVE_TRADING.md DEPLOY.md
```

限制：

- 默认不提交，不清理，不重命名，不移动。
- 需要单独人工批准后，才能进入版本候选审查或 server 操作审查。

## 9. G 类：禁止自动读取或处理的 secret / credential 路径

禁止路径/模式：

- `.env`
- `user_data/monitor.env`
- `*.pem`
- `*.key`
- `id_rsa`
- `id_ed25519`
- 任意含 `api_key`、`secret`、`password`、`token`、`credential` 的真实文件或字段。

人工命令建议：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- .env user_data/monitor.env
git -C D:\code\freqtrade-strategies ls-files --others --exclude-standard -- .env user_data/monitor.env
```

限制：

- Codex 不得读取内容。
- Codex 不得复制、移动、删除、stage、commit。
- 若这些路径出现在状态中，直接标记为 secret incident，由人工处理。

## 10. 推荐处理顺序

1. 冻结原始工作区：停止自动清理、自动 stash、自动 commit、自动格式化。
2. 建立只读清单：保留 `status --short`、`diff --name-only`、`diff --stat`、`ls-files --others` 输出作为审计证据。
3. 先处理 G 类：确认 secret 路径是否出现在 Git 状态中；如果出现，由人工处理。
4. 处理 C 类：只做 `.gitignore` 规则草案，不删除文件。
5. 分离 B 类：把回测/报告/原始产物作为证据保留，不提交。
6. 处理 A 类：提交文档、harness、审计基线。
7. 单独审查 D 类策略候选。
8. 单独审查 E 类 bot 配置。
9. 单独审查 F 类冻结面。
10. 每完成一类，重新运行只读状态命令，不进入下一类之前先人工确认。

## 11. 每一步的手工命令建议

基线快照：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all
git -C D:\code\freqtrade-strategies diff --name-only
git -C D:\code\freqtrade-strategies diff --stat
git -C D:\code\freqtrade-strategies ls-files --others --exclude-standard
```

A 类人工 stage：

```powershell
git -C D:\code\freqtrade-strategies add -- AGENTS.md docs reports/audits tasks README.md STRATEGY_GUIDE.md
git -C D:\code\freqtrade-strategies diff --cached --name-only
```

C 类 `.gitignore` 人工验证：

```powershell
git -C D:\code\freqtrade-strategies check-ignore -n reports/btc_mvp/backtests/latest.json
git -C D:\code\freqtrade-strategies check-ignore -n user_data/backtest_results/reliable_strategy_search_v11_data/BTC_USDT-1h.feather
```

D/E/F 类人工查看路径名：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- strategies configs user_data scripts deploy dashboard reports/reliable_strategy_search_v1129
git -C D:\code\freqtrade-strategies diff --name-only -- strategies configs user_data scripts deploy dashboard reports/reliable_strategy_search_v1129
```

最终人工确认：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all
git -C D:\code\freqtrade-strategies diff --stat
```

## 12. 绝对不能由 Codex 自动执行的动作

- `git stash`。
- `git add -A` 或 `git add .`。
- 对原始工作区执行任何 commit。
- 删除、移动、重命名、压缩或归档原始工作区文件。
- `git reset --hard`、`git clean`、`git checkout --`、`git restore`。
- 读取 `.env`、`user_data/monitor.env`、API key、交易所凭证、服务器密钥。
- 修改 `strategies/**`。
- 修改 `user_data/config*.json` 或任何 bot 配置。
- 修改 V10.8.2、V11.29、live、deploy、dashboard/server 操作面。
- 启动、停止、重启 bot。
- 登录服务器。
- 运行回测或下载行情数据。

## 13. 后续 Task 3 推荐

推荐 Task 3 只做一件事：在明确人工批准后，为原始工作区制定并验证 `.gitignore` 草案和 A 类文档提交清单。

建议边界：

- 仍然不清理、不删除、不移动、不 stash。
- 不触碰 `strategies/**`、`user_data/config*.json`、V10.8.2、V11.29、live/server 操作面。
- 只允许输出 `.gitignore` patch 草案和 `git add -- <explicit paths>` 白名单。
- 在执行任何 commit 前，必须展示 `git diff --cached --name-only`，由人工确认。

Task 3 不应处理 D/E/F/G 类；这些应拆成独立任务，并且每个任务都需要新的人工授权。
