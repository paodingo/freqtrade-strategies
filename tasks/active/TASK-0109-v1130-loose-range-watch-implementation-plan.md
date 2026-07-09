# TASK-0109: V11.30 Loose-Range Watch Implementation Plan

## Status

Completed.

## Goal

Define a safe implementation plan for the `v1130_loose_range_watch` candidate
without writing strategy code or modifying runtime surfaces.

## Allowed Outputs

- `reports/audits/task109_v1130_loose_range_watch_implementation_plan.md`
- `tasks/active/TASK-0109-v1130-loose-range-watch-implementation-plan.md`

## Result

Future implementation should be treated as a new dry-run/shadow candidate, not
as a direct mutation of current V11.30.

Potential future strategy path for review:

```text
strategies/RegimeAwareV1131LooseRangeWatchShadow.py
```

Potential future dry-run config path for review:

```text
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
```

These paths remain blocked until a separate exact guard/implementation task.

## Boundaries

This task did not:

- write strategy code;
- modify V11.30;
- modify bot configs;
- run backtests;
- refresh data;
- read secrets;
- restart bots;
- force-close trades;
- claim replacement readiness.

Recommended next task:

```text
Task 110: V11.31 Loose-Range Watch Strategy Guard Review
```

