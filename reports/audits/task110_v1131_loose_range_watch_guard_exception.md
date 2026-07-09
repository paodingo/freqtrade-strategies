# Task 110: V11.31 Loose-Range Watch Strategy Guard Review

## Summary

Added exact guard exceptions for the planned V11.31 loose-range watch shadow
strategy surface.

Conclusion:

```text
v1131_loose_range_watch_shadow_paths_allowed_exactly
```

This task only updates static guard allowlists and the harness change-surface
matrix. It does not implement the strategy, run backtests, modify existing
V11.30 behavior, deploy to server, restart bots, or read secrets.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `ed86024` |
| starting status | clean |
| readiness before change | passed |
| source plan | `reports/audits/task109_v1130_loose_range_watch_implementation_plan.md` |

## Exact Paths Allowed

Allowed exactly:

```text
strategies/RegimeAwareV1131LooseRangeWatchShadow.py
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
tests/test_regime_aware_v1131_loose_range_watch_shadow.py
```

## Explicit Non-Allowances

This task did not allow:

- `strategies/**`;
- `user_data/**`;
- `tests/**`;
- `configs/**`;
- `dashboard/**`;
- `deploy/**`;
- `scripts/start_bot.sh`;
- `scripts/ensure_dry_run_bots_started.sh`;
- `scripts/refresh_data.sh`;
- broad `*v1131*`;
- server/runtime operations;
- SQLite snapshots;
- market-data files;
- secrets.

## Guard Files Updated

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
```

The exceptions are exact path entries only.

## Required Validation

Run:

```text
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Self-test requirements:

- the three exact V11.31 paths must pass guard checks;
- unrelated strategy paths must remain blocked;
- unrelated `user_data` config paths must remain blocked;
- broad tests paths must remain blocked unless exact.

## Safety Boundary

This task did not:

- create or edit the V11.31 strategy;
- create or edit the V11.31 config;
- run tests for strategy behavior;
- run backtests;
- refresh or download market data;
- modify current V11.30;
- modify dashboard or deploy files;
- read `.env` or `user_data/monitor.env`;
- start, stop, or restart bots;
- force-close trades;
- produce a replacement conclusion.

## Recommended Next Task

Proceed with:

```text
Task 111: V11.31 Loose-Range Watch Strategy Implementation
```

Task 111 may create only the three exact implementation paths plus its audit and
task records. It must remain local-only and must not deploy or start bots.

