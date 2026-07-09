# Task 102: Strategy Candidate Evidence Inventory

## Summary

Read-only inventory completed for existing strategy families, historical reports,
V11.29/V11.30 evidence, high-volatility replay outputs, and available backtest
summaries.

Conclusion:

```text
candidate_search_should_start_from_existing_high_volatility_and_crash_rebound_evidence
```

This task did not run backtests, modify strategies, modify bot configs, touch
dashboard/deploy files, read secrets, or restart any bot.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `909b85f` |
| starting status | clean |
| readiness before inventory | passed |

## Evidence Sources

| source | status | use |
|---|---|---|
| `strategies/**` path listing | observed | identify existing strategy families only |
| `docs/backtests/2026-06-11-v66-alpha-family-30d.summary.json` | observed | historical V6.6/V6.7 alpha-risk backtest summary |
| `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json` | observed | high-volatility candidate-family ranking |
| `reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.json` | observed | runtime-candle ranging-short candidate study |
| `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json` | observed | 30d OHLCV-derived ranging-short study |
| `reports/v1130_observation/v1130_loose_range_replay_report.json` | observed | V11.30 loose-range replay evidence |
| `reports/v1130_observation/v1130_watch_only_telemetry_report.json` | observed | V11.30 watch/strict gate telemetry |
| `reports/v1130_observation/v1130_final_decision_telemetry.json` | observed | V11.30 final live decision telemetry |
| `reports/audits/task96x_v1130_live_final_decision_telemetry_analysis.md` | observed | V11.30 live trades/orders confirmation |
| `reports/audits/task96y_v1130_early_trade_quality_open_position_monitor.md` | observed | early trade quality and open-position monitor |
| `reports/audits/task101r_next_strategy_candidate_search_plan_refresh.md` | observed | latest candidate-search plan gate |

## Existing Strategy Families

| family | representative files | current evidence |
|---|---|---|
| V6 / V6.6 alpha-risk family | `RegimeAwareV6*.py`, `RegimeAwareV66AlphaRisk.py`, `RegimeAwareV661AlphaRisk.py`, `RegimeAwareV662AlphaRisk.py`, `RegimeAwareV67AlphaRisk.py` | historical 30d summary exists; best listed variant is `RegimeAwareV66AlphaRisk` with `85` trades and `69.8575914` absolute profit in the recorded window |
| V11.29 ranging short | `RegimeAwareV1129RangingShortShadow.py` | research-candidate evidence exists, but live/execution validation was insufficient |
| V11.30 crash-rebound long | `RegimeAwareV1130CrashReboundShadow.py` | live dry-run signals/orders/trades now observed; early quality remains insufficient/negative |
| shared regime/risk helpers | `regime_aware_base.py`, `regime_detector.py`, `risk_manager.py`, `alpha_risk_filter.py`, `trade_supervisor_filter.py` | reusable framework surface; not modified in this task |

## Historical Evidence Highlights

### V6.6 / V6.7 Alpha-Risk Summary

From `docs/backtests/2026-06-11-v66-alpha-family-30d.summary.json`:

| strategy | trades | profit_abs | winrate | profit_factor | max_drawdown_abs |
|---|---:|---:|---:|---:|---:|
| `RegimeAwareV66AlphaRisk` | `85` | `69.8575914` | `78.8235%` | `1.1434` | `107.76371559` |
| `RegimeAwareV661AlphaRisk` | `63` | `-169.15335598` | `49.2063%` | `0.6288` | `205.60495996` |
| `RegimeAwareV662AlphaRisk` | `63` | `-204.23609661` | `49.2063%` | `0.6275` | `248.04001404` |
| `RegimeAwareV67AlphaRisk` | `36` | `-82.50218060` | `52.7778%` | `0.5889` | `132.12495827` |

Interpretation:

```text
V66AlphaRisk remains useful as a historical benchmark, but it is stale versus
the current V11.30 observation context and should not be treated as current
deployment guidance.
```

### V11.29 High-Volatility Replay

From `v1129_high_volatility_replay_scorecard.json`:

| item | value |
|---|---:|
| rows observed | `8064` |
| high_volatility candidates | `43` |
| selloff_continuation candidates | `122` |
| blowoff_short candidates | `1075` |
| crash_rebound candidates | `15` |
| final_entry_rows | `0` |

