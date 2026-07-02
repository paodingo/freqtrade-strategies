# Agent Task Template

## Goal

Describe the smallest useful outcome.

## Allowed Change Surface

- List exact files or directories the agent may create or edit.

## Blocked Change Surface

- `strategies/**`
- `user_data/**`
- `dashboard/lib/config.js`
- `dashboard/server.js`
- `dashboard/public/**`
- bot lifecycle scripts
- deployment files
- V10.8.2 and V11.29 strategy/report surfaces
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords

## Runtime Limits

- Do not start, stop, or restart bots.
- Do not log in to servers.
- Do not read secret files or credential material.
- CI must remain static-only: no Docker, no server, no secret dependency.

## Required Verification

```bash
bash -n scripts/run_agent_readiness_checks.sh
node --check scripts/guard_harness_diff.js
node --check scripts/guard_no_secret_material.js
node --check scripts/guard_trading_surface.js
bash scripts/run_agent_readiness_checks.sh
git diff --name-only
```

## Handoff Report

- changed files
- verification commands
- test results
- remaining risks
