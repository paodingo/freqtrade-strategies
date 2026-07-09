# Task 131: Ranging Short Alpha-State Reconstruction Plan

## Summary

Defined a read-only reconstruction plan for the missing alpha/taker/protection
state in the `ranging_short_volatility_fade` research candidate.

Decision:

```text
alpha_state_reconstruction_required_before_strategy_or_backtest
```

The existing ranging-short evidence is large but OHLCV-derived. It cannot
authorize a strategy implementation, Freqtrade backtest, or deployment until the
missing alpha-state path is reconstructed or explicitly proven unavailable.

## Source Evidence

| source | path |
|---|---|
| Task 128 deep review | `reports/audits/task128_ranging_short_candidate_evidence_deep_review.md` |
| historical study JSON | `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json` |
| historical study Markdown | `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md` |

## Missing State To Reconstruct

| field | current state | why it matters |
|---|---|---|
| `alpha_risk_flags` | `missing` | Determines whether historical short entries were blocked by crowding/taker flags |
| `taker_buy_pressure` | `missing` | Short candidates may be unsafe during taker-buy pressure |
| `taker_sell_pressure` | `missing` | Helps distinguish continuation from exhaustion |
| `protection_blocked` | `unknown` | Live strategy may reject otherwise valid signals |
| `pairlist_included` | `unknown` | Candidate pairs may not have been tradable in the runtime universe |
| `max_open_trades_blocked` | `unknown` | Live execution may be blocked even when signal exists |
| `wallet_or_stake_blocked` | `unknown` | A signal is not an executable trade without stake availability |

## Reconstruction Strategy

Use a staged read-only approach:

1. Inventory available committed reports for any historical alpha/taker fields.
2. Inventory server-side non-secret OHLCV and telemetry files by path/mtime only.
3. If authorized later, build a read-only reconstruction report that joins
   historical candidate timestamps with available alpha/taker telemetry.
4. Mark every unreconstructable field as `unknown`, not `false`.

## Proposed Future Exact Paths

Future implementation should be reviewed by a separate exact path task before
guard changes. Candidate paths:

```text
scripts/build_ranging_short_alpha_state_reconstruction.js
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.json
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.md
```

Do not allow broad rules such as:

```text
reports/ranging_short_research/**
scripts/build_ranging_short_*
reports/**/*ranging_short*
```

## Acceptance Criteria

The reconstruction can support a later calibration decision only if it reports:

- candidate count after alpha/taker/protection filters;
- blocked count by reason;
- per-pair and per-day concentration;
- fee-adjusted forward returns after removing blocked candidates;
- whether source data is recent enough for 2026-07 runtime conditions;
- whether the result remains OHLCV-derived or becomes alpha-observed.

## Explicit Non-Conclusion

This plan does not conclude:

- ranging-short is profitable;
- ranging-short should be implemented;
- a backtest should be run;
- any live bot should be started, stopped, or restarted.

## Recommended Next Task

Proceed with:

```text
Task 134: Ranging Short Alpha-State Reconstruction Exact Path Review
```

Task 134 should approve exact paths only. It should not modify strategies or bot
configs.

