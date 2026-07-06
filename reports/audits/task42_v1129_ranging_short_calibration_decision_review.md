# Task 42: V11.29 Ranging-Short Calibration Decision Review

## Summary

This task reviews the V11.29 ranging-short calibration evidence from Task 39
and Task 41. It does not modify strategy code, bot configuration, dashboard,
deploy files, data files, SQLite files, or server runtime state.

Decision:

```text
Proceed to a separately authorized shadow/dry-run design task, but do not
modify live V11.29 strategy/config yet.
```

The ranging-short research lane should not be rejected outright, because the
30d feather-derived study produced enough samples and a slightly positive
fee-adjusted 4-candle aggregate. It also should not be enabled live, because
runtime alpha-allowed evidence was negative in the short sample, historical
alpha state is missing, and no execution-quality evidence exists.

## Evidence Reviewed

Task 39 runtime-data candidate study:

| Field | Result |
| --- | --- |
| Source | V11.29 runtime `pair_candles` API |
| Window | about 5.49 days |
| Candidates | 111 |
| Alpha state | observed runtime alpha split |
| 4-candle fee-adjusted mean | -16.4547 bps |
| Alpha-allowed 4-candle fee-adjusted mean | -15.5344 bps |
| Classification | `insufficient` |

Task 41 feather-based historical study:

| Field | Result |
| --- | --- |
| Source | server container feather files |
| Window | 30 days ending 2026-07-03 |
| Candidates | 1214 |
| Alpha state | `missing` |
| 4-candle fee-adjusted mean | 0.1647 bps |
| 8-candle fee-adjusted mean | 7.3426 bps |
| Classification | `research_candidate` |

## Decision Rationale

The evidence is mixed:

- The live runtime-style sample is recent and includes alpha information, but
  it is too short and currently negative after fees.
- The 30d feather sample has enough candidates and slightly positive aggregate
  behavior, but it is OHLCV-derived and lacks historical alpha state.
- Pair-level results are uneven. Some pairs are positive, others are clearly
  negative.
- No evidence here measures real orders, fills, funding, slippage, latency, or
  actual dry-run execution quality.

Therefore:

- Rejecting the lane now would be premature.
- Enabling it live now would be unsafe.
- The correct next step is a narrow, explicitly authorized shadow/dry-run
  design that still does not replace V10.8.2 and does not change the existing
  V11.29 live strategy in-place.

## Pair Filter Implications

Task 41 pair-level 4-candle fee-adjusted means:

| Pair | Candidates | 4-candle fee-adjusted mean bps | Decision Hint |
| --- | ---: | ---: | --- |
| ETH/USDT:USDT | 65 | 14.8993 | Review as candidate |
| AVAX/USDT:USDT | 138 | 6.0043 | Review as candidate |
| LINK/USDT:USDT | 104 | 3.4790 | Review as candidate |
| BCH/USDT:USDT | 106 | 3.0939 | Review as candidate |
| XRP/USDT:USDT | 112 | 2.3791 | Review as candidate |
| DOGE/USDT:USDT | 94 | 1.0184 | Needs sample caution |
| LTC/USDT:USDT | 158 | 0.4521 | Thin edge |
| BTC/USDT:USDT | 97 | -0.1956 | Needs caution |
| BNB/USDT:USDT | 110 | -4.3756 | Exclude unless new evidence |
| TRX/USDT:USDT | 7 | -6.5083 | Exclude or insufficient |
| SOL/USDT:USDT | 133 | -7.6870 | Exclude unless new evidence |
| ADA/USDT:USDT | 90 | -12.6730 | Exclude unless new evidence |

This points toward a pair-filtered research lane, not a broad all-pair enable.

## Required Alpha Handling

Historical alpha state is currently missing in Task 41. Any later shadow/dry-run
design must choose one of these approaches explicitly:

1. Preserve current alpha filter behavior and only allow candidates that pass
   runtime `alpha_filter_block_short == false`.
2. Run alpha as an observed telemetry field but keep it blocking by default.
3. Do not bypass alpha unless a separate task proves that alpha is blocking the
   profitable subset.

Default recommendation:

```text
Keep alpha blocking active.
```

Task 39 showed alpha-allowed runtime candidates were still negative in the
short sample, so there is no evidence that bypassing alpha would help.

## Shadow/Dry-Run Design Requirements

Any Task 43 design should be separate from the existing V11.29 live strategy
and must include:

- exact strategy file path if a new shadow strategy is proposed;
- exact bot config path if a new dry-run bot is proposed;
- separate database path;
- separate Telegram label / dashboard label if monitored;
- explicit pair allowlist;
- no live-money trading;
- no modification of V10.8.2;
- no modification of current V11.29 production-like config;
- explicit stop conditions.

Minimum stop conditions:

- API instability or monitor failure;
- zero candidates for a defined observation period;
- adverse excursion exceeding design threshold;
- unexpected live order placement;
- missing alpha telemetry;
- config or DB path mismatch.

## Current Decision

| Question | Decision |
| --- | --- |
| Reject ranging-short lane now? | No |
| Enable live V11.29 ranging-short now? | No |
| Modify existing V11.29 strategy/config now? | No |
| Proceed to shadow/dry-run design? | Yes, with separate authorization |
| Claim V11.29 can replace V10.8.2? | No |

## Recommended Task 43

Recommended next task:

```text
Task 43: V11.29 Ranging-Short Shadow Dry-Run Design
```

Scope:

- Design but do not yet deploy a separate shadow dry-run lane.
- Define exact files that would need guard exceptions in a later implementation
  task.
- Define pair allowlist from Task 41 candidates.
- Keep alpha blocking active by default.
- Define database, label, monitoring, and stop conditions.
- Do not edit strategy/config in Task 43 unless separately authorized.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- download or refresh market data;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Verification

Required completion checks:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

