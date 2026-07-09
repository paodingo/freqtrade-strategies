# Task 134: Ranging Short Alpha-State Reconstruction Exact Path Review

## Summary

Reviewed the future path surface proposed by Task 131 for a read-only
`ranging_short_volatility_fade` alpha-state reconstruction.

Decision:

```text
approve_exact_paths_only_for_future_guard_exception
```

This review does not implement the reconstruction and does not modify strategy
or bot config files.

## Source Reviewed

```text
reports/audits/task131_ranging_short_alpha_state_reconstruction_plan.md
```

## Approved Future Exact Paths

Only these exact paths should be considered for a later guard exception task:

```text
scripts/build_ranging_short_alpha_state_reconstruction.js
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.json
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.md
```

## Explicitly Not Approved

Do not approve broad patterns such as:

```text
reports/ranging_short_research/**
scripts/build_ranging_short_*
reports/**/*ranging_short*
```

Do not approve changes under:

```text
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
reports/btc_mvp/backtests/**
reports/reliable_strategy_search_*/**
reports/api_gap_backtest_candidates/**
```

## Required Future Guard Rules

A future guard exception must:

- allow only the three exact paths listed above;
- avoid broad directory or wildcard rules;
- keep `strategies/**`, `user_data/**`, `configs/**`, `dashboard/**`, and
  `deploy/**` blocked;
- keep secrets and live/server operation surfaces blocked;
- keep the task read-only with respect to trading behavior.

## Human Review Needed

Manual review is still required before a strategy implementation or backtest can
be authorized, because the current ranging-short evidence is OHLCV-derived and
does not yet prove alpha/taker/protection state.

## Recommended Next Task

Proceed with:

```text
Task 137: Ranging Short Alpha-State Reconstruction Guard Exception
```

