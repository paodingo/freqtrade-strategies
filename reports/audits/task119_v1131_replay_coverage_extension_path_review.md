# Task 119: V11.31 Replay Coverage Extension Exact Path Review

## Summary

Reviewed the exact file surface needed for a future V11.31 replay coverage
extension task.

Decision:

```text
approve_exact_paths_only_require_guard_exception_before_implementation
```

This task does not modify guards and does not implement the replay extension.

## Source Plan

| item | path |
|---|---|
| Task 118 report | `reports/audits/task118_v1131_replay_coverage_extension_plan.md` |
| Task 117 report | `reports/audits/task117_v1131_replay_result_review.md` |

## Approved Future Paths

Only these exact paths should be considered for a future implementation:

```text
scripts/build_v1131_loose_range_replay_coverage_extension.js
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md
```

## Required Guard Policy

A future guard task may add exact exceptions for the three paths above.

It must not add any of these broad patterns:

```text
reports/v1131_observation/**
reports/*v1131*
scripts/build_v1131_*
scripts/*v1131*
```

## Explicitly Forbidden Paths

Do not include:

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- SQLite snapshots
- server logs copied into Git
- API keys, exchange credentials, server keys, dashboard passwords
- live/server operation files

## Implementation Boundary For Future Task

The future implementation should:

- read committed evidence only;
- produce JSON and Markdown replay coverage outputs;
- avoid real bot operation;
- avoid Freqtrade backtests;
- avoid strategy/config edits;
- avoid any V11.31 deploy or server action;
- preserve `sample_status` if the expanded sample remains below gate.

## Recommended Next Task

Proceed with:

```text
Task 121: V11.31 Replay Coverage Extension Guard Exception
```

Task 121 should make only the exact guard exceptions needed for the three future
implementation paths. Do not proceed directly to implementation until the guard
exception passes readiness and blocking self-tests.

