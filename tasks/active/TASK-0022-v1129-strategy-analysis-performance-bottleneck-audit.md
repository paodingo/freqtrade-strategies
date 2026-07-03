# TASK-0022: V11.29 Strategy Analysis Performance Bottleneck Audit

## Goal

Read-only audit why V11.29 strategy analysis can take too long and whether the 4h fallback/regime path is a likely bottleneck.

## Preconditions

- Task 21A committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task22_v1129_strategy_analysis_performance_bottleneck_audit.md`
- `tasks/active/TASK-0022-v1129-strategy-analysis-performance-bottleneck-audit.md`

## Forbidden files and surfaces

- `strategies/**` modifications
- `user_data/**` modifications
- `configs/**` modifications
- `dashboard/**` modifications
- `deploy/**` modifications
- bot lifecycle scripts
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- live/server write operation surface

## Execution boundaries

- Read-only SSH allowed.
- Read-only server logs and stats allowed.
- Read-only container micro-benchmark allowed.
- Do not modify strategy or config files.
- Do not download data.
- Do not start, stop, or restart containers.
- Do not run backtests.
- Do not claim V11.29 passed validation or can replace V10.8.2.

## Completed work

- Confirmed V11.29 had one 225.62s strategy analysis warning in recent logs.
- Confirmed running containers are now V11.29 and V10.8.2 only.
- Identified full-history 4h regime loop as the main structural bottleneck candidate.
- Ran read-only micro-benchmark showing about 15.64s for the 12-pair 4h fallback/regime path alone.
- Recommended a future fix-plan task before any code edits.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not enter Task 22R or Task 23 without explicit user instruction.
