# TASK-0121: V11.31 Replay Coverage Extension Guard Exception

## Objective

Add exact guard exceptions for the future V11.31 replay coverage extension
implementation paths approved by Task 119.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Readiness checks: passed
- Task 119 approved exact future paths only

## Allowed Files

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task121_v1131_replay_coverage_extension_guard_exception.md`
- `tasks/active/TASK-0121-v1131-replay-coverage-extension-guard-exception.md`

## Exact Paths Allowed

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

Stop after guard validation and commit. Do not implement Task 122 until the
guard exception passes readiness and blocking self-tests.

