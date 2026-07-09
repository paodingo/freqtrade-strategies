# TASK-0119: V11.31 Replay Coverage Extension Exact Path Review

## Objective

Review and approve the exact future file paths needed for V11.31 replay coverage
extension work.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Readiness checks: passed
- Task 118 generated the coverage extension plan

## Allowed Files

- `reports/audits/task119_v1131_replay_coverage_extension_path_review.md`
- `tasks/active/TASK-0119-v1131-replay-coverage-extension-path-review.md`

## Approved Future Paths

```text
scripts/build_v1131_loose_range_replay_coverage_extension.js
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md
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

Stop after documenting the exact-path review. Do not modify guards in this task.

