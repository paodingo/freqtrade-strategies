# TASK-0127: V11.31 Longer Replay Window Inventory Exact Path Review

## Objective

Approve exact future paths for the V11.31 longer replay window inventory.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Task 124 generated the acquisition plan

## Allowed Files

- `reports/audits/task127_v1131_longer_replay_window_path_review.md`
- `tasks/active/TASK-0127-v1131-longer-replay-window-path-review.md`

## Approved Future Paths

```text
scripts/build_v1131_longer_replay_window_inventory.js
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

## Stop Condition

Stop after documenting this exact-path review. Do not modify guards or implement
the inventory builder in this task.

