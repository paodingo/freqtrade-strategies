# Task 9R: Generated Ignore Patch

结论：已按 Task 8/9 的 generated report gap 做最小 `.gitignore` 修补。新增规则只覆盖 generated/report/backtest/cache/data 类路径，没有使用 `reports/` 总规则，没有 ignore `reports/audits/*.md`、`tasks/**/*.md` 或 `docs/**/*.md`，未触碰原始脏工作区。

## 1. Task 8/9 未覆盖摘要

Task 8/9 记录的关键事实：

- Task 8 的 7 个样例路径全部已被原有 `.gitignore` 覆盖。
- 原始脏工作区观察范围内共有 988 个 generated/report/backtest/cache/data 候选路径。
- 原有 `.gitignore` 可覆盖 627 个路径。
- 仍有 361 个报告类路径未覆盖。
- 不能 ignore `reports/audits/**`、`tasks/**`、`docs/**`、`AGENTS.md`、`README.md`。

未覆盖路径主要包括：

- `reports/btc_mvp/phase2/**`
- `reports/btc_mvp/experiments/**`
- `reports/reliable_strategy_search/**`
- `reports/live_window_execution_check/**`
- `reports/btc_mvp/phase1_remediation/**`
- `reports/btc_mvp/oi_collector/**`
- `reports/btc_mvp/paper/**`
- root-level `reports/v*.html` / `reports/v*.json`

## 2. 本次新增的 `.gitignore` 规则

新增规则：

```text
reports/btc_mvp/experiments/
reports/btc_mvp/oi_collector/
reports/btc_mvp/paper/
reports/btc_mvp/phase1_remediation/
reports/btc_mvp/phase2/
reports/live_window_execution_check/
reports/reliable_strategy_search/
reports/v*.html
reports/v*.json
```

## 3. 每条规则对应路径类别

| 新增规则 | 覆盖 Task 8/9 路径类别 |
|---|---|
| `reports/btc_mvp/experiments/` | `reports/btc_mvp/experiments/**` 历史实验报告产物 |
| `reports/btc_mvp/oi_collector/` | `reports/btc_mvp/oi_collector/**` collector log/report 产物 |
| `reports/btc_mvp/paper/` | `reports/btc_mvp/paper/**` paper run report 产物 |
| `reports/btc_mvp/phase1_remediation/` | `reports/btc_mvp/phase1_remediation/**` phase1 remediation report 产物 |
| `reports/btc_mvp/phase2/` | `reports/btc_mvp/phase2/**` phase2 summary/raw report 产物 |
| `reports/live_window_execution_check/` | `reports/live_window_execution_check/**` live-window check report 产物 |
| `reports/reliable_strategy_search/` | non-versioned `reports/reliable_strategy_search/**` report 产物 |
| `reports/v*.html` | root-level historical `reports/v*.html` report 产物 |
| `reports/v*.json` | root-level historical `reports/v*.json` report 产物 |

## 4. 明确未 ignore 的路径类别

本任务没有新增以下规则：

- 没有 `reports/`
- 没有 `reports/audits/`
- 没有 `reports/audits/*.md`
- 没有 `tasks/`
- 没有 `tasks/**/*.md`
- 没有 `docs/`
- 没有 `docs/**/*.md`

审计报告、任务记录、docs、`AGENTS.md`、`README.md` 仍然保持可提交。

## 5. `git check-ignore` 验证结果

本机 Git 对用户要求的 `git check-ignore -n <path>` 返回：

```text
fatal: --non-matching is only valid with --verbose
```

因此使用等价可解释形式 `git check-ignore -v -n <path>` 验证。

原有样例路径仍被 ignore：

```text
.gitignore:18:reports/btc_mvp/backtests/ reports/btc_mvp/backtests/latest.json
.gitignore:26:reports/reliable_strategy_search_*/ reports/reliable_strategy_search_v1129/example.json
.gitignore:27:reports/api_gap_backtest_candidates/ reports/api_gap_backtest_candidates/backtest-result-placeholder.json
.gitignore:30:user_data/backtest_results/ user_data/backtest_results/example.json
.gitignore:31:user_data/alpha/ user_data/alpha/example.json
.gitignore:17:output/ output/example.png
.gitignore:16:.tmp_*/ .tmp_v1127_analysis/example.json
```

Task 8/9 gap 代表路径已被新增规则覆盖：

```text
.gitignore:23:reports/btc_mvp/phase2/ reports/btc_mvp/phase2/phase2_summary.json
.gitignore:23:reports/btc_mvp/phase2/ reports/btc_mvp/phase2/raw/example_trades.json
.gitignore:19:reports/btc_mvp/experiments/ reports/btc_mvp/experiments/latest.json
.gitignore:25:reports/reliable_strategy_search/ reports/reliable_strategy_search/backtest-result-latest.json
.gitignore:24:reports/live_window_execution_check/ reports/live_window_execution_check/live_window_execution_check.json
.gitignore:22:reports/btc_mvp/phase1_remediation/ reports/btc_mvp/phase1_remediation/phase1_remediation_report.json
.gitignore:20:reports/btc_mvp/oi_collector/ reports/btc_mvp/oi_collector/collector.err.log
.gitignore:21:reports/btc_mvp/paper/ reports/btc_mvp/paper/latest.json
.gitignore:28:reports/v*.html reports/v84_system_acceptance_20260613.html
.gitignore:29:reports/v*.json reports/v97_v101_small_account_comparison_20260613.json
```

不应被 ignore 的路径未被 ignore，`git check-ignore -v -n` 输出 `::`：

```text
:: reports/audits/task9_generated_ignore_closure.md
:: tasks/active/TASK-0009-generated-ignore-closure.md
:: docs/agent_operating_playbook.md
```

## 6. 仍未覆盖的路径

使用原始脏工作区同一只读观察范围重新批量验证：

```text
TOTAL=988
MATCHED=986
UNMATCHED=2
```

仍未覆盖的 2 个路径：

```text
reports/audits/git_worktree_inventory.md
reports/audits/harness_readiness_audit.md
```

判断：这 2 个是审计基线，按任务要求不应被 ignore。因此 generated/report/backtest/cache/data 类 gap 已关闭；未覆盖项是刻意保留的可提交审计证据。

## 7. 是否可以进入 Task 10

判断：Task 9R commit 后可以进入 Task 10。

进入 Task 10 前仍需满足：

- 当前分支为 `codex/btc-mvp-system-harnessed`
- `git status --short` 为空
- `.\scripts\run_agent_readiness_checks.ps1` 通过

## 8. 后续建议

推荐后续 Task 10：执行 harness migration milestone review，复盘 Task 1 到 Task 9R 已完成能力、仍未处理的原始脏工作区风险，以及是否可以进入策略候选只读审查和 bot 配置只读审查。

本任务未进入 Task 10。

## 9. 执行边界

- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未删除任何文件
- 未移动任何文件
- 未 stash
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未使用过宽 `reports/` ignore 规则
