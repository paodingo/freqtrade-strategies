# TASK-0021: V11.29 4h Data Availability Root-Cause Plan

## Goal

Read-only determine why V11.29 logs repeated `No data found for (..., 4h, )` while server data files appear to contain futures `4h` feather files.

## Preconditions

- Task 20S-STOP committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task21_v1129_4h_data_availability_root_cause_plan.md`
- `tasks/active/TASK-0021-v1129-4h-data-availability-root-cause-plan.md`

## Forbidden files and surfaces

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- bot lifecycle scripts
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- live/server write operation surface

## Execution boundaries

- Read-only SSH allowed.
- Read-only `docker logs` and `docker exec python` metadata checks allowed.
- Do not download data.
- Do not modify data files.
- Do not read secrets.
- Do not start, stop, or restart containers.
- Do not run backtests.
- Do not modify strategy or config files.

## Completed work

- Confirmed V11.29 still logs repeated `No data found for (..., 4h, )` for all 12 observed pairs.
- Confirmed futures `4h` feather files exist for all 12 observed pairs.
- Confirmed files are readable and contain about 5486 `4h` rows each.
- Confirmed latest observed `4h` candle in files is `2026-07-03 04:00:00+00:00`.
- Concluded that the root cause is not simply total absence of files.
- Recommended a non-secret config and informative mapping audit before any data refresh.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not enter Task 21A without explicit user instruction.
