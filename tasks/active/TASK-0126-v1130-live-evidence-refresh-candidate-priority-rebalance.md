# TASK-0126: V11.30 Live Evidence Refresh And Candidate Priority Rebalance

## Objective

Refresh V11.30 live evidence read-only and rebalance candidate priorities.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Readiness checks: passed
- Server access available through `ubuntu@43.134.72.69`

## Allowed Files

- `reports/audits/task126_v1130_live_evidence_refresh_candidate_priority_rebalance.md`
- `tasks/active/TASK-0126-v1130-live-evidence-refresh-candidate-priority-rebalance.md`

## Read-Only Server Operations Used

- `hostname`
- `date -Is`
- `docker ps --format ...`
- read-only SQLite queries against V11.30 dry-run DB
- `docker logs --tail 300` keyword filtering

## Result

V11.30 has `2` closed dry-run trades and `4` orders. Both closed trades are BCH
longs exited by `v1130_rebound_time_exit` with negative realized PnL.

## Stop Condition

Stop after documenting evidence. Do not start/stop/restart bots, run backtests,
modify strategy/config, or enter the next task automatically.

