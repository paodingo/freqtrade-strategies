# Task 9: Generated Ignore Verification Closure

结论：Task 8 已证明当前 `.gitignore` 覆盖了指定样例路径和大部分 generated/report/backtest/cache/data 产物，但覆盖尚不足以关闭 generated ignore 风险。仍有 361 个报告类路径未被当前规则覆盖，因此需要后续 Task 9R；本任务只补齐 closure 记录，不修改 `.gitignore`，不触碰原始脏工作区。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 当前 commit：`17dfcfe`
- Task 8 报告：`reports/audits/task8_generated_ignore_verification.md`
- Task 8 任务记录：`tasks/active/TASK-0008-generated-ignore-verification.md`

前置 gate：

```text
git status --short
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

## 2. Task 8 结论摘要

Task 8 的核心结论：

- 7 个指定 `git check-ignore` 样例路径全部被当前 clean `.gitignore` 覆盖。
- 原始脏工作区观察范围内共有 988 个 generated/report/backtest/cache/data 候选路径。
- 其中 627 个路径按当前 clean `.gitignore` 会被 ignore。
- 仍有 361 个报告类路径未被当前 `.gitignore` 覆盖。
- Task 8 建议后续只针对未覆盖的 generated/report 产物补充 `.gitignore`，并继续保留 `reports/audits/**`、`tasks/**`、`docs/**` 等审计、任务、文档基线不被忽略。

## 3. 当前 `.gitignore` 是否足够

判断：当前 `.gitignore` 对已明确识别的主要 generated/backtest/cache/data 家族有基本覆盖，但尚不足以完整覆盖 Task 8 观察到的 generated/report 产物。

已覆盖的关键规则包括：

- `.tmp_*/`
- `output/`
- `reports/btc_mvp/backtests/`
- `reports/reliable_strategy_search_*/`
- `reports/api_gap_backtest_candidates/`
- `user_data/backtest_results/`
- `user_data/alpha/`
- `*.sqlite`
- `*.db`
- `*.feather`
- `*.parquet`
- `*.zip`
- `*.tgz`
- `*.log`

不足点：Task 8 明确列出的部分 report 产物仍未被 ignore，尤其是 `reports/btc_mvp/phase2/**`。

## 4. 未覆盖路径判断

Task 8 已发现未覆盖路径，总数为 361。主要分布：

| 未覆盖路径组 | 数量 | 判断 |
|---|---:|---|
| `reports/btc_mvp/phase2/**` | 329 | generated/report 产物风险，需要 Task 9R 评估 |
| `reports/btc_mvp/experiments/**` | 6 | generated/report 产物风险，需要 Task 9R 评估 |
| `reports/reliable_strategy_search/**` | 2 | generated/report 产物风险，需要 Task 9R 评估 |
| `reports/live_window_execution_check/**` | 2 | generated/report 产物风险，需要 Task 9R 评估 |
| `reports/btc_mvp/phase1_remediation/**` | 2 | generated/report 产物风险，需要 Task 9R 评估 |
| `reports/btc_mvp/oi_collector/**` | 2 | generated/log 产物风险，需要 Task 9R 评估 |
| `reports/btc_mvp/paper/**` | 2 | generated/report 产物风险，需要 Task 9R 评估 |
| root-level `reports/v*.html` / `reports/v*.json` | 14 | 历史报告产物，需要 Task 9R 评估 |
| `reports/audits/**` | 2 | 不应 ignore；这是审计证据 |

## 5. 是否需要后续 Task 9R

需要 Task 9R。

Task 9R 建议只做 `.gitignore` 的窄范围修复，并继续遵守以下边界：

- 可以评估是否 ignore `reports/btc_mvp/phase2/raw/`、`reports/btc_mvp/experiments/`、`reports/btc_mvp/paper/`、`reports/btc_mvp/oi_collector/`、`reports/btc_mvp/phase1_remediation/`、`reports/live_window_execution_check/`、`reports/reliable_strategy_search/`。
- 可以评估 root-level `reports/v*.html` / `reports/v*.json` 是否属于 generated report。
- 不应 ignore `reports/audits/**`、`tasks/**`、`docs/**`、`AGENTS.md`、`README.md`。
- 不应修改策略、bot 配置、dashboard、deploy、secret 或 live/server 操作面。

本任务只给出建议，不执行 Task 9R。

## 6. `.gitignore` 修改声明

本任务未修改 `.gitignore`。

当前 closure 只引用 Task 8 的验证结论，不新增 ignore 规则，不删除现有规则，不调整任何生成产物路径。

## 7. 原始脏工作区处理声明

本任务未触碰原始脏工作区 `D:\code\freqtrade-strategies`。

执行边界：

- 未修改原始脏工作区中的任何文件
- 未复制文件
- 未删除文件
- 未移动文件
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未进入 Task 10

## 8. 是否允许进入 Task 10

判断：不建议直接进入 Task 10。

原因：Task 9 closure 明确确认 generated ignore 覆盖尚不足，且需要 Task 9R。若现在进入 Task 10，里程碑复盘会带着一个已知、可修复的 generated/report 污染风险。

推荐顺序：

1. 执行 Task 9R：窄范围修复 `.gitignore` 的未覆盖 generated/report 产物规则。
2. 重新运行 generated ignore verification。
3. Task 9R commit 后，再进入 Task 10 里程碑复盘。
