# TASK-0008: Generated Evidence Ignore Verification

状态：已完成验证，未修改 `.gitignore`，未进入 Task 9。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

验证当前 `.gitignore` 是否能覆盖原始脏工作区中的 generated/report/backtest/cache/data 类产物，并生成验证报告。

## 前置条件结果

- Task 7S：通过，commit `e1bec02 Migrate approved agent operating docs`
- `git status --short`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 只读检查

已验证用户给定的 7 个样例路径。由于本机 Git 对 `git check-ignore -n` 要求同时使用 `--verbose`，实际使用：

```powershell
git check-ignore -v -n <path>
```

也已只读观察原始工作区：

```powershell
git -C D:\code\freqtrade-strategies status --short --untracked-files=all -- reports output .tmp_v1127_analysis .tmp_v1128_analysis user_data/backtest_results user_data/alpha
```

## 结果摘要

- 样例路径：7/7 已被当前 clean `.gitignore` 覆盖
- 原始工作区候选路径：988 个
- 按当前 clean `.gitignore` 会被 ignore：627 个
- 仍未被 ignore：361 个
- 是否需要 Task 8R：需要，建议只补 generated/report 产物规则，不能忽略审计、任务和文档基线

## 本任务允许修改

- `reports/audits/task8_generated_ignore_verification.md`
- `tasks/active/TASK-0008-generated-ignore-verification.md`

## 本任务未执行

- 未修改 `.gitignore`
- 未修改原始工作区 `D:\code\freqtrade-strategies`
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
- 未进入 Task 9

## 输出

- `reports/audits/task8_generated_ignore_verification.md`
