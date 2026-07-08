# TASK-0057: High-Volatility Replay Harness

## Objective

实现并运行一个只读 high-volatility replay harness，对 Task 56 提出的候选事件族计算 forward-return scorecard，为 V11.30 候选选择提供证据。

## Preconditions

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 56 已提交
- `git status --short --untracked-files=all` 在写入前为空
- `.\scripts\run_agent_readiness_checks.ps1` 在写入前通过

## Allowed Changes

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `tests/test_v1129_high_volatility_replay_harness.js`
- `scripts/build_v1129_high_volatility_replay_harness.js`
- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json`
- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.md`
- `reports/audits/task57_high_volatility_replay_harness.md`
- `tasks/active/TASK-0057-high-volatility-replay-harness.md`

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

## Verification Commands

Executed:

```powershell
node --test tests/test_v1129_high_volatility_replay_harness.js
node --check scripts/build_v1129_high_volatility_replay_harness.js
node scripts/build_v1129_high_volatility_replay_harness.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Result

Replay generated:

- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json`
- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.md`

Key result:

- `crash_rebound` is currently the best rough candidate by 4-candle fee-adjusted mean bps.
- `blowoff_short` and `selloff_continuation` are negative under rough gates.
- This does not authorize strategy/config changes or live trading.

## Recommended Next Task

Task 58：`V11.30 Candidate Selection`

