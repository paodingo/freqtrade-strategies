# TASK-0025: Dashboard Runtime Topology Repair

## Goal

Repair server dashboard runtime topology so the visible bot lanes match the currently running bots.

## Preconditions

- Task 24W committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.
- User authorized continuing to the next step.

## Allowed operations

- SSH to `ubuntu@43.134.72.69`.
- Read non-secret dashboard runtime topology.
- Write a systemd drop-in for `freqtrade-monitor.service`.
- Restart only `freqtrade-monitor.service`.
- Verify non-secret process environment and API health.
- Write this task record and audit report.

## Forbidden operations

- Read `.env`.
- Read or print `user_data/monitor.env`.
- Print dashboard password or API credentials.
- Modify strategies.
- Modify bot configs.
- Start, stop, or restart trading bots.
- Run backtests.
- Claim V11.29 replacement readiness.

## Completed work

- Confirmed old dashboard lanes pointed to stopped `8109` and `8120`.
- Confirmed active lanes are `8122` for V11.29 and `8091` for V10.8.2.
- Added dashboard systemd drop-in `35-exec-current-v1129-v1082-topology.conf`.
- Restarted dashboard service only.
- Confirmed dashboard process env now uses V11.29 as base and V10.8.2 as benchmark.
- Confirmed trading bot containers were not changed.

## Stop condition

Stop after report, verification, commit, and push. Do not enter Task 26 automatically.

