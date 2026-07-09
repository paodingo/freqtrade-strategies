# Task 105: Candidate Search Harness Exact Path Allowlist Review

## Summary

Reviewed the exact path surface needed for the future offline candidate-search
harness described by Task 104.

Conclusion:

```text
approve_narrow_future_allowlist_review_but_do_not_modify_guard_yet
```

This task only reviews the future allowlist. It does not modify guard scripts,
write harness code, run backtests, refresh data, modify strategies, modify bot
configs, or touch server/runtime state.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `e05fe14` |
| starting status | clean |
| readiness before review | passed |
| source reports | Task 102, Task 103, Task 104 |

## Source Conclusions Used

| source | conclusion used |
|---|---|
| `reports/audits/task102_strategy_candidate_evidence_inventory.md` | candidate search should start from existing high-volatility and crash-rebound evidence |
| `reports/audits/task103_high_volatility_window_dataset_readiness_plan.md` | `15m` and `4h` recent OHLCV are usable; exact `1h` futures OHLCV is stale |
| `reports/audits/task104_candidate_search_harness_design.md` | future harness should be metric-first, data-gated, read-only, and exact-path authorized |

## Future Paths Approved For A Guard-Exception Task

The following paths are approved only as candidates for a later exact guard
exception / implementation task. They are not created or allowed by this task.

| path | proposed action | reason |
|---|---|---|
| `scripts/build_strategy_candidate_search_harness.js` | allow in a future guard task | offline read-only report builder for candidate search |
| `reports/candidate_search/<run_id>/candidate_search_summary.json` | allow pattern by exact run directory in a future guard task | machine-readable candidate-search output |
| `reports/candidate_search/<run_id>/candidate_search_summary.md` | allow pattern by exact run directory in a future guard task | human-readable candidate-search output |
| `reports/candidate_search/<run_id>/candidate_matrix.csv` | allow pattern by exact run directory in a future guard task | tabular candidate ranking / metrics matrix |

Important constraint:

```text
Do not approve reports/candidate_search/** as a permanent broad wildcard.
```

The future implementation task should choose one concrete run id, for example:

```text
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/
```

Then guard exceptions, staging, and outputs should use that concrete directory
or an explicitly bounded one-run regex.

## Paths Not Approved

| path or pattern | decision | reason |
|---|---|---|
| `strategies/**` | not approved | strategy behavior changes require a separate strategy implementation task |
| `user_data/**` | not approved | bot configs, SQLite, runtime state, and data files are protected by default |
| `configs/**` | not approved | config changes require a separate task |
| `dashboard/**` | not approved | dashboard issues are separate and require authenticated evidence |
| `deploy/**` | not approved | deploy changes are live/server surface |
| `reports/v1130_observation/**` | not approved | V11.30 observation evidence should stay exact-path gated |
| `reports/v1129_execution_validation/**` | not approved | V11.29 evidence should stay exact-path gated |
| `reports/candidate_search/**` | not approved as broad wildcard | too wide; future tasks should bind one run id |
| `scripts/build_v1130_*` | not approved | broad script prefix is too wide |
| `scripts/build_strategy_*` | not approved | broad script prefix is too wide |
| `tests/**` | not approved by this review | test paths should be explicit if implementation adds tests |
| `.env` | blocked | secret material |
| `user_data/monitor.env` | blocked | secret/runtime credential material |

## Required Future Guard Rules

If Task 106 implements the harness, it should first create or include an exact
guard exception task with these properties:

1. Add only `scripts/build_strategy_candidate_search_harness.js` to script
   allowlists.
2. Add only one concrete `reports/candidate_search/<run_id>/...` output set.
3. Do not add `reports/candidate_search/**`.
4. Do not add `reports/**`.
5. Do not add `scripts/build_strategy_*`.
6. Do not lower blocking for `strategies/**`, `user_data/**`, `configs/**`,
   `dashboard/**`, or `deploy/**`.
7. Do not allow SQLite snapshots, market-data files, bot configs, or secrets
   into Git.

## Recommended First Run Surface

Because Task 103 found `1h` OHLCV stale, the first implementation should use a
`15m + 4h` only run id:

```text
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
```

This avoids silently using stale `1h` features.

## Implementation Preconditions For Task 106

Task 106 may proceed only if it remains within this scope:

- read-only local/server market-data inspection;
- no market-data download;
- no strategy edits;
- no bot config edits;
- no dashboard/deploy edits;
- no bot start/stop/restart;
- no backtest unless explicitly authorized;
- no secrets;
- no V11.30 replacement conclusion;
- no manual intervention in current V11.30 trades.

If the harness requires current `1h` OHLCV, stop and run:

```text
Task 103R: Refresh V11.30 1h Futures OHLCV Data
```

## Candidate Search Output Requirements

Future harness output must include:

- input data coverage by pair/timeframe;
- candidate family name;
- parameter set id;
- trade count;
- closed trade count;
- gross PnL;
- net PnL after fees;
- winrate;
- profit factor;
- max drawdown;
- MFE / MAE;
- hold-time distribution;
- pair participation;
- pair concentration;
- exit reason distribution;
- data gap status;
- insufficiency labels when sample size is too small.

## Stop Conditions

Stop before writing implementation code if:

- `git status --short --untracked-files=all` is not clean;
- readiness fails before the task starts;
- the task needs `1h` features before a refresh task;
- the task needs strategy changes;
- the task needs bot config changes;
- the task needs dashboard/deploy changes;
- the task needs server restart or bot lifecycle commands;
- the task needs secrets;
- the task attempts to rank V11.30 as good/bad from insufficient live samples.

## Safety Boundary

This task did not:

- modify `scripts/guard_harness_diff.js`;
- modify `scripts/guard_trading_surface.js`;
- modify `docs/harness/change_surface_matrix.md`;
- write harness code;
- run backtests;
- refresh or download data;
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
Task 106: Candidate Search Harness Guard Exception
```

Task 106 should add exact guard exceptions for:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
```

It should not implement the harness unless the task explicitly combines guard
exception and implementation.

