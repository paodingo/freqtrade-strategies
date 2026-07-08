# Task 96U: V11.30 Decision Telemetry Guard Review

## Summary

Reviewed and patched the exact guard surface required for the next
behavior-neutral V11.30 final decision telemetry task.

Conclusion:

```text
exact_final_decision_telemetry_outputs_allowed
```

This task only extended guard exceptions for two generated telemetry output
files. It did not implement telemetry, modify strategy behavior, change bot
config, deploy code, restart bots, or touch server runtime.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting `git status --short --untracked-files=all`: empty
- Readiness before changes: passed
- Source plan: `reports/audits/task96t_v1130_decision_telemetry_instrumentation_plan.md`

## Guard Changes

Added exact output paths only:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

Changed guard files:

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
```

## Existing Exact Paths Already Allowed

The current guards already allow these exact V11.30 implementation surfaces:

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
tests/test_regime_aware_v1130_crash_rebound_shadow.py
```

Task 96U did not add new strategy, config, dashboard, deploy, SQLite, or server
runtime allowances.

## Explicit Non-Allowances

This task did not allow:

- `reports/v1130_observation/**`
- `scripts/build_v1130_*`
- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- SQLite snapshot files
- real trading evidence wildcards
- server runtime commands
- bot lifecycle scripts
- API credentials or secrets

## Why This Is Needed

Task 96S showed that current V11.30 runtime surfaces cannot expose final
decision fields:

- `alpha_filter_block_short`
- `alpha_risk_flags`
- `taker_sell_pressure`
- `v1130_crash_rebound_gate`
- `enter_long`
- `enter_tag`

Task 96T therefore recommended behavior-neutral final decision telemetry. The
next implementation task needs a place to write the generated telemetry report
without opening a broad V11.30 reports directory.

## Required Task 96V Boundary

Task 96V may proceed only if it remains behavior-neutral:

- no threshold changes;
- no pairlist changes;
- no stake, leverage, ROI, stoploss, or order-type changes;
- no exit logic changes;
- no config changes;
- no dashboard changes;
- no server deployment or restart;
- no secret reads;
- no SQLite writes;
- no replacement conclusion.

Task 96V must prove that `enter_long`, `enter_tag`, and
`v1130_crash_rebound_gate` remain unchanged for the same input dataframe.

## Verification

Executed verification:

```text
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Result:

```text
node --check scripts/guard_harness_diff.js: pass
node --check scripts/guard_trading_surface.js: pass
readiness: pass
```

Exact allow self-test:

```text
guard_harness_diff allowed:
- reports/v1130_observation/v1130_final_decision_telemetry.json
- reports/v1130_observation/v1130_final_decision_telemetry.md

guard_trading_surface allowed:
- reports/v1130_observation/v1130_final_decision_telemetry.json
- reports/v1130_observation/v1130_final_decision_telemetry.md
```

Adjacent-path blocking self-test:

```text
guard_harness_diff blocked:
- reports/v1130_observation/v1130_final_decision_telemetry_extra.json
- reports/v1130_observation/other_runtime_report.json
- scripts/build_v1130_final_decision_telemetry.js
```

`guard_trading_surface` intentionally does not block ordinary unknown report or
script paths by itself; the combined readiness gate relies on
`guard_harness_diff` to enforce the low-risk harness allowlist and
`guard_trading_surface` to block trading surfaces.

Final status must only include Task 96U and parallel Task 97B authorized files.

## Recommended Next Task

Proceed with:

```text
Task 96V: Implement V11.30 behavior-neutral final decision telemetry
```

Do not deploy or restart V11.30 until a later explicit rollout task.
