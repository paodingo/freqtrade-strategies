# Task 96T: V11.30 Decision Telemetry Instrumentation Plan

## Summary

Defined the smallest behavior-neutral instrumentation plan needed to make the
V11.30 final decision path observable.

Conclusion:

```text
behavior_neutral_decision_telemetry_required
```

Task 96S confirmed that the current V11.30 runtime does not expose final
analyzed dataframe columns through existing read-only API or log surfaces.
Therefore zero trades and zero orders cannot yet be attributed to a final
strategy cause.

This task is a plan only. It did not modify strategy code, bot config,
dashboard, deploy files, server runtime, SQLite, or generated telemetry output.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `e06ce29`
- Starting `git status --short --untracked-files=all`: empty
- Local readiness before planning: passed

## Evidence Reviewed

- `reports/audits/task96r_v1130_final_decision_path_observability_plan.md`
- `reports/audits/task96s_v1130_analyzed_dataframe_readonly_probe.md`
- `tasks/active/TASK-0096R-v1130-final-decision-path-observability-plan.md`
- `tasks/active/TASK-0096S-v1130-analyzed-dataframe-readonly-probe.md`
- `strategies/RegimeAwareV1130CrashReboundShadow.py` symbol search only
- `strategies/alpha_risk_filter.py` symbol search only

## Current Observability Gap

Observed from Task 96S:

- V11.30 has no host API port mapping.
- Common in-container API ports did not expose a Freqtrade API.
- V11.30 logs do not include per-candle `v1130_crash_rebound_gate` values.
- Existing OHLCV reports can reconstruct candidate candles, but cannot prove
  final analyzed dataframe values.

Still unknown:

| field | current state | impact |
|---|---|---|
| `alpha_filter_block_short` | unknown | may block a crash-rebound candidate |
| `alpha_risk_flags` | unknown | may contain `takerSellPressure` |
| `taker_sell_pressure` | unknown | V11.30 requires this for the crash-rebound long |
| `v1130_crash_rebound_gate` | unknown | final strategy-local gate reason is hidden |
| `enter_long` | unknown | final analyzed signal is hidden |
| `enter_tag` | unknown | final V11.30 tag emission is hidden |
| post-signal order block | unknown | only relevant after an `enter_long = 1` row is proven |

## Instrumentation Goal

Add behavior-neutral telemetry that records final decision fields after the
V11.30 strategy has computed the analyzed dataframe.

The instrumentation must answer:

1. Did a latest candle become a V11.30 crash-rebound candidate?
2. If yes, which final gate value was assigned?
3. Did alpha risk block it?
4. Did taker sell pressure exist?
5. Did the strategy set `enter_long = 1`?
6. Did the strategy set the V11.30 `enter_tag`?
7. If `enter_long = 1` exists but orders remain `0`, should the next task move
   to wallet, pairlock, protection, or order-blocking inspection?

## Behavior-Neutral Constraints

The implementation task must not change:

- entry thresholds;
- exit thresholds;
- pairlist;
- stake amount;
- leverage;
- protections;
- stoploss;
- ROI;
- order type;
- position adjustment;
- `enter_long` assignment logic;
- `enter_tag` assignment logic;
- SQLite trading tables;
- bot config;
- dashboard behavior;
- live/server process state.

The instrumentation must only mirror values that already exist or are directly
derived from existing dataframe columns.

## Required Telemetry Fields

Minimum per-row fields:

| field | status in telemetry | source |
|---|---|---|
| `pair` | observed | metadata or pair loop |
| `timeframe` | observed | strategy timeframe |
| `candle_time` | observed | dataframe date column |
| `open` | observed | dataframe |
| `high` | observed | dataframe |
| `low` | observed | dataframe |
| `close` | observed | dataframe |
| `volume` | observed | dataframe |
| `candle_return` | derived | `(close - open) / open` |
| `candle_range` | derived | `(high - low) / open` |
| `rsi` | observed if present, otherwise `missing` | dataframe |
| `volume_ratio` | derived if `volume_mean` present, otherwise `missing` | dataframe |
| `candidate` | derived | V11.30 raw crash-rebound conditions |
| `alpha_filter_block_short` | observed if present, otherwise `missing` | dataframe |
| `alpha_risk_flags` | observed if present, otherwise `missing` | dataframe |
| `taker_sell_pressure` | derived if `alpha_risk_flags` present, otherwise `unknown` | strategy helper |
| `v1130_crash_rebound_gate` | observed if present, otherwise `missing` | dataframe |
| `enter_long` | observed | dataframe |
| `enter_tag` | observed | dataframe |

