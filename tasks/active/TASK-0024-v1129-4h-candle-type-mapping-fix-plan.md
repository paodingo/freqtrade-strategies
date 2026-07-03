# TASK-0024: V11.29 4h Candle Type Mapping Fix Plan

## Goal

Create a safe plan to fix the remaining V11.29 `No data found for (..., 4h, )` DataProvider warning without changing trading rules.

## Preconditions

- Task 23 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task24_v1129_4h_candle_type_mapping_fix_plan.md`
- `tasks/active/TASK-0024-v1129-4h-candle-type-mapping-fix-plan.md`

## Forbidden operations

- Modify strategies.
- Modify bot configs.
- Modify dashboard or deploy files.
- Read `.env`.
- Read `user_data/monitor.env`.
- Print secrets.
- Start, stop, or restart bots.
- Run backtests.
- Claim V11.29 replacement readiness.

## Completed work

- Reviewed Task 21A and Task 23 evidence.
- Confirmed the remaining warning is likely caused by an empty candle type DataProvider lookup.
- Defined fix options:
  - explicit futures candle type;
  - skip noisy DataProvider lookup and use verified futures feather fallback;
  - hybrid probe plus fallback.
- Recommended Task 24A signature inspection before code changes.

## Stop condition

Stop after report, verification, commit, and push. Do not enter Task 24A automatically.

