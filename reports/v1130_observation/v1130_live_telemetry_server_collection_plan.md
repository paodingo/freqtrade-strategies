# V11.30 Live Telemetry Server Collection Plan

## Summary

This is a plan-only artifact. It does not connect to the server, read fresh logs, modify files, restart bots, or run backtests.

## Committed Runtime Evidence

| field | value |
| --- | --- |
| host | 43.134.72.69 |
| hostname | VM-0-8-ubuntu |
| last checked | 2026-07-09T15:50:03+08:00 |
| v1130 container | freqtrade-v1130-crash-rebound-shadow |
| v1130 state | Up 18 hours |
| analysis overrun | observed |
| exchange timeout | observed |

## Future Collection Plan

| evidence type | state | command draft |
| --- | --- | --- |
| bounded_logs | planned_not_executed | docker logs --tail 800 freqtrade-v1130-crash-rebound-shadow |
| point_in_time_container_state | planned_not_executed | docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' |
| point_in_time_resource_snapshot | planned_not_executed | docker stats --no-stream freqtrade-v1130-crash-rebound-shadow |
| read_only_sqlite_counts | planned_not_executed | sqlite3 -readonly <approved-v1130-snapshot-or-db> '<bounded count/timestamp queries>' |

## Stop Conditions

- worktree is dirty before execution
- readiness checks fail
- server command would read secrets or full docker inspect output
- command would start, stop, restart, or deploy a bot
- command would write SQLite, strategy, config, dashboard, or deploy files

## Decisions

| decision | value |
| --- | --- |
| can_claim_runtime_stability | false |
| can_claim_profitability | false |
| can_evaluate_replacement | false |
| can_execute_collection_now | false |

## Recommended Next Task

Task 167: V11.30 Live Telemetry Server Collection Execution Authorization
