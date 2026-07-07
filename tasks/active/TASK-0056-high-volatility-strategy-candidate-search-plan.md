# TASK-0056: High-Volatility Strategy Candidate Search Plan

## Objective

基于 Task 55 的 V11.29 live signal miss 根因审计，制定下一代高波动策略候选搜索计划，并用只读 live dataframe 粗筛最近强波动窗口中的候选事件。

## Preconditions

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- `git status --short --untracked-files=all` 在写入前为空
- `.\scripts\run_agent_readiness_checks.ps1` 在写入前通过
- Task 55 已提交并推送

## Allowed Changes

- `reports/audits/task56_high_volatility_strategy_candidate_search_plan.md`
- `tasks/active/TASK-0056-high-volatility-strategy-candidate-search-plan.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key、交易所凭证、服务器密钥、dashboard 密码
- V10.8.2 策略/config
- V11.29 策略/config
- live/server 运行面
- 原始脏工作区 `D:\code\freqtrade-strategies`

## Read-Only Evidence

只读检查 `freqtrade-v1129` API：

- `/api/v1/whitelist`
- `/api/v1/pair_candles?timeframe=15m&limit=672`

统计范围：

- 12 个 pair；
- 约 7560 根 15m dataframe 行；
- 只在临时脚本中计算 candidate counts，临时脚本已删除。

## Result

粗筛结果：

- `final_entry=0`
- `high_volatility=43`
- `selloff_continuation_candidate=110`
- `blowoff_short_candidate=1064`
- `shadow_core=160`
- `base_ranging_short=1`
- `high_adx=6404`

结论：

- V11.29 当前 entry/gate 体系对高波动行情响应不足；
- 下一代策略应优先研究 high-ADX selloff continuation、blowoff short/exhaustion fade、crash rebound long；
- 不能直接改 live 策略，必须先做 replay harness。

## Recommended Next Task

Task 57：`High-Volatility Replay Harness`

目标：

- 新增只读 replay 脚本；
- 对候选事件计算 forward return；
- 输出 JSON/Markdown scorecard；
- 决定是否进入 V11.30 candidate selection。

