# V11.31 Longer Replay Data Acquisition Plan

## Summary

This is a plan-only artifact. It does not acquire data, access the server, run backtests, modify strategy/config files, or make any profitability/deployment claim.

## Current Evidence

| field | state |
| --- | --- |
| approved pairs | ETH/USDT:USDT, SOL/USDT:USDT, DOGE/USDT:USDT, LINK/USDT:USDT, XRP/USDT:USDT, BCH/USDT:USDT |
| 15m source rows per pair | 88271 |
| committed replay rows per pair | 240 |
| committed replay days per pair | 2.5 |
| 15m supports 7d review | false |
| 15m supports 14d review | false |
| 4h source state | unknown |
| alpha/taker/protection | missing or unknown |

## Acquisition Targets

| pair | observed 15m source | rows | committed rows | 4h discovery needed |
| --- | --- | --- | --- | --- |
| ETH/USDT:USDT | /freqtrade/project/user_data/data/futures/ETH_USDT_USDT-15m-futures.feather | 88271 | 240 | true |
| SOL/USDT:USDT | /freqtrade/project/user_data/data/futures/SOL_USDT_USDT-15m-futures.feather | 88271 | 240 | true |
| DOGE/USDT:USDT | /freqtrade/project/user_data/data/futures/DOGE_USDT_USDT-15m-futures.feather | 88271 | 240 | true |
| LINK/USDT:USDT | /freqtrade/project/user_data/data/futures/LINK_USDT_USDT-15m-futures.feather | 88271 | 240 | true |
| XRP/USDT:USDT | /freqtrade/project/user_data/data/futures/XRP_USDT_USDT-15m-futures.feather | 88271 | 240 | true |
| BCH/USDT:USDT | /freqtrade/project/user_data/data/futures/BCH_USDT_USDT-15m-futures.feather | 88271 | 240 | true |

## Future Execution Boundary

- Future data acquisition requires separate authorization before any server access.
- Future checks must remain read-only and non-secret.
- The pair set must remain exact unless a later review explicitly changes it.
- No backtest may run until a future replay gate review approves it.

## Blocking Gaps

- Actual longer replay data was not acquired in this task.
- 4h informative source path and row-level coverage remain unknown.
- Committed replay artifacts still cover only the latest 240 15m candles per pair.
- Alpha/taker/protection evidence remains missing or unknown.
- Backtest remains blocked until a future replay gate review approves it.

## Decisions

| decision | value |
| --- | --- |
| can acquire now | false |
| can reconsider backtest | false |
| can deploy shadow | false |
| can claim profitability | false |

## Recommended Next Task

Task 162: V11.31 Longer Replay Data Acquisition Execution Authorization
