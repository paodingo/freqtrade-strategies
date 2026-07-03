# TASK-0022X: Authorized V11.29 API Start and Runtime Observation

## Goal

Start only `freqtrade-v1129` using an explicitly authorized credential-safe path, then observe initial runtime state after Task 22F/22V deployment.

## Preconditions

- Task 22W committed and pushed.
- User selected authorization path 2.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Authorized credential source

Read only these fields from:

```text
freqtrade-v1129:/freqtrade/project/user_data/config_multi_futures_v1129.json
```

Fields:

- `api_server.username`
- `api_server.password`

Do not print secret values.

## Allowed operations

- SSH to `ubuntu@43.134.72.69`.
- Read the two authorized API credential fields in memory.
- Call local V11.29 API start endpoint.
- Read recent logs.
- Read-only query V11.29 SQLite counts.
- Write this task record and audit report.

## Forbidden operations

- Print credentials.
- Read `.env`.
- Read `user_data/monitor.env`.
- Modify bot config.
- Modify strategies.
- Restart `freqtrade-v1082`.
- Stop/restart `freqtrade-v1129`.
- Touch `freqtrade-v1127` or `freqtrade-v1116`.
- Run backtests.
- Claim replacement readiness.

## Completed work

- Authenticated `/api/v1/start` returned `HTTP_STATUS=200`.
- Observed `freqtrade-v1129` transition to `RUNNING`.
- Confirmed `freqtrade-v1082` remained running.
- Observed no `Strategy analysis took ...` warning in the short window.
- Observed continued 4h DataProvider warnings.
- Confirmed V11.29 SQLite remains `trades=0`, `orders=0`.

## Stop condition

Stop after report, verification, commit, and push. Do not enter Task 23 without separate authorization.

