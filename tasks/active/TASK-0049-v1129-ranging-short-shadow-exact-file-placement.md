# TASK-0049: V11.29 Ranging-Short Shadow Exact File Placement

## Status

Completed.

## Objective

Copy only the two Task 45 V11.29 ranging-short shadow files to the exact server
paths identified in Task 48.

## Files Placed

```text
/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

## Boundaries Preserved

- Did not start the shadow bot.
- Did not stop/restart existing bots.
- Did not run `freqtrade trade`.
- Did not run backtests.
- Did not read env files or secrets.
- Did not create SQLite runtime data.
- Did not commit the server worktree.

## Validation

```text
server sha256sum exact files
container visibility checks
port 8123 listener check
server git status for exact paths
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Next Recommended Task

```text
Task 50: V11.29 Ranging-Short Shadow Start Readiness and Resource Gate
```
