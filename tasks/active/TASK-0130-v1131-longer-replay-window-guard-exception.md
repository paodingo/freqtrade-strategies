# TASK-0130: V11.31 Longer Replay Window Inventory Guard Exception

## Objective

Add exact guard exceptions for the future V11.31 longer replay window inventory
paths approved by Task 127.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Task 127 approved exact future paths

## Allowed Files

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task130_v1131_longer_replay_window_guard_exception.md`
- `tasks/active/TASK-0130-v1131-longer-replay-window-guard-exception.md`

## Exact Paths Allowed

```text
scripts/build_v1131_longer_replay_window_inventory.js
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

## Forbidden Broad Rules

Do not allow:

```text
reports/v1131_observation/**
reports/*v1131*
scripts/build_v1131_*
scripts/*v1131*
```

## Stop Condition

Stop after guard validation and commit. Do not implement the inventory builder
inside Task 130.

