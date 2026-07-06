# TASK-0027: Runtime State Truth Monitor

## Goal

Separate container uptime, API readability, bot running state, and trade/order observation in the trade monitor state.

## Motivation

V11.29 container uptime was previously easy to misread as true bot trading runtime. Read-only evidence showed the container was `Up 2 days`, but bot state changed from `STOPPED` to `RUNNING` only on 2026-07-06 11:53:30 CST.

## Allowed Changes

- `scripts/check_trades.sh`
- `reports/audits/task27_runtime_state_truth_monitor.md`
- `tasks/active/TASK-0027-runtime-state-truth-monitor.md`

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
- live trading operations

## Completed Work

- Added `observed_at` to monitor state.
- Added `state_changed_at` to monitor state.
- Added `runtime_status` to distinguish API unavailable, bot stopped, and bot running.
- Added `execution_status` to distinguish bot running with no observed trades from bot running with observed trades.
- Verified `state_changed_at` remains stable across repeated polling when bot state does not change.

## Verification

- `bash -n scripts/check_trades.sh`
- `.\scripts\run_agent_readiness_checks.ps1`
- Server dry-run with temporary state file
- Repeated server dry-run proving `state_changed_at` stability
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, push, and server script deployment. Do not enter Task 28 automatically.
