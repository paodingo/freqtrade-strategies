# Task 115: V11.31 Offline Replay Harness Guard Exception

## Summary

Added exact guard exceptions for the V11.31 offline replay harness paths
reviewed in Task 114.

Conclusion:

```text
v1131_replay_harness_paths_allowed_exactly
```

This task only updates static guard allowlists and the harness change-surface
matrix. It does not write replay code, generate replay outputs, run backtests,
modify strategies, modify bot configs, deploy, restart bots, or read secrets.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `8b27e1c` |
| starting status | clean |
| readiness before change | passed |
| source review | `reports/audits/task114_v1131_offline_replay_harness_path_review.md` |

## Exact Paths Allowed

Allowed exactly:

```text
scripts/build_v1131_loose_range_replay_report.js
reports/v1131_observation/v1131_loose_range_replay_report.json
reports/v1131_observation/v1131_loose_range_replay_report.md
```

## Explicit Non-Allowances

This task did not allow:

- `scripts/build_v1131_*`;
- `reports/v1131_observation/**`;
- `reports/**`;
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

## Validation

Required checks:

```text
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Self-test expectations:

- exact V11.31 replay script and output paths pass;
- extra `reports/v1131_observation/*` paths remain blocked;
- broad `scripts/build_v1131_*` paths remain blocked;
- strategy/config/dashboard/deploy surfaces remain blocked except already
  approved exact paths.

## Safety Boundary

This task did not:

- write replay implementation code;
- generate replay outputs;
- run replay;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- refresh or download data;
- read `.env` or `user_data/monitor.env`;
- start, stop, or restart bots;
- force-close trades;
- produce a replacement conclusion.

## Recommended Next Task

Proceed with:

```text
Task 116: V11.31 Offline Replay Harness Implementation
```

Task 116 may create only the exact replay script and two exact replay outputs,
plus its audit/task records. It must remain read-only and must not run a
Freqtrade backtest.

