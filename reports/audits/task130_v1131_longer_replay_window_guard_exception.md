# Task 130: V11.31 Longer Replay Window Inventory Guard Exception

## Summary

Added exact guard exceptions for the future V11.31 longer replay window
inventory task.

Allowed exact paths:

```text
scripts/build_v1131_longer_replay_window_inventory.js
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

No broad rule was added for `reports/v1131_observation/**`,
`reports/*v1131*`, `scripts/build_v1131_*`, or `scripts/*v1131*`.

## Source Authority

| item | path |
|---|---|
| Task 127 path review | `reports/audits/task127_v1131_longer_replay_window_path_review.md` |
| Task 124 plan | `reports/audits/task124_v1131_longer_replay_window_acquisition_plan.md` |

## Files Modified

| file | change |
|---|---|
| `scripts/guard_harness_diff.js` | Added three exact low-risk paths |
| `scripts/guard_trading_surface.js` | Added the same three exact versioned-path exceptions |
| `docs/harness/change_surface_matrix.md` | Documented the exact Task 130 guard surface |

## Boundaries Preserved

The guard still blocks:

- broad `reports/v1131_observation/**`;
- broad `scripts/build_v1131_*`;
- `strategies/**`;
- `user_data/**` except previously authorized exact shadow config paths;
- `configs/**`;
- `dashboard/**` except previously authorized exact dashboard correction paths;
- `deploy/**`;
- bot lifecycle scripts;
- SQLite snapshots;
- secrets and env files.

## Self-Test Result

Required self-tests:

- approved three exact paths must pass both guards;
- `reports/v1131_observation/unapproved_inventory.json` must be blocked;
- `scripts/build_v1131_unapproved_inventory.js` must be blocked;
- `strategies/RegimeAwareV1131GuardSelfTest.py` must be blocked;
- `user_data/config_multi_futures_v1131_guard_selftest.json` must be blocked.

## Recommended Next Task

Proceed with:

```text
Task 133: V11.31 Longer Replay Window Inventory Implementation
```

Do not run a Freqtrade backtest or deploy from Task 130.

