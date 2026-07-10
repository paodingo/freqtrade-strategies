# V11.31 Longer Replay Data Acquisition Execution Report

## Summary

This report artifact was generated from committed evidence only. No server access, data acquisition, data copy, backtest, strategy/config edit, or bot lifecycle command was performed.

## Execution Status

| field | value |
| --- | --- |
| acquisition executed | false |
| can use as longer replay evidence | false |
| reason | This task builds the execution report artifact from committed evidence only; no server/source acquisition was performed. |

## Prior Evidence Summary

| field | value |
| --- | --- |
| approved pairs | ETH/USDT:USDT, SOL/USDT:USDT, DOGE/USDT:USDT, LINK/USDT:USDT, XRP/USDT:USDT, BCH/USDT:USDT |
| 15m source rows per pair | 88271 |
| committed replay rows per pair | 240 |
| committed replay days per pair | 2.5 |
| supports 7d review | false |
| supports 14d review | false |
| 4h source state | unknown |

## Target Results

| pair | 15m source path | prior rows | rechecked | 4h state |
| --- | --- | --- | --- | --- |
| ETH/USDT:USDT | /freqtrade/project/user_data/data/futures/ETH_USDT_USDT-15m-futures.feather | 88271 | false | unknown |
| SOL/USDT:USDT | /freqtrade/project/user_data/data/futures/SOL_USDT_USDT-15m-futures.feather | 88271 | false | unknown |
| DOGE/USDT:USDT | /freqtrade/project/user_data/data/futures/DOGE_USDT_USDT-15m-futures.feather | 88271 | false | unknown |
| LINK/USDT:USDT | /freqtrade/project/user_data/data/futures/LINK_USDT_USDT-15m-futures.feather | 88271 | false | unknown |
| XRP/USDT:USDT | /freqtrade/project/user_data/data/futures/XRP_USDT_USDT-15m-futures.feather | 88271 | false | unknown |
| BCH/USDT:USDT | /freqtrade/project/user_data/data/futures/BCH_USDT_USDT-15m-futures.feather | 88271 | false | unknown |

## Field Availability After This Task

| field | state |
| --- | --- |
| aligned_7d_15m_window | missing |
| aligned_14d_15m_window | missing |
| aligned_4h_informative_window | unknown |
| alpha_risk_timeline | unknown |
| taker_buy_pressure_timeline | unknown |
| taker_sell_pressure_timeline | unknown |
| protection_or_pairlock_timeline | unknown |

## Blocking Gaps

- No server/source acquisition was executed in this task.
- No aligned 7d or 14d local replay window artifact was created.
- 4h informative source paths remain unknown.
- Alpha/taker/protection timelines remain unknown.
- Backtest remains blocked until a later task creates and reviews actual longer-window evidence.

## Decisions

| decision | value |
| --- | --- |
| can run longer replay backtest | false |
| can deploy shadow | false |
| can claim profitability | false |
| can evaluate replacement | false |

## Recommended Next Task

Task 174: V11.31 Longer Replay Data Acquisition Execution Authorization With Exact Output Paths
