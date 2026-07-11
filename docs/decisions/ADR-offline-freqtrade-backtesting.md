# ADR: Offline Freqtrade Backtesting With Sealed Exchange Metadata

Status: accepted for Research Campaign Harness Stage 3A.4
Date: 2026-07-10

## Context

Stage 3A.3 proved that a local OHLCV dataset is not enough to make the standard Freqtrade CLI backtesting command hermetic. With `freqtrade==2025.8`, the standard CLI path creates `Backtesting(config)`, which creates an Exchange through `ExchangeResolver.load_exchange(...)`.

The Exchange initialization performs CCXT `load_markets()` before backtest execution. That request fetches Binance markets metadata such as `exchangeInfo`. Local OHLCV files, `StaticPairList`, fixed fee, and strategy-only changes do not remove this initial Exchange metadata load.

The observed immediate failure was:

- class: `infra_transient`
- reason: `exchange_markets_metadata_timeout`

The acceptance blocker is:

- class: `infra_permanent`
- reason: `offline_execution_contract_unsatisfied`

Neither failure is a candidate strategy failure and neither counts toward consecutive candidate failure budgets.

## Decision

The standard CLI remains useful as an online diagnostic and baseline path, but it is not the long-term hermetic Research Runner.

The project will use:

1. a real captured Binance spot markets metadata snapshot;
2. strict snapshot validation and secret scanning;
3. `ExchangeResolver.load_exchange(validate=False)` to create the real Freqtrade Binance Exchange without online validation;
4. injection of sealed markets and currencies into both sync and async CCXT objects;
5. explicit `Backtesting(config, exchange=sealed_exchange)` execution.

The adapter must not modify Freqtrade or CCXT files under site-packages. It must not use a FakeExchange or mock results for real acceptance. Any attempt to reload markets after injection is an `offline_contract_violation` and must fail rather than falling back to public endpoints.

## Consequences

Freqtrade and CCXT versions are part of the adapter contract. Changing either version invalidates the offline adapter until compatibility tests pass again.

Online CLI baseline, offline adapter control, and two independent offline reruns are distinct acceptance runs. Stage 3A is complete only when all required real runs produce matching metrics and normalized trade hashes.
