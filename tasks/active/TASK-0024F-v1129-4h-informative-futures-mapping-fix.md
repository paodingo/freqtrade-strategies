# TASK-0024F: V11.29 4h Informative Futures Mapping Fix

## Goal

Implement the minimum V11.29 strategy-code fix recommended by Task 24A.

## Preconditions

- Task 24A committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.
- User authorized entering the implementation step.

## Allowed files

- `strategies/regime_aware_base.py`
- `reports/audits/task24f_v1129_4h_informative_futures_mapping_fix.md`
- `tasks/active/TASK-0024F-v1129-4h-informative-futures-mapping-fix.md`

## Forbidden operations

- Modify bot configs.
- Modify dashboard or deploy files.
- Read `.env`.
- Read `user_data/monitor.env`.
- Print secrets.
- Start, stop, or restart bots.
- Run backtests.
- Change entry/exit/stake/risk rules.
- Claim V11.29 replacement readiness.

## Completed work

- Imported `CandleType`.
- Added `informative_pairs()` returning `(pair, "4h", CandleType.FUTURES)`.
- Changed `_load_4h()` to call `get_pair_dataframe(..., candle_type="futures")`.
- Kept local futures feather fallback unchanged.

## Verification commands

```powershell
& 'C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile strategies/regime_aware_base.py
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification, commit, and push. Do not deploy to server and do not enter Task 24V without separate authorization.

