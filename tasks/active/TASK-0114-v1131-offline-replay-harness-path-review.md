# TASK-0114: V11.31 Offline Replay Harness Exact Path Review

## Status

Completed.

## Goal

Review exact future paths for a V11.31 offline replay harness.

## Allowed Outputs

- `reports/audits/task114_v1131_offline_replay_harness_path_review.md`
- `tasks/active/TASK-0114-v1131-offline-replay-harness-path-review.md`

## Result

Recommended future exact paths:

```text
scripts/build_v1131_loose_range_replay_report.js
reports/v1131_observation/v1131_loose_range_replay_report.json
reports/v1131_observation/v1131_loose_range_replay_report.md
```

## Boundaries

This task did not:

- modify guards;
- write replay code;
- run replay;
- run backtests;
- modify strategies/configs;
- deploy or restart bots;
- read secrets.

Recommended next task:

```text
Task 115: V11.31 Offline Replay Harness Guard Exception
```