Candidate ranking included:

| type | count | horizon | fee_adjusted_mean_bps | positive_rate |
|---|---:|---:|---:|---:|
| `crash_rebound` | `15` | `4` | `21.5559` | `0.6667` |
| `blowoff_short` | `1075` | `4` | `-18.6530` | `0.4009` |
| `selloff_continuation` | `122` | `4` | `-19.9735` | `0.3361` |

Interpretation:

```text
Crash-rebound was the clearest high-volatility replay candidate, which explains
why V11.30 exists. It remains a candidate family, not a proven replacement.
```

### V11.29 Ranging-Short Studies

Runtime-candle study:

| item | value |
|---|---:|
| candidate_count | `111` |
| status | `insufficient` |
| 4-candle fee-adjusted mean | `-16.4547 bps` |
| reason | runtime candle window shorter than 30d gate |

30d feather study:

| item | value |
|---|---:|
| candidate_count | `1214` |
| status | `research_candidate` |
| 4-candle fee-adjusted mean | `0.1647 bps` |
| 8-candle fee-adjusted mean | `7.3426 bps` |
| key limitation | historical alpha-risk state missing; not a backtest |

Interpretation:

```text
Ranging-short is not the immediate winner, but it remains a useful research
family for a properly controlled offline harness.
```

### V11.30 Crash-Rebound Evidence

Read-only V11.30 evidence currently says:

| evidence | value |
|---|---|
| final decision telemetry | `candidate_rows = 1`, `enabled_rows = 1`, `blocked_rows = 0` |
| Task 96X SQLite state | `trades_count = 2`, `orders_count = 3` |
| current participation | BCH-only in observed live dry-run trades |
| first closed trade | `realized_profit = -1.67763633 USDT` |
| first closed exit reason | `v1130_rebound_time_exit` |
| current state | one BCH long was still open at Task 101R refresh |

Interpretation:

```text
V11.30 can trade, but early quality is insufficient and currently negative.
No tuning or replacement conclusion is justified yet.
```

## Candidate Family Priority

| priority | family | why inspect next | key risk |
|---:|---|---|---|
| 1 | high-volatility crash/rebound continuation | best existing replay ranking; V11.30 proves live path can emit orders | early live trade quality weak; BCH concentration |
| 2 | exit-quality revision around crash-rebound | first closed V11.30 trade exited by time exit at a loss | overfitting one closed trade |
| 3 | ranging-short / volatility fade | 30d feather study has large sample and positive 8-candle fee-adjusted mean | alpha-risk state missing; not execution evidence |
| 4 | volatility breakout / continuation | aligns with recent violent windows and can be evaluated across pairs | can chase exhaustion moves |
| 5 | alpha/taker-pressure contrarian filter | converts current alpha filters from blockers into candidate features | depends on alpha-data quality and availability |
| 6 | multi-timeframe pullback continuation | less reactive than pure 15m crash-rebound | may be too slow for crash/rebound windows |

## Files Requiring Separate Authorization Before Any Change

The following are research targets only and were not modified:

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- live/server operation surface

Any strategy implementation, bot config update, dashboard fix, backtest run, or
server restart must be its own exact-scope task.

## Task 103 Input

Task 103 should verify whether recent violent windows have usable `15m`, `1h`,
and `4h` data for the current V11.30 pairs:

```text
ETH/USDT:USDT
SOL/USDT:USDT
DOGE/USDT:USDT
LINK/USDT:USDT
XRP/USDT:USDT
BCH/USDT:USDT
```

## Task 104 Input

Task 104 should design an offline search harness before any code or strategy
work. Required metrics:

- trade count;
- net profit after fees;
- max drawdown;
- pair dispersion;
- exit reason distribution;
- overfit checks.

## Safety Boundary

This task did not:

- run backtests;
- modify strategy files;
- modify bot config;
- modify dashboard or deploy files;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- force-close any V11.30 trade;
- claim V11.30 is good or bad;
- claim V11.30 can replace V10.8.2.

## Recommended Next Task

Proceed with:

```text
Task 103: High-Volatility Window Dataset Readiness Plan
```

