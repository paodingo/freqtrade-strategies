# Task 30: V11.29 Read-Only Signal Telemetry Implementation

## Summary

Implemented the first narrow V11.29 signal decision telemetry generator:

```text
scripts/build_v1129_signal_decision_telemetry.js
```

The generator produces:

```text
reports/v1129_execution_validation/signal_decision_telemetry_sample.json
reports/v1129_execution_validation/signal_decision_telemetry_sample.md
```

This implementation is intentionally conservative. It reads only clean-worktree audit evidence from Task 28 and Task 29. It does not SSH, does not query the live bot, does not read SQLite snapshots, does not read secrets, does not place orders, and does not modify strategy or bot configuration.

## Data Freshness Finding

The generated telemetry sample records the Task 28 data freshness finding:

- local `15m` futures feather latest candle: `2026-07-03T08:45:00+00:00`
- local `4h` futures feather latest candle: `2026-07-03T04:00:00+00:00`
- all 12 V11.29 whitelist pairs are marked `local_fallback` / `stale` for those local files
- `dataprovider_live` freshness is explicitly marked `unknown`

Interpretation:

- The local downloaded/fallback data set is not real-time updated in current evidence.
- This still does not prove that the running V11.29 bot lacked live exchange candles.
- A safe runtime DataProvider freshness probe is still required before treating stale local feather data as the root cause of zero trades.

## Guard Changes

Added exact-path guard exceptions only for Task 30:

```text
scripts/build_v1129_signal_decision_telemetry.js
reports/v1129_execution_validation/signal_decision_telemetry_sample.json
reports/v1129_execution_validation/signal_decision_telemetry_sample.md
```

Updated:

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
```

No broad allowlist was added. The guards still do not allow:

- `reports/v1129_execution_validation/**`
- `reports/*v1129*`
- `scripts/build_v1129_*`
- SQLite snapshots as commit targets
- strategy/config/dashboard/deploy/live/server surfaces

## Generated Telemetry Coverage

The sample contains:

- metadata and source list;
- Task 28 runtime context copied as prior audit evidence;
- 12-pair data freshness rows for `15m`, `4h`, and `runtime_dataprovider`;
- 12 pair decision rows;
- inherited V11 gate placeholders marked `unknown`;
- stake decision placeholders marked `unknown`;
- blocking gaps for runtime DataProvider freshness, signal dataframe evidence, gate-level reasons, and stake decision evidence.

## What Remains Unknown

The sample cannot yet prove:

- whether V11.29 currently receives fresh live exchange candles;
- whether any pair produced raw entry signals;
- whether V11 inherited gates blocked or retagged entries;
- whether stake sizing returned below-minimum / zero categories;
- why V11.29 produced no trades/orders;
- whether V11.29 can or cannot replace V10.8.2.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.

## Validation

Required validation:

```powershell
node --check scripts/build_v1129_signal_decision_telemetry.js
node scripts/build_v1129_signal_decision_telemetry.js
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Observed validation results:

```text
node --check scripts/build_v1129_signal_decision_telemetry.js: pass
node scripts/build_v1129_signal_decision_telemetry.js: pass
node --check scripts/guard_harness_diff.js: pass
node --check scripts/guard_trading_surface.js: pass
.\scripts\run_agent_readiness_checks.ps1: pass
```

Guard self-test results:

```text
Task 30 exact telemetry paths: allowed
reports/v1129_execution_validation/v1129_real_execution_report.json: blocked
reports/v1129_execution_validation/snapshots/should_not_commit.sqlite: blocked
strategies/RegimeAwareV1129GuardSelfTest.py: blocked
user_data/config_multi_futures_v1129_guard_selftest.json: blocked
```

## Recommended Task 31

Recommended next task:

```text
Task 31: V11.29 Safe Runtime Data Freshness Probe
```

Goal:

- Use a strictly read-only server/runtime method to prove whether V11.29 is receiving fresh `15m` and `4h` candles from live DataProvider/exchange sources.
- Do not change strategy, bot config, dashboard, deploy scripts, or bot lifecycle state.
- Do not read secrets.
- If live DataProvider freshness cannot be proven safely, keep it `unknown` and plan a narrower instrumentation task.
