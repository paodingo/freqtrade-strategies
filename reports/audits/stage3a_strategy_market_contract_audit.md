# Stage 3A Strategy-Market Contract Audit

## Decision

Stage 3A must use a futures baseline for `RegimeAwareV6`.

## Evidence

- `strategies/regime_aware_base.py:22` declares `can_short = True`.
- `strategies/regime_aware_base.py:242` initializes `enter_short`.
- `strategies/regime_aware_base.py:279` emits `enter_short = 1` with `trending_short`.
- `strategies/regime_aware_base.py:302` emits `enter_short = 1` with `ranging_short`.
- `strategies/regime_aware_base.py:411` branches custom entry pricing on `side == "short"`.
- `strategies/regime_aware_base.py:425` branches custom exit pricing on `trade.is_short`.
- `strategies/regime_aware_base.py:37` requests informative pairs with `CandleType.FUTURES`.
- `user_data/config_btc_futures_v6.json:12` uses `trading_mode: futures`.
- `user_data/config_btc_futures_v6.json:13` uses `margin_mode: isolated`.
- `user_data/config_btc_futures_v6.json:28` fixes the historical V6 pair to `BTC/USDT:USDT`.
- `docs/backtests/2026-06-11-v66-alpha-risk-backtest.md:9` reports a futures pair `BTC/USDT:USDT`.
- `docs/backtests/2026-06-11-v66-alpha-risk-backtest.md:27` records long/short counts for the benchmark result.
- `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md:41` records `BTC/USDT:USDT` ranging-short candidates.
- `reports/audits/task55_v1129_live_signal_miss_root_cause_audit.md:7` describes the runtime as `running / dry_run / futures / 15m`.

## Rejected Spot Interpretation

The prior `demo-sealed-offline-backtest` config used `trading_mode: spot` and `BTC/USDT`, but that was a Stage 3A execution-plane demo mismatch. It does not match the strategy's real semantics. Modifying `RegimeAwareV6.can_short`, suppressing short signals, or wrapping the strategy would change the strategy contract and is forbidden.

## Required Stage 3A Contract

- strategy: original `strategies/RegimeAwareV6.py`
- market: Binance USD-M futures
- trading mode: `futures`
- margin mode: `isolated`
- pair: `BTC/USDT:USDT`
- stake/settle currency: `USDT`
- dataset: futures OHLCV plus mark/funding or an explicitly synthetic funding execution-only contract
- metadata snapshot: futures/swap metadata, not the existing spot snapshot

## Completion Status

This audit selects futures. Stage 3A remains incomplete until the futures snapshot, futures dataset, leverage-tier contract, online/offline comparison, and RUN-A/RUN-B reproducibility checks all pass.
