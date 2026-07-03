# Task 8: Generated Evidence Ignore Verification

结论：当前 clean worktree 的 `.gitignore` 已覆盖 Task 8 指定的 7 个 generated/report/backtest/cache/data 样例路径，也覆盖原始脏工作区观察范围内 627 个候选路径；但仍有 361 个报告类路径未被当前规则覆盖。建议后续 Task 8R 只针对这些未覆盖的 generated/report 产物补充 `.gitignore`，同时继续保留 `reports/audits/**`、`tasks/**`、`docs/**` 等可审计文档路径不被忽略。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 7S commit：`e1bec02 Migrate approved agent operating docs`
- 原始脏工作区：`D:\code\freqtrade-strategies`

前置 gate：

```text
git status --short
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

## 2. 当前 `.gitignore` 规则覆盖情况

本任务只读查看当前 clean worktree 的 `.gitignore`。相关 generated/data/cache 规则如下：

```text
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

用户给定的 `git check-ignore -n <path>` 在本机 Git 上返回：

```text
fatal: --non-matching is only valid with --verbose
```

因此本任务使用等价只读命令 `git check-ignore -v -n <path>` 继续验证。结果：

| 路径 | 覆盖规则 |
|---|---|
| `reports/btc_mvp/backtests/latest.json` | `.gitignore:18:reports/btc_mvp/backtests/` |
| `reports/reliable_strategy_search_v1129/some-placeholder` | `.gitignore:19:reports/reliable_strategy_search_*/` |
| `reports/api_gap_backtest_candidates/backtest-result-placeholder.json` | `.gitignore:20:reports/api_gap_backtest_candidates/` |
| `user_data/backtest_results/some-placeholder.json` | `.gitignore:21:user_data/backtest_results/` |
| `user_data/alpha/some-placeholder.json` | `.gitignore:22:user_data/alpha/` |
| `output/some-placeholder.png` | `.gitignore:17:output/` |
| `.tmp_v1127_analysis/some-placeholder.json` | `.gitignore:16:.tmp_*/` |

## 3. 已被 ignore 的 generated/report/backtest/cache/data 路径

对原始脏工作区只读观察命令：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- reports output .tmp_v1127_analysis .tmp_v1128_analysis user_data/backtest_results user_data/alpha
```

将观察到的 988 个路径按当前 clean `.gitignore` 规则批量验证后，627 个路径会被 ignore：

| 覆盖规则 | 数量 |
|---|---:|
| `reports/btc_mvp/backtests/` | 440 |
| `reports/reliable_strategy_search_*/` | 124 |
| `user_data/backtest_results/` | 45 |
| `.tmp_*/` | 7 |
| `output/` | 6 |
| `reports/api_gap_backtest_candidates/` | 4 |
| `user_data/alpha/` | 1 |

判断：当前 `.gitignore` 已覆盖主要 backtest result、strategy search versioned reports、临时分析目录、output、API gap backtest candidate、backtest data 和 alpha data 产物。

## 4. 仍未被 ignore 的路径

批量验证中仍有 361 个路径未被当前 clean `.gitignore` 覆盖。主要分布：

| 未覆盖路径组 | 数量 | 示例 |
|---|---:|---|
| `reports/btc_mvp/phase2/**` | 329 | `reports/btc_mvp/phase2/phase2_summary.json`、`reports/btc_mvp/phase2/raw/..._trades.json` |
| `reports/btc_mvp/experiments/**` | 6 | `reports/btc_mvp/experiments/latest.json` |
| `reports/reliable_strategy_search/**` | 2 | `reports/reliable_strategy_search/backtest-result-latest.json` |
| `reports/live_window_execution_check/**` | 2 | `reports/live_window_execution_check/live_window_execution_check.json` |
| `reports/btc_mvp/phase1_remediation/**` | 2 | `reports/btc_mvp/phase1_remediation/phase1_remediation_report.json` |
| `reports/btc_mvp/oi_collector/**` | 2 | `reports/btc_mvp/oi_collector/collector.err.log` |
| `reports/btc_mvp/paper/**` | 2 | `reports/btc_mvp/paper/latest.json` |
| root-level `reports/v*.html` / `reports/v*.json` | 14 | `reports/v84_system_acceptance_20260613.html` |
| `reports/audits/**` | 2 | `reports/audits/git_worktree_inventory.md`、`reports/audits/harness_readiness_audit.md` |

注意：`reports/audits/**` 不应作为 generated 产物忽略；它们是审计证据，应继续可提交。其余未覆盖项大多属于报告产物或历史实验输出，适合后续 Task 8R 逐项评估是否补充 ignore。

## 5. 是否需要后续 Task 8R 修改 `.gitignore`

需要 Task 8R，但应保持窄范围。

建议 Task 8R 只评估并可能添加 generated/report 产物规则，例如：

- `reports/btc_mvp/phase2/raw/`
- `reports/btc_mvp/experiments/`
- `reports/btc_mvp/paper/`
- `reports/btc_mvp/oi_collector/`
- `reports/btc_mvp/phase1_remediation/`
- `reports/live_window_execution_check/`
- `reports/reliable_strategy_search/`
- 必要时评估 root-level `reports/v*.html` / `reports/v*.json`

Task 8R 不应忽略：

- `reports/audits/**`
- `tasks/**`
- `docs/**`
- `AGENTS.md`
- `README.md`
- 任何需要人工审计或任务追踪的文档基线

## 6. 原始工作区处理声明

本任务没有删除、移动、清理任何原始文件。

执行边界：

- 未修改原始工作区 `D:\code\freqtrade-strategies` 中的任何文件
- 未删除任何文件
- 未移动任何文件
- 未 stash
- 未 commit 原始工作区
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未修改 `.gitignore`
- 未进入 Task 9

## 7. 后续 Task 9 推荐

推荐 Task 9：在 Task 8R 完成并 commit 后，重新运行 generated ignore verification，确认原始脏工作区中 generated/report/backtest/cache/data 类路径不再污染迁移候选视图，同时继续保留审计、任务和文档基线为显式可提交路径。
