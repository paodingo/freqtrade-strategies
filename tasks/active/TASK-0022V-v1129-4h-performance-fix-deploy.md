# TASK-0022V: V11.29 4h Performance Fix Deploy

## Goal

Deploy the Task 22F bounded 4h regime lookback fix to the server-side V11.29 dry-run container and observe immediate runtime state.

## Preconditions

- Task 22F committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Local worktree clean before edits.
- Readiness checks passed before edits.
- User authorized executing the next deployment step.

## Allowed operations

- SSH to `ubuntu@43.134.72.69`.
- Check hostname/date/container state.
- Backup `freqtrade-v1129` container copy of `/freqtrade/project/strategies/regime_aware_base.py`.
- Copy local `strategies/regime_aware_base.py` to `freqtrade-v1129`.
- Restart only `freqtrade-v1129`.
- Read logs and read-only SQLite counts.
- Write this task record and audit report.

## Forbidden operations

- Read `.env`.
- Read `user_data/monitor.env`.
- Print or copy API keys, exchange credentials, server keys, tokens, or dashboard passwords.
- Modify bot config.
- Modify dashboard.
- Modify deploy scripts.
- Restart `freqtrade-v1082`.
- Start/stop/restart `freqtrade-v1127` or `freqtrade-v1116`.
- Run backtests.
- Produce V11.29 replacement conclusion.

## Completed work

- Verified local clean worktree and readiness before deployment.
- Recorded local source hash.
- Confirmed server identity and V11.29/V10.8.2 container state.
- Backed up the pre-deploy V11.29 strategy base file inside the container.
- Copied the patched `regime_aware_base.py` into `freqtrade-v1129`.
- Restarted only `freqtrade-v1129`.
- Confirmed `freqtrade-v1082` remained running.
- Confirmed deployed file hash matches local hash.
- Observed V11.29 internal state is `STOPPED`.
- Confirmed V11.29 SQLite remains `trades=0`, `orders=0`.

## Stop condition

Stop after report, verification, commit, and push. Do not start the stopped bot without separate explicit authorization.

