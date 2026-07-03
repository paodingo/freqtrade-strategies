# TASK-0022W: V11.29 Post-Deploy Start Observation

## Goal

Attempt to start only `freqtrade-v1129` after Task 22V deployment, without reading secrets, and observe whether the bot enters `RUNNING`.

## Preconditions

- Task 22V committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.
- User authorized continuing to the next step.

## Allowed operations

- SSH to `ubuntu@43.134.72.69`.
- Check hostname/date/container state.
- Attempt unauthenticated local `/api/v1/start`.
- Read recent V11.29 logs.
- Write this task record and audit report.

## Forbidden operations

- Read `.env`.
- Read `user_data/monitor.env`.
- Print or copy API keys, passwords, tokens, exchange credentials, server key content, or dashboard password.
- Modify bot config.
- Modify strategies.
- Modify dashboard or deploy files.
- Restart `freqtrade-v1082`.
- Start/stop/restart legacy containers.
- Run backtests.

## Completed work

- Confirmed local worktree and readiness.
- Confirmed server and container state.
- Confirmed `freqtrade-v1129` remains `STOPPED`.
- Attempted unauthenticated `/api/v1/start`.
- Observed `401 Unauthorized`.
- Did not read credentials and did not perform authenticated start.

## Stop condition

Stop after report, verification, commit, and push. Do not enter Task 22X without explicit authorization for a credential-safe start path.

