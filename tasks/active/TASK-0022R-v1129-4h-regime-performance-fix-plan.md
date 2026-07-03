# TASK-0022R: V11.29 4h Regime Performance Fix Plan

## Goal

Create a safe implementation plan for fixing the V11.29 4h regime analysis bottleneck without modifying strategy code in this task.

## Preconditions

- Task 22 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task22r_v1129_4h_regime_performance_fix_plan.md`
- `tasks/active/TASK-0022R-v1129-4h-regime-performance-fix-plan.md`

## Forbidden files and surfaces

- `strategies/**` modifications
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- bot lifecycle scripts
- `.env`
- `user_data/monitor.env`
- server write operations

## Completed work

- Defined bounded 4h lookback as the recommended first patch.
- Deferred cache and candle type mapping cleanup to later tasks.
- Defined verification requirements and deployment separation.
- Recommended `Task 22F` as the next implementation task, requiring explicit strategy-code authorization.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification, commit, and push. Do not modify strategy code in this task.