Do not write missing fields as `0`. Use `missing` or `unknown`.

## Recommended Output Shape

Generate a narrow append-only or overwrite-safe JSON report from the strategy or
from an approved telemetry builder:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

Recommended top-level JSON fields:

- `metadata`
- `runtime_context`
- `pairs`
- `latest_rows`
- `candidate_rows`
- `enabled_rows`
- `blocked_rows`
- `data_gaps`
- `safety_verdict`

Recommended `safety_verdict` values:

- `telemetry_only_no_behavior_change`
- `insufficient_missing_required_columns`
- `ready_for_order_blocking_probe`
- `ready_for_zero_signal_cause_report`

## Exact Future Change Surface

Task 96T does not approve implementation. It recommends a separate explicit
approval task before any strategy edit.

Recommended future allowed paths for implementation review:

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
reports/audits/task96u_v1130_decision_telemetry_guard_review.md
tasks/active/TASK-0096U-v1130-decision-telemetry-guard-review.md
```

If tests are added, they must use exact file paths selected in Task 96U. Do not
use broad allowlists such as `strategies/**`, `reports/v1130_observation/**`,
or `tests/**`.

## Guardrail Requirements For Task 96U

Task 96U should review and, if approved, add exact path exceptions only.

Required guard principles:

- no broad `strategies/**` allowance;
- no broad `reports/v1130_observation/**` allowance;
- no broad `scripts/build_v1130_*` allowance;
- no allowance for bot config changes;
- no allowance for dashboard/deploy changes;
- no allowance for SQLite snapshots;
- no allowance for server runtime commands.

If the guard cannot express this safely, stop before implementation.

## Implementation Acceptance Criteria For A Later Task

A later implementation task must prove:

1. `enter_long` and `enter_tag` outputs are identical with telemetry enabled
   and disabled on the same fixture dataframe.
2. Strategy constants and thresholds are unchanged.
3. Pairlist, stake, leverage, exit, stoploss, ROI, and order-type settings are
   untouched.
4. Telemetry writes only to approved generated report/log paths.
5. Missing columns are marked `missing` or `unknown`, not `0`.
6. `node --check` or Python syntax checks pass for changed files.
7. `.\scripts\run_agent_readiness_checks.ps1` passes.

Suggested behavior-invariance test:

```text
Build a small dataframe fixture containing one non-candidate row, one blocked
candidate row, and one enabled candidate row. Run the strategy decision method
before and after telemetry insertion. Assert that `enter_long`, `enter_tag`,
and `v1130_crash_rebound_gate` are identical.
```

## Deployment Boundary

Do not deploy or restart V11.30 in the instrumentation implementation task
unless a later task explicitly authorizes:

- copying the modified strategy to the server;
- restarting or reloading the V11.30 container;
- observing fresh logs after deployment.

The implementation and rollout should remain separate so behavior-neutral code
review can happen before touching a running bot.

## Not Allowed In This Task

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- use API credentials;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- log in to the server;
- decide whether V11.30 can replace V10.8.2.

## Recommended Next Tasks

Proceed with:

```text
Task 96U: V11.30 behavior-neutral decision telemetry guard review
```

Task 96U should approve exact future change paths and guard behavior before any
strategy implementation.

Then:

```text
Task 96V: Implement V11.30 behavior-neutral decision telemetry
```

Only after Task 96V passes local invariance checks should a separate rollout
task consider deploying the telemetry to the running V11.30 container.
