# TASK-0059: V11.30 Crash Rebound Shadow Implementation Plan

## Objective

Create a plan-only implementation path for V11.30 Crash Rebound Long Shadow,
based on Task 58 candidate selection.

## Preconditions

- Current directory: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Task 58 committed and pushed
- `git status --short --untracked-files=all` was clean before writing
- `.\scripts\run_agent_readiness_checks.ps1` passed before writing

## Allowed Changes

- `reports/audits/task59_v1130_crash_rebound_shadow_implementation_plan.md`
- `tasks/active/TASK-0059-v1130-crash-rebound-shadow-implementation-plan.md`

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

## Result

Plan created for:

- V11.30 long-only crash-rebound shadow strategy;
- clean-worktree base class `RegimeAwareV66AlphaRisk`;
- small dry-run config;
- TDD implementation;
- exact guard exception first;
- later deployment/start split into separate tasks.

## Recommended Next Task

Task 60R: `V11.30 Crash Rebound Guard Exception`

This must be completed before strategy/config implementation because current
guards block `strategies/**` and `user_data/**` by default.

