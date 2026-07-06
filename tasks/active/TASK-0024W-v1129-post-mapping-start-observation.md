# TASK-0024W: V11.29 Post-Mapping Start Observation

## Goal

Start only `freqtrade-v1129` after Task 24V and observe whether the fresh runtime cycle still emits 4h DataProvider warnings.

## Preconditions

- Task 24V committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.
- User authorized continuing to the next step.

## Allowed operations

- SSH to `ubuntu@43.134.72.69`.
- Read V11.29 API username/password from the already authorized config source in memory only.
- Call `POST /api/v1/start` on `localhost:8122`.
- Read recent logs.
- Read V11.29 and V10.8.2 API health.
- Write this task record and audit report.

## Forbidden operations

- Print credentials.
- Read `.env`.
- Read `user_data/monitor.env`.
- Modify bot config.
- Modify strategies.
- Restart bots.
- Touch stopped legacy containers.
- Run backtests.
- Claim V11.29 replacement readiness.

## Completed work

- Authenticated V11.29 start returned `HTTP_STATUS=200`.
- Observed V11.29 transition to `RUNNING`.
- Confirmed V11.29 API endpoints return `200`.
- Observed no fresh `No data found for (..., 4h, )` warning in the checked window.
- Confirmed V11.29 SQLite remains `trades=0`, `orders=0`.
- Confirmed dashboard lane health mismatch: `8109` and `8120` are down, while `8091` and `8122` are healthy.

## Stop condition

Stop after report, verification, commit, and push. Do not enter Task 25 automatically.

