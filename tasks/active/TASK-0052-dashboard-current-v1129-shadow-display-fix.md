# TASK-0052: Dashboard Current V11.29 Shadow Display Fix

## Status

Completed.

## Objective

Correct dashboard bot-source display for the current runtime topology after
Task 51.

## Completed

- Changed default dashboard bot list to `v1129` API plus `v1129_shadow` SQLite.
- Added SQLite-only shadow summary support.
- Kept shadow API disabled and did not add credentials.
- Added exact guard exceptions for two dashboard files only.
- Deployed the two dashboard files to the server.
- Restarted `freqtrade-monitor.service`.

## Validation

```text
node --check dashboard/lib/config.js
node --check dashboard/server.js
.\scripts\run_agent_readiness_checks.ps1
systemctl is-active freqtrade-monitor.service
```

## Next Recommended Task

```text
Task 53: V11.29 Shadow First Web Observation Check
```
