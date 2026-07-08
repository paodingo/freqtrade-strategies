# Task 61: V11.30 Local Replay Consistency Check

## Summary

Completed a local-only consistency check for the V11.30 crash-rebound shadow
implementation. The implemented strategy/config matches the Task 58 candidate
selection and Task 59 implementation plan at the gate, alpha-policy, sizing,
pair, and dry-run identity levels.

This task did not deploy files, start a bot, stop a bot, run a backtest, read
secrets, or touch server/live runtime state.

## Inputs Reviewed

- `reports/audits/task58_v1130_candidate_selection.md`
- `reports/audits/task59_v1130_crash_rebound_shadow_implementation_plan.md`
- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json`
- `strategies/RegimeAwareV1130CrashReboundShadow.py`
- `user_data/config_multi_futures_v1130_crash_rebound_shadow.json`
- `tests/test_regime_aware_v1130_crash_rebound_shadow.py`

## Task 58 Replay Baseline

Observed from `v1129_high_volatility_replay_scorecard.json`:

- `final_entry_rows`: `0`
- `crash_rebound` sample count: `15`
- `crash_rebound` 4-candle fee-adjusted mean bps: `21.5559`
- `crash_rebound` 4-candle positive rate: `0.6667`
- `crash_rebound` 8-candle fee-adjusted mean bps: `51.9828`
- `crash_rebound` 8-candle positive rate: `0.6667`

Task 58 selected `V11.30 Crash Rebound Long Shadow` as the next dry-run shadow
candidate, not a production/live replacement.

## Gate Consistency

Implemented gate matches Task 59:

| Field | Planned | Implemented | Status |
|---|---:|---:|---|
| direction | long only | `can_short = False`; only `enter_long` emitted | consistent |
| timeframe | `15m` | `timeframe = "15m"` | consistent |
| entry tag | `v1130_crash_rebound_long` | `v1130_crash_rebound_long` | consistent |
| 15m return | `> 0.004` | `shadow_min_15m_return = 0.004` with strict `>` | consistent |
| 15m range | `>= 0.012` | `shadow_min_15m_range = 0.012` with `>=` | consistent |
| RSI | `35 <= rsi <= 62` | `shadow_min_rsi = 35`, `shadow_max_rsi = 62` | consistent |
| volume | `volume > volume_mean * 0.8` | `shadow_min_volume_ratio = 0.8` with `>` | consistent |
| alpha short block | hard veto | `alpha_filter_block_short` blocks entry | consistent |
| taker sell pressure | hard veto | `takerSellPressure` blocks with specific gate reason | consistent |
| alpha long crowding | not hard veto | tested as allowed | consistent |

Implemented gate telemetry:

- `not_candidate`
- `blocked_pair_not_allowlisted`
- `blocked_missing_columns:<columns>`
- `blocked_alpha_short`
- `blocked_taker_sell_pressure`
- `enabled_crash_rebound_long`

## Pair And Config Consistency

Implemented strategy allowlist:

- `ETH/USDT:USDT`
- `SOL/USDT:USDT`
- `DOGE/USDT:USDT`
- `LINK/USDT:USDT`
- `XRP/USDT:USDT`
- `BCH/USDT:USDT`

Implemented config allowlist has the same six pairs.

Config identity:

- strategy: `RegimeAwareV1130CrashReboundShadow`
- dry-run: `true`
- max open trades: `2`
- stake amount: `250`
- tradable balance ratio: `0.2`
- DB URL: `sqlite:////freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite`
- `api_server`: absent

## Test Coverage

Task 60 unit tests cover:

- successful crash-rebound long entry;
- long-crowding does not hard-block entry;
- `takerSellPressure` blocks entry;
- `alpha_filter_block_short` blocks entry;
- missing required columns fail closed;
- non-allowlisted pairs are blocked;
- V11.30 long stake is capped at `250`;
- V11.30 exits are isolated from non-V11.30 parent entries.

## Validation Commands

Commands run:

```powershell
C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tests\test_regime_aware_v1130_crash_rebound_shadow.py
C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile strategies\RegimeAwareV1130CrashReboundShadow.py tests\test_regime_aware_v1130_crash_rebound_shadow.py
node -e "<scorecard summary parse>"
.\scripts\run_agent_readiness_checks.ps1
```

Results:

- unit tests: `Ran 8 tests ... OK`
- Python compile: passed
- scorecard JSON parse: passed
- strategy/config constant inspection: passed
- readiness checks: passed

## What This Cannot Conclude

This task cannot conclude:

- V11.30 is profitable;
- V11.30 can replace V10.8.2;
- V11.30 can replace V11.29;
- V11.30 is safe for live trading;
- dry-run orders will appear after deployment.

It only confirms that the local implementation matches the selected
crash-rebound shadow plan and is ready for a separate server preflight/placement
task.

## Boundaries

This task did not:

- deploy to the server;
- start, stop, or restart any bot;
- run `freqtrade trade`;
- run a backtest;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- modify strategy/config outside the already committed Task 60 files;
- modify the original dirty workspace.

## Recommended Next Task

Recommended next task:

```text
Task 62: V11.30 Server Preflight And Exact File Placement
```

Scope:

- read-only server resource check;
- exact placement plan for only the V11.30 strategy/config;
- no bot start yet;
- no bot stop unless a separate resource-management task explicitly authorizes
  it.
