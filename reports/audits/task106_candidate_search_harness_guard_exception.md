# Task 106: Candidate Search Harness Guard Exception

## Summary

Added exact guard exceptions for the first offline candidate-search harness
implementation surface approved by Task 105.

Conclusion:

```text
candidate_search_harness_first_pass_paths_allowed_exactly
```

This task only changes static guard allowlists and the harness change-surface
matrix. It does not write the harness, run candidate search, run backtests,
refresh data, modify strategies, modify bot configs, or touch server/runtime
state.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `d39de85` |
| starting status | clean |
| readiness before change | passed |
| source approval | `reports/audits/task105_candidate_search_harness_allowlist_review.md` |

## Exact Paths Added

### `scripts/guard_harness_diff.js`

Allowed exactly:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
```

### `scripts/guard_trading_surface.js`

Allowed exactly:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
```

The trading-surface exception is needed because the first run id contains
`v1130`, which is intentionally blocked unless exact report/harness paths are
approved.

## Explicit Non-Allowances

This task did not allow:

- `reports/candidate_search/**`;
- `reports/**`;
- `scripts/build_strategy_*`;
- `scripts/build_v1130_*`;
- `strategies/**`;
- `user_data/**`;
- `configs/**`;
- `dashboard/**`;
- `deploy/**`;
- SQLite snapshots;
- market-data files;
- bot configs;
- secrets;
- server or live operation paths.

## Documentation Update

Updated:

```text
docs/harness/change_surface_matrix.md
```

The matrix now records the Task 106 exact-path allowance and states that the
allowance is limited to one first-pass run id.

## Validation

Required checks:

```text
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

The post-change verification should also confirm that only the Task 106 allowed
files are changed before commit.

## Safety Boundary

This task did not:

- write harness implementation code;
- generate candidate-search outputs;
- run backtests;
- refresh or download market data;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- force-close V11.30 trades;
- produce a V11.30 replacement conclusion.

## Recommended Next Task

Proceed with:

```text
Task 107: Candidate Search Harness First Pass
```

Task 107 may create only:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
reports/audits/task107_candidate_search_harness_first_pass.md
tasks/active/TASK-0107-candidate-search-harness-first-pass.md
```

Task 107 must remain read-only and must not use stale `1h` OHLCV data.

