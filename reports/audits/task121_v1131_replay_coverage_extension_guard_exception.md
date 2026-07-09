# Task 121: V11.31 Replay Coverage Extension Guard Exception

## Summary

Added exact guard exceptions for the future V11.31 replay coverage extension.

Allowed exact paths:

```text
scripts/build_v1131_loose_range_replay_coverage_extension.js
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md
```

No broad rule was added for `reports/v1131_observation/**`,
`reports/*v1131*`, `scripts/build_v1131_*`, or `scripts/*v1131*`.

## Source Authority

| item | path |
|---|---|
| Task 118 plan | `reports/audits/task118_v1131_replay_coverage_extension_plan.md` |
| Task 119 exact path review | `reports/audits/task119_v1131_replay_coverage_extension_path_review.md` |
| Task 120 go/no-go consolidation | `reports/audits/task120_v1131_backtest_go_no_go_consolidation.md` |

## Files Modified

| file | change |
|---|---|
| `scripts/guard_harness_diff.js` | Added three exact low-risk paths |
| `scripts/guard_trading_surface.js` | Added the same three exact versioned-path exceptions |
| `docs/harness/change_surface_matrix.md` | Documented the exact Task 121 guard surface |

## Blocking Boundaries Preserved

The guard still blocks:

- `strategies/**` except previously authorized exact shadow paths;
- `user_data/**` except previously authorized exact shadow config paths;
- `configs/**`;
- `dashboard/**` except previously authorized exact dashboard correction paths;
- `deploy/**`;
- bot lifecycle scripts;
- SQLite snapshots;
- unapproved V11.31 report paths;
- broad V11.31 script/report wildcards;
- secrets and env files.

## Self-Test Plan

The blocking self-test must confirm:

- the three exact Task 122 paths are allowed;
- `reports/v1131_observation/extra.json` is blocked;
- `scripts/build_v1131_other_report.js` is blocked;
- `strategies/RegimeAwareV1131GuardSelfTest.py` is blocked;
- `user_data/config_multi_futures_v1131_guard_selftest.json` is blocked.

## Result

Task 121 prepares the narrow guard surface for Task 122 implementation only. It
does not implement the replay coverage extension, run backtests, deploy,
restart bots, modify strategies, or modify bot configs.

## Recommended Next Task

Proceed with:

```text
Task 122: V11.31 Replay Coverage Extension Implementation
```

