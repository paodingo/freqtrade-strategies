# Task 43: V11.29 Ranging-Short Shadow Dry-Run Design

## Summary

This task designs a separate V11.29 ranging-short shadow dry-run lane. It does
not implement the lane, does not modify strategy code, does not modify bot
configuration, and does not start/stop/restart any container.

Design decision:

```text
Proceed only as a separate shadow dry-run lane, not as an in-place change to
the current V11.29 bot.
```

The proposed lane exists to answer one question:

```text
Can a pair-filtered, alpha-blocked ranging-short variant produce real dry-run
orders with acceptable execution quality?
```

It is not a V11.29 replacement decision and not a live-money trading plan.

## Evidence Basis

Task 39 runtime candidate study:

- recent runtime window: about 5.49 days;
- 111 candidates;
- alpha observed;
- 4-candle fee-adjusted mean: `-16.4547 bps`;
- alpha-allowed 4-candle fee-adjusted mean: `-15.5344 bps`;
- classification: `insufficient`.

Task 41 feather historical study:

- 30d OHLCV-derived study ending 2026-07-03;
- 1214 derived candidates;
- 4-candle fee-adjusted mean: `0.1647 bps`;
- 8-candle fee-adjusted mean: `7.3426 bps`;
- alpha state: `missing`;
- classification: `research_candidate`.

Task 42 decision:

- do not reject the lane outright;
- do not enable live V11.29 ranging-short in-place;
- proceed to a separately authorized shadow/dry-run design.

## Proposed Shadow Lane Identity

Recommended name:

```text
V11.29 ranging-short shadow dry-run
```

Suggested identifiers for a later implementation task:

| Item | Suggested value | Status |
| --- | --- | --- |
| Strategy class | `RegimeAwareV1129RangingShortShadow` | design only |
| Strategy file | `strategies/RegimeAwareV1129RangingShortShadow.py` | not created |
| Config file | `user_data/config_multi_futures_v1129_ranging_short_shadow.json` | not created |
| Database | `sqlite:////freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite` | not created |
| Container | `freqtrade-v1129-ranging-short-shadow` | not created |
| API port | choose an unused localhost-only port, e.g. `8123` | not bound |
| Dashboard label | `V11.29 ranging-short shadow` | not configured |
| Telegram label | `V11.29 ranging-short shadow` | not configured |

Any later implementation must be separately authorized because these paths
touch blocked strategy/config/server surfaces.

## Pair Allowlist Design

Task 41 pair-level 4-candle fee-adjusted means suggest a pair-filtered lane.

Recommended initial allowlist:

| Pair | Reason |
| --- | --- |
| `ETH/USDT:USDT` | Positive 4-candle fee-adjusted mean; 65 samples |
| `AVAX/USDT:USDT` | Positive 4-candle fee-adjusted mean; 138 samples |
| `LINK/USDT:USDT` | Positive 4-candle fee-adjusted mean; 104 samples |
| `BCH/USDT:USDT` | Positive 4-candle fee-adjusted mean; 106 samples |
| `XRP/USDT:USDT` | Positive 4-candle fee-adjusted mean; 112 samples |

Watch-only / not initially enabled:

| Pair | Reason |
| --- | --- |
| `DOGE/USDT:USDT` | Positive but small edge; fewer than 100 samples in Task 41 |
| `LTC/USDT:USDT` | Very thin edge despite larger sample |
| `BTC/USDT:USDT` | Slightly negative 4-candle mean |

Explicit initial exclusions:

| Pair | Reason |
| --- | --- |
| `BNB/USDT:USDT` | Negative Task 41 pair result |
| `TRX/USDT:USDT` | Too few candidates and negative result |
| `SOL/USDT:USDT` | Negative Task 41 pair result |
| `ADA/USDT:USDT` | Negative Task 41 pair result |

The allowlist must not be broadened to all pairs without a new evidence task.

## Alpha Policy

Default policy:

```text
Keep alpha blocking active.
```

Rationale:

- Task 41 cannot reconstruct historical alpha state.
- Task 39 has recent alpha-observed runtime evidence, but alpha-allowed
  candidates were still negative in the short sample.
- There is no evidence that bypassing alpha improves the lane.

Required behavior for a later implementation:

- candidate may only become final `enter_short` if
  `alpha_filter_block_short == false`;
- alpha state must be logged as telemetry;
- if alpha telemetry is missing, the candidate must remain blocked.

## Candidate Logic Design

The shadow lane should not mutate current V11.29 in-place. It should be a
separate strategy class that:

1. Inherits from the current V11.29 strategy or composes its logic in a clearly
   reviewable way.
2. Preserves all current V11.29 protections unless explicitly overridden.
3. Adds a separate path for `v66_ranging_short_edge`-style candidates.
4. Applies the pair allowlist.
5. Applies alpha short blocking.
6. Uses a small, explicit stake cap for dry-run only.
7. Emits clear `enter_tag`, for example:

```text
v1129_shadow_ranging_short
```

The later implementation must avoid ambiguous tags that look like production
V11.29 replacement proof.

## Risk Controls

Minimum controls for later implementation:

| Control | Requirement |
| --- | --- |
| Mode | dry-run only |
| Pair allowlist | explicit list, no wildcard |
| Alpha | blocking active by default |
| Stake | smaller than main V11.29 dry-run stake |
| DB | separate SQLite file |
| API | separate localhost-only port |
| Monitoring | separate label |
| Lifecycle | no auto-start until authorized |
| Dashboard | optional, must not merge with V10.8.2/V11.29 baseline labels |

## Observation Requirements

The shadow lane should not be evaluated on candidate count alone. It needs
real dry-run execution evidence:

- trades;
- orders;
- open/closed trade counts;
- order price;
- filled price;
- fee;
- funding fee if available;
- slippage bps;
- latency where measurable;
- entry tag;
- exit reason;
- pair;
- side;
- open time;
- close time;
- bot uptime;
- API errors and monitor failures.

If there are no orders, the result remains `insufficient`.

## Stop Conditions

The shadow lane must stop or be reviewed if any of these occur:

- API health is unstable for the shadow bot;
- Telegram/dashboard monitor cannot distinguish the shadow lane from existing
  bots;
- alpha telemetry is missing or cannot be trusted;
- DB path does not match the design;
- unexpected live-money trading mode is detected;
- pair allowlist differs from the approved list;
- strategy/config path differs from the approved list;
- no candidates or no orders after the agreed observation window;
- adverse excursion or drawdown exceeds the later-approved dry-run threshold;
- server resource pressure becomes unacceptable.

## Files Requiring Later Explicit Authorization

Potential implementation files, not created in this task:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Potential server/runtime artifacts, not created in this task:

```text
user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
freqtrade-v1129-ranging-short-shadow
localhost shadow API port such as 8123
```

Any future task that touches these paths must first expand guard allowlists with
exact paths and must state the operational boundary explicitly.

## Recommended Task 44

Recommended next task:

```text
Task 44: V11.29 Ranging-Short Shadow Implementation Plan
```

Scope:

- Produce a concrete implementation plan and exact allowlist for strategy,
  config, DB path, container name, port, and monitor labels.
- Do not implement yet unless the task explicitly authorizes strategy/config
  edits.
- Include rollback and observation plan.

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

