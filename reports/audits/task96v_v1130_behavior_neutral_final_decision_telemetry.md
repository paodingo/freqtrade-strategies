# Task 96V: V11.30 Behavior-Neutral Final Decision Telemetry

## Summary

Implemented behavior-neutral final decision telemetry for the V11.30
crash-rebound shadow strategy.

Conclusion:

```text
local_behavior_neutral_telemetry_implemented_not_deployed
```

The strategy now mirrors final decision fields to generated JSON and Markdown
telemetry files after `populate_entry_trend` completes its existing decision
logic. The telemetry is a side effect only; it does not change entry thresholds,
exit thresholds, stake, leverage, pairlist, config, order behavior, or bot
runtime state.

This task did not deploy to the server and did not restart V11.30.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting `git status --short --untracked-files=all`: empty
- Readiness before changes: passed
- Guard approval source:
  `reports/audits/task96u_v1130_decision_telemetry_guard_review.md`

## Files Changed

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
tests/test_regime_aware_v1130_crash_rebound_shadow.py
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
reports/audits/task96v_v1130_behavior_neutral_final_decision_telemetry.md
tasks/active/TASK-0096V-v1130-behavior-neutral-final-decision-telemetry.md
```

## Implementation

Added strategy helper methods that write:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

The output can be redirected with:

```text
V1130_FINAL_DECISION_TELEMETRY_JSON
V1130_FINAL_DECISION_TELEMETRY_MD
```

The output aggregates by pair under:

```text
pairs[<pair>]
```

This matters because Freqtrade calls `populate_entry_trend` once per pair; a
single overwrite-only report would risk preserving only the last processed pair.

The output can be disabled with:

```text
V1130_FINAL_DECISION_TELEMETRY_DISABLE=1
```

The write path is wrapped defensively. Telemetry write failure returns silently
and does not change the dataframe returned to Freqtrade.

## Telemetry Fields

The generated report records:

- `pair`
- `timeframe`
- `candle_time`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `candle_return`
- `candle_range`
- `rsi`
- `volume_ratio`
- `candidate`
- `alpha_filter_block_short`
- `alpha_risk_flags`
- `taker_sell_pressure`
- `v1130_crash_rebound_gate`
- `enter_long`
- `enter_tag`

Observed values are marked as `observed`. Computed values are marked as
`derived`. Missing or unprovable values are marked as `missing` or `unknown`;
they are not converted to `0`.

## Behavior-Neutral Proof

Added test:

```text
test_final_decision_telemetry_does_not_change_entry_decision
```

It runs the same dataframe twice:

1. telemetry disabled;
2. telemetry enabled and redirected to a temporary directory.

The test asserts equality for:

```text
enter_long
enter_tag
v1130_crash_rebound_gate
```

It also asserts the telemetry file exists and includes `safety_verdict =
telemetry_only_no_behavior_change`.

## Generated Local Sample

Generated sample files:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

Important boundary:

```text
sample_source = local test fixture
```

This sample is not live V11.30 execution evidence and does not prove replacement
readiness.

Sample summary:

| field | value |
|---|---:|
| pairs_observed | `2` |
| rows_observed | `6` |
| candidate_rows | `4` |
| enabled_rows | `4` |
| blocked_rows | `0` |
| safety_verdict | `telemetry_only_no_behavior_change` |

## Verification

Executed with bundled Python:

```text
C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile strategies/RegimeAwareV1130CrashReboundShadow.py tests/test_regime_aware_v1130_crash_rebound_shadow.py
C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_regime_aware_v1130_crash_rebound_shadow
```

Result:

```text
py_compile: pass
unit tests: 9 passed
```

Final required verification:

```text
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Safety Boundary

This task did not:

- change entry thresholds;
- change exit thresholds;
- change pairlist;
- change stake;
- change leverage;
- change ROI;
- change stoploss;
- change order type;
- change bot config;
- change dashboard;
- change deploy files;
- read `.env`;
- read `user_data/monitor.env`;
- use API credentials;
- write SQLite;
- start, stop, or restart any bot;
- log in to the server for V11.30 deployment;
- decide whether V11.30 can replace V10.8.2.

## Recommended Next Task

Proceed with:

```text
Task 96W: Deploy V11.30 final decision telemetry to server
```

Task 96W must be a separate explicit server-runtime task. It should copy only
the approved strategy file, restart or reload only the V11.30 shadow container
if authorized, and then observe whether live telemetry files are produced.
