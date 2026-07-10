# Ranging Short Alpha/Taker Source Acquisition Plan

## Summary

This is a plan-only artifact. It does not access the server, acquire data, run backtests, modify strategy/config files, or make profitability/deployment claims.

## Current Research Evidence

| field | value |
| --- | --- |
| candidate count | 1214 |
| pair count | 12 |
| latest pair data max | 2026-07-03T08:45:00+00:00 |
| source method | derived_from_ohlcv_feather |

## Acquisition Field Plan

| field | current state | source status | future source need |
| --- | --- | --- | --- |
| alpha_risk_flags | missing | missing | historical alpha-risk allowed/blocked timeline for every candidate timestamp |
| taker_buy_pressure | missing | missing | taker-buy pressure timeline aligned to candidate timestamps |
| taker_sell_pressure | missing | missing | taker-sell pressure timeline aligned to candidate timestamps |
| protection_blocked | unknown | unknown | protection/pairlock timeline, if non-secret and available |
| pairlist_included | unknown | unknown | historical pairlist membership by candidate timestamp |
| wallet_or_stake_blocked | unknown | unknown | non-secret wallet/stake blocker evidence, if explicitly authorized |

## Boundaries

- Future execution requires separate authorization before any server access.
- Missing fields remain `missing` or `unknown` until non-secret evidence proves otherwise.
- No strategy implementation, backtest, shadow deployment, or profitability claim is authorized.

## Blocking Gaps

- alpha_risk_flags: missing
- taker_buy_pressure: missing
- taker_sell_pressure: missing
- protection_blocked: unknown
- pairlist_included: unknown
- wallet_or_stake_blocked: unknown

## Recommended Next Task

Task 166: Ranging Short Alpha/Taker Source Acquisition Execution Authorization
