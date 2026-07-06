# TASK-0031: V11.29 Safe Runtime Data Freshness Probe

## Goal

Use strictly read-only server/runtime evidence to determine whether V11.29 is receiving fresh `15m` and `4h` candle data, and whether zero trades are better explained by data absence or by zero final entry signals.

## Preconditions

- Task 30 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task31_v1129_runtime_data_freshness_probe.md`
- `tasks/active/TASK-0031-v1129-runtime-data-freshness-probe.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**` bot configs
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- V10.8.2 strategy/config
- V11.29 strategy/config
- SQLite snapshot files
- live trading operations

## Completed Work

- Verified clean worktree and readiness before edits.
- Read Task 30 telemetry report.
- Used read-only SSH access.
- Checked V11.29 container status.
- Checked V11.29 API endpoint health.
- Identified `pair_candles?pair=<pair>&timeframe=15m&limit=<n>` as the safe runtime dataframe endpoint.
- Probed all 12 V11.29 whitelist pairs for 24h `15m` runtime data.
- Confirmed runtime `15m` data is current-day and includes embedded `4h` context.
- Confirmed observed 24h final `enter_long` / `enter_short` counts are zero for all pairs.
- Documented that stale local fallback data is not the same as missing runtime data.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 32 automatically.
