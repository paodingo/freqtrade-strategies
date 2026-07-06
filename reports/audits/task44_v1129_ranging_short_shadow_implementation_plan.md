# Task 44: V11.29 Ranging-Short Shadow Implementation Plan

## Summary

This task converts the Task 43 shadow dry-run design into a concrete
implementation plan. It does not implement the strategy, does not create bot
configuration, does not create a database, does not deploy a container, and
does not start/stop/restart any bot.

The implementation is high-risk because it would touch:

- `strategies/**`;
- `user_data/**` bot config/runtime paths;
- server/container operations;
- monitoring labels and API ports.

Therefore the next implementation step must be explicitly authorized and must
first add exact guard exceptions.

## Implementation Goal

Create a separate dry-run-only shadow lane:

```text
V11.29 ranging-short shadow dry-run
```

The lane is not allowed to replace V10.8.2 or the current V11.29 bot. It exists
only to collect real dry-run evidence for the pair-filtered, alpha-blocked
ranging-short research lane.

## Exact Proposed Files

Strategy file, not created in this task:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
```

Config file, not created in this task:

```text
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Optional local audit/report files for the implementation task:

```text
reports/audits/task45_v1129_ranging_short_shadow_implementation.md
tasks/active/TASK-0045-v1129-ranging-short-shadow-implementation.md
```

No broad path rule should be used. Do not allow:

- `strategies/**`;
- `user_data/**`;
- `configs/**`;
- `reports/v1129_execution_validation/**`;
- `scripts/build_v1129_*`;
- `reports/*v1129*`.

## Required Guard Plan

Before creating strategy/config files, run a narrow guard exception task.

Recommended Task 45R allowlist:

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
reports/audits/task45r_v1129_ranging_short_shadow_guard_exception.md
tasks/active/TASK-0045R-v1129-ranging-short-shadow-guard-exception.md
```

Exact future paths to allow, only if Task 45 is approved:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

The guard exception must not allow any other V11.29 strategy/config path.

## Strategy Implementation Outline

The shadow strategy should:

1. Inherit from the current V11.29 strategy, or use a minimal wrapper that is
   easy to diff against V11.29.
2. Preserve existing V11.29 protections by default.
3. Add a separate `v1129_shadow_ranging_short` entry path.
4. Allow only explicitly approved pairs.
5. Require `alpha_filter_block_short == false`.
6. Block the candidate if alpha telemetry is missing.
7. Emit a clear `enter_tag`:

```text
v1129_shadow_ranging_short
```

8. Keep the normal V11.29 production-like bot untouched.

The strategy must not:

- modify V10.8.2;
- modify the current V11.29 strategy in-place;
- bypass alpha filtering;
- enable all pairs;
- introduce live-money behavior.

## Config Implementation Outline

The shadow config should be dry-run only.

Required identifiers:

```text
bot_name: V11.29 ranging-short shadow
dry_run: true
db_url: sqlite:////freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
api_server.listen_port: 8123
```

Required pair allowlist:

```text
ETH/USDT:USDT
AVAX/USDT:USDT
LINK/USDT:USDT
BCH/USDT:USDT
XRP/USDT:USDT
```

Initial exclusions:

```text
BNB/USDT:USDT
TRX/USDT:USDT
SOL/USDT:USDT
ADA/USDT:USDT
```

Watch-only, not initially enabled:

```text
DOGE/USDT:USDT
LTC/USDT:USDT
BTC/USDT:USDT
```

The config must not read or expose secrets in audit output. Do not print API
keys, exchange credentials, passwords, tokens, `.env`, or
`user_data/monitor.env`.

## Server Runtime Plan

Any future server task must be separately authorized.

Proposed container:

```text
freqtrade-v1129-ranging-short-shadow
```

Proposed API:

```text
127.0.0.1:8123
```

Proposed DB:

```text
/freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
```

Do not use:

- the V10.8.2 DB;
- the current V11.29 DB;
- existing V11.29 container name;
- live mode;
- a public API bind.

## Validation Plan Before Start

Before starting any shadow bot:

1. Syntax-check the new strategy.
2. Validate config file exists at the exact approved path.
3. Confirm `dry_run = true`.
4. Confirm `db_url` points to the shadow DB only.
5. Confirm pair allowlist matches the approved list exactly.
6. Confirm API port is unused.
7. Confirm alpha blocking logic is active.
8. Confirm no live server secrets are printed in logs or reports.
9. Confirm readiness checks pass.

## Observation Plan

Observation windows:

| Window | Purpose |
| --- | --- |
| 1d | confirm process/API stability and candidate/order telemetry |
| 3d | initial execution sample health |
| 7d | minimum dry-run evidence window |
| 14d | preferred decision window if server resources allow |

Metrics to collect:

- bot uptime;
- API health;
- candidate count;
- blocked-by-alpha count;
- final `enter_short` count;
- open trades;
- closed trades;
- orders;
- fees;
- funding fees if available;
- order price;
- filled price;
- slippage bps;
- entry tag;
- exit reason;
- pair;
- side;
- open time;
- close time.

If trades/orders remain zero, the result is `insufficient`.

## Stop Conditions

Stop or pause the shadow lane if:

- dry-run is not true;
- DB path does not match the shadow DB;
- pair allowlist differs from approved list;
- alpha telemetry is missing;
- API health is unstable;
- monitor cannot distinguish the shadow lane from V10.8.2/V11.29;
- server resource pressure becomes unacceptable;
- unexpected live order capability appears;
- strategy/config diff differs from approved scope;
- no candidates or no orders after the approved observation window.

## Rollback Plan

Rollback must be explicit and separate from implementation:

1. Stop only the shadow container, if it exists.
2. Do not stop V10.8.2 or current V11.29.
3. Preserve the shadow DB as evidence unless a later task authorizes cleanup.
4. Preserve logs/reports as evidence.
5. Record rollback reason in an audit report.

## Recommended Task 45R

Recommended next task:

```text
Task 45R: Allow V11.29 Ranging-Short Shadow Exact Paths
```

Scope:

- Add exact guard exceptions for:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

- Do not create those files yet.
- Confirm broad strategy/config paths remain blocked.

## Recommended Task 45

Only after Task 45R:

```text
Task 45: Implement V11.29 Ranging-Short Shadow Strategy and Config
```

Scope:

- Create the exact strategy and config files.
- Do not deploy/start the bot unless that task explicitly authorizes it.
- Run static checks and readiness.
- Commit/push before any server runtime task.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- download or refresh market data;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Verification

Required completion checks:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

