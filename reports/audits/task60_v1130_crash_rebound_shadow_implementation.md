# Task 60: V11.30 Crash Rebound Shadow Local Implementation

## Summary

Implemented a local-only V11.30 crash-rebound long shadow strategy, dry-run
configuration, and focused unit tests. This task did not deploy the strategy,
start a bot, stop a bot, run a backtest, or touch server/live runtime state.

## Implemented Files

- `strategies/RegimeAwareV1130CrashReboundShadow.py`
- `user_data/config_multi_futures_v1130_crash_rebound_shadow.json`
- `tests/test_regime_aware_v1130_crash_rebound_shadow.py`

## Strategy Design

- parent class: `RegimeAwareV66AlphaRisk`
- direction: long only
- entry tag: `v1130_crash_rebound_long`
- timeframe: `15m`
- position adjustment: disabled
- stoploss: `-0.02`
- dry-run shadow stake cap: `250`

The implementation intentionally avoids the clean-worktree missing parent
`RegimeAwareV1129ResidualDragMicroSizer`.

## Entry Gate

Allowed pairs:

- `ETH/USDT:USDT`
- `SOL/USDT:USDT`
- `DOGE/USDT:USDT`
- `LINK/USDT:USDT`
- `XRP/USDT:USDT`
- `BCH/USDT:USDT`

Required gate:

- 15m return greater than `0.004`
- 15m candle range at least `0.012`
- `35 <= rsi <= 62`
- `volume > volume_mean * 0.8`
- `alpha_filter_block_short == false`
- `alpha_risk_flags` does not include `takerSellPressure`
- `volume > 0`

Gate telemetry column:

- `v1130_crash_rebound_gate`

Gate states implemented:

- `not_candidate`
- `blocked_pair_not_allowlisted`
- `blocked_missing_columns:<columns>`
- `blocked_alpha_short`
- `blocked_taker_sell_pressure`
- `enabled_crash_rebound_long`

## Alpha-Risk Policy

- `alpha_filter_block_short` is a hard veto.
- `takerSellPressure` is a hard veto with a specific gate reason.
- `alpha_filter_block_long` is not a hard veto in this first shadow version.
- Long-crowding flags are preserved for observation but do not block entry.

## Exit And Stake Policy

V11.30-specific exits:

- `v1130_rebound_take_profit` when `current_profit >= 0.008`
- `v1130_rebound_rsi_exit` when analyzed `rsi > 68`
- `v1130_rebound_time_exit` after `120` minutes

Non-V11.30 entries fall back to parent exit behavior.

Stake behavior:

- V11.30 long entries are capped at `250`.
- Non-V11.30 entries fall back to parent stake behavior.

## Config

Created dry-run config:

- `user_data/config_multi_futures_v1130_crash_rebound_shadow.json`

Important config properties:

- `dry_run: true`
- `max_open_trades: 2`
- `stake_amount: 250`
- `tradable_balance_ratio: 0.2`
- `db_url: sqlite:////freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite`
- no `api_server` block

## Validation

Commands run:

```powershell
C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile strategies\RegimeAwareV1130CrashReboundShadow.py tests\test_regime_aware_v1130_crash_rebound_shadow.py
C:\Users\paodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tests\test_regime_aware_v1130_crash_rebound_shadow.py
```

Results:

- Python compile: passed
- unit tests: `Ran 8 tests ... OK`
- config JSON parse: passed
- `api_server` presence check: absent

Note: local `python` command is unavailable in this Windows environment, and
the bundled Python does not include `pytest`; the test is written as
`unittest` and was executed directly with the bundled Python runtime.

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
- modify V11.29 strategy/config/report evidence;
- modify the original dirty workspace.

## Recommended Next Task

Recommended next task:

```text
Task 61: V11.30 Local Replay Consistency Check
```

Scope:

- compare this implementation against Task 58/59 selected gate semantics;
- verify exact config identity and no API-server secret surface;
- keep the check local-only;
- do not deploy or start V11.30 yet.
