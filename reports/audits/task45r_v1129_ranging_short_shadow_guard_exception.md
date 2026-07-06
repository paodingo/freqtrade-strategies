# Task 45R: V11.29 Ranging-Short Shadow Guard Exception

## Summary

Added exact guard exceptions for the two Task 45 shadow implementation files:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

This task did not create those files. It only updated guard policy so a later
explicit Task 45 can create exactly those paths.

## Modified Files

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
reports/audits/task45r_v1129_ranging_short_shadow_guard_exception.md
tasks/active/TASK-0045R-v1129-ranging-short-shadow-guard-exception.md
```

## Explicit Non-Allowances

This task does not allow:

- `strategies/**`;
- `user_data/**`;
- other V11.29 strategy files;
- other V11.29 config files;
- `configs/**`;
- `dashboard/**`;
- `deploy/**`;
- server/container operations;
- SQLite DB creation;
- data refresh/download;
- live trading.

## Self-Test Requirements

Allowed exact paths must pass:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Blocked paths must remain blocked:

```text
strategies/RegimeAwareV1129GuardSelfTest.py
strategies/RegimeAwareV1129AnotherShadow.py
user_data/config_multi_futures_v1129_guard_selftest.json
user_data/config_multi_futures_v1129_other_shadow.json
configs/v1129_shadow.json
dashboard/v1129_shadow.js
deploy/v1129_shadow.yml
```

## Boundary Confirmation

This task did not:

- create or modify strategy implementation files;
- create or modify bot config files;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- download or refresh market data;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Recommended Task 45

Recommended next task:

```text
Task 45: Implement V11.29 Ranging-Short Shadow Strategy and Config
```

Task 45 must still be explicitly authorized and must not deploy/start the bot
unless that task says so.

