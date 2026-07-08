# TASK-0058: V11.30 Candidate Selection

## Objective

Select the next V11.30 candidate direction based on Task 57 high-volatility replay evidence, without modifying strategies, bot configs, or runtime state.

## Preconditions

- Current directory: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Task 57 committed and pushed
- `git status --short --untracked-files=all` was clean before writing
- `.\scripts\run_agent_readiness_checks.ps1` passed before writing

## Allowed Changes

- `reports/audits/task58_v1130_candidate_selection.md`
- `tasks/active/TASK-0058-v1130-candidate-selection.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key、交易所凭证、服务器密钥、dashboard 密码
- V10.8.2 strategy/config
- V11.29 strategy/config
- live/server runtime state
- original dirty workspace `D:\code\freqtrade-strategies`

## Evidence Used

- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json`
- Read-only `freqtrade-v1129` local API `/api/v1/pair_candles`
- Temporary crash-rebound gate exploration script; deleted after use

## Result

Selected next candidate:

- `V11.30 Crash Rebound Long Shadow`

Rejected as primary candidates:

- `blowoff_short`
- `selloff_continuation`
- direct V11.29 gate loosening

## Verification

Required:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Recommended Next Task

Task 59: `V11.30 Crash Rebound Shadow Implementation Plan`

Task 59 should still be a plan only. Strategy/config implementation must be authorized separately after the plan.

