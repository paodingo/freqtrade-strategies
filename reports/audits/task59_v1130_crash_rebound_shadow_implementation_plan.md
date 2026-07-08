# Task 59: V11.30 Crash Rebound Shadow Implementation Plan

## Summary

This is a plan-only task for implementing a separate V11.30 crash-rebound long
shadow lane. It does not modify strategy code, bot config, server files,
dashboard code, deployment scripts, or live runtime state.

Decision from Task 58:

- selected candidate: `V11.30 Crash Rebound Long Shadow`;
- direction: long only;
- rough evidence: 12 filtered crash-rebound samples with 4-candle
  fee-adjusted mean around `+24.5853 bps` and positive rate `0.75`;
- status: enough to plan a dry-run shadow, not enough to enable live trading or
  replacement.

Important source-control constraint:

- the clean worktree currently contains
  `strategies/RegimeAwareV1129RangingShortShadow.py`;
- that file imports `RegimeAwareV1129ResidualDragMicroSizer`, but the clean
  worktree does not contain `strategies/RegimeAwareV1129ResidualDragMicroSizer.py`;
- therefore V11.30 should not depend on that hidden/server-only parent class
  unless a later task explicitly authorizes source migration and review;
- the recommended V11.30 plan uses clean-worktree source that already exists:
  `RegimeAwareV66AlphaRisk` plus a new isolated shadow class.

## Non-Actions In This Task

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
- start, stop, or restart any bot;
- run `freqtrade trade`;
- run a backtest;
- copy files to the server;
- modify the original dirty workspace.

## Proposed Architecture

Create a new strategy class:

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
```

Recommended inheritance:

```python
from RegimeAwareV66AlphaRisk import RegimeAwareV66AlphaRisk


class RegimeAwareV1130CrashReboundShadow(RegimeAwareV66AlphaRisk):
    ...
```

Reason:

- `RegimeAwareV66AlphaRisk` exists in the clean worktree;
- it already populates alpha-risk columns through `apply_alpha_filter`;
- it avoids the missing local `RegimeAwareV1129ResidualDragMicroSizer`
  dependency;
- it is safer for a separate V11.30 shadow than modifying V11.29 main.

The V11.30 strategy should preserve parent indicator generation and alpha
columns, but isolate entries by clearing inherited parent entries before setting
the V11.30 crash-rebound entry:

```python
dataframe = super().populate_entry_trend(dataframe, metadata)
dataframe["enter_long"] = 0
dataframe["enter_short"] = 0
dataframe["enter_tag"] = ""
```

Then add only the new V11.30 entry tag when all crash-rebound gates pass:

```text
v1130_crash_rebound_long
```

## Proposed Entry Gate

The Task 60 implementation should use explicit named class parameters:

```python
shadow_entry_tag = "v1130_crash_rebound_long"
shadow_stake_amount = 250
shadow_min_15m_return = 0.004
shadow_min_15m_range = 0.012
shadow_min_rsi = 35
shadow_max_rsi = 62
shadow_min_volume_ratio = 0.8
shadow_allowed_pairs = {
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "DOGE/USDT:USDT",
    "LINK/USDT:USDT",
    "XRP/USDT:USDT",
    "BCH/USDT:USDT",
}
```

Required columns:

```text
open
high
low
close
volume
volume_mean
rsi
alpha_filter_block_short
alpha_risk_flags
```

Gate logic:

```text
pair in shadow_allowed_pairs
15m open-close return > 0.004
15m high-low range / close >= 0.012
35 <= rsi <= 62
volume > volume_mean * 0.8
alpha_filter_block_short == false
alpha_risk_flags does not contain takerSellPressure
volume > 0
```

Deliberate alpha policy:

- `alpha_filter_block_short` is a hard veto because Task 58 showed cleaner
  results when removing taker-sell pressure / short-blocked rows.
- `alpha_filter_block_long` is not a hard veto because most observed profitable
  crash-rebound samples still had long-crowding flags.
- `alpha_filter_block_long` can be used later for sizing or observation labels,
  but not as a blocker in the first shadow.

Gate telemetry column:

```text
v1130_crash_rebound_gate
```

Required gate states:

```text
not_candidate
blocked_pair_not_allowlisted
blocked_missing_columns:<comma-separated-columns>
blocked_alpha_short
blocked_taker_sell_pressure
enabled_crash_rebound_long
```

## Proposed Stake And Position Policy

Initial dry-run-only sizing:

```text
stake_amount: 250 USDT
max_open_trades: 2
tradable_balance_ratio: 0.2
```

Strategy-level `custom_stake_amount` should cap only V11.30 shadow entries:

```python
if side == "long" and entry_tag == self.shadow_entry_tag:
    return self._capped_stake(self.shadow_stake_amount, proposed_stake, min_stake, max_stake)
return super().custom_stake_amount(...)
```

Do not enable position adjustment for V11.30 in the first shadow version.

## Proposed Exit Policy

Task 58 selected a 4-to-8 candle observation horizon. For a 15m strategy this
means roughly 60 to 120 minutes.

Recommended first shadow exit behavior:

- keep parent ROI/stoploss conservative, but add explicit custom exit only for
  `v1130_crash_rebound_long`;
- exit after 8 candles / 120 minutes if still open;
- exit early if RSI becomes overbought, for example `rsi > 68`;
- exit early if current profit reaches a modest observation target, for example
  `current_profit >= 0.008`;
- rely on stoploss for downside protection; proposed first stoploss cap:
  `-0.02`.

Draft custom exit states:

```text
v1130_rebound_take_profit
v1130_rebound_rsi_exit
v1130_rebound_time_exit
```

The custom exit must fall back to `super().custom_exit(...)` for all non-V11.30
entry tags.

## Proposed Config

Create only after a guard-exception task authorizes it:

```text
user_data/config_multi_futures_v1130_crash_rebound_shadow.json
```

Config fields:

```json
{
  "bot_name": "V11.30 crash-rebound shadow",
  "strategy": "RegimeAwareV1130CrashReboundShadow",
  "max_open_trades": 2,
  "stake_currency": "USDT",
  "stake_amount": 250,
  "tradable_balance_ratio": 0.2,
  "fiat_display_currency": "USD",
  "dry_run": true,
  "initial_state": "running",
  "dry_run_wallet": 10000,
  "db_url": "sqlite:////freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite",
  "cancel_open_orders_on_exit": true,
  "trading_mode": "futures",
  "margin_mode": "isolated",
  "exchange": {
    "name": "binance",
    "pair_whitelist": [
      "ETH/USDT:USDT",
      "SOL/USDT:USDT",
      "DOGE/USDT:USDT",
      "LINK/USDT:USDT",
      "XRP/USDT:USDT",
      "BCH/USDT:USDT"
    ],
    "pair_blacklist": []
  },
  "pairlists": [
    {
      "method": "StaticPairList",
      "allow_inactive": false
    }
  ],
  "entry_pricing": {
    "price_side": "same",
    "use_order_book": true,
    "order_book_top": 1
  },
  "exit_pricing": {
    "price_side": "same",
    "use_order_book": true,
    "order_book_top": 1
  }
}
```

Do not add `api_server` in the first config. The previous V11.29 ranging-short
shadow showed that including an `api_server` object can force plaintext API
credentials. Monitoring should initially use SQLite/logs unless a later
secret-safe API task is authorized.

## Required Local Tests

Future Task 60 should be TDD.

Create:

```text
tests/test_regime_aware_v1130_crash_rebound_shadow.py
```

Required tests:

1. `test_crash_rebound_long_enabled_when_gate_passes`
   - DataFrame row has:
     - pair allowlisted;
     - return > `0.004`;
     - range >= `0.012`;
     - `35 <= rsi <= 62`;
     - `volume > volume_mean * 0.8`;
     - `alpha_filter_block_short == False`;
     - no `takerSellPressure`.
   - Expected:
     - `enter_long == 1`;
     - `enter_short == 0`;
     - `enter_tag == "v1130_crash_rebound_long"`;
     - `v1130_crash_rebound_gate == "enabled_crash_rebound_long"`.

2. `test_long_crowding_does_not_hard_block_crash_rebound`
   - Same as pass case, but `alpha_filter_block_long == True` and
     `alpha_risk_flags` includes `topTraderAccountLongCrowding`.
   - Expected:
     - V11.30 entry still enabled.

3. `test_taker_sell_pressure_blocks_crash_rebound`
   - Same as pass case, but `alpha_risk_flags` includes `takerSellPressure`.
   - Expected:
     - `enter_long == 0`;
     - gate state `blocked_taker_sell_pressure`.

4. `test_alpha_short_block_blocks_crash_rebound`
   - Same as pass case, but `alpha_filter_block_short == True`.
   - Expected:
     - `enter_long == 0`;
     - gate state `blocked_alpha_short`.

5. `test_missing_columns_fail_closed`
   - Remove `volume_mean` or `alpha_filter_block_short`.
   - Expected:
     - no entry;
     - gate state starts with `blocked_missing_columns:`.

6. `test_non_allowlisted_pair_blocks_entry`
   - Metadata pair is `BTC/USDT:USDT`.
   - Expected:
     - no entry;
     - gate state `blocked_pair_not_allowlisted`.

7. `test_custom_stake_caps_only_v1130_long`
   - `side="long"` and `entry_tag="v1130_crash_rebound_long"` returns capped
     `250`.
   - non-V11.30 tags fall back to parent behavior.

8. `test_custom_exit_only_handles_v1130_tag`
   - V11.30 entry older than 120 minutes exits with `v1130_rebound_time_exit`.
   - non-V11.30 entry falls through to parent behavior.

Required validation commands for Task 60:

```powershell
python -m py_compile strategies/RegimeAwareV1130CrashReboundShadow.py
python -m pytest tests/test_regime_aware_v1130_crash_rebound_shadow.py -q
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

If Python is unavailable on Windows, Task 60 must stop and report the local
runtime blocker instead of skipping tests.

## Required Task Sequence

### Task 60R: V11.30 Crash Rebound Guard Exception

Purpose:

- add exact guard exceptions for the V11.30 strategy/config/test paths.

Allowed future paths:

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
reports/audits/task60r_v1130_crash_rebound_guard_exception.md
tasks/active/TASK-0060R-v1130-crash-rebound-guard-exception.md
```

Exact paths to allow:

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
user_data/config_multi_futures_v1130_crash_rebound_shadow.json
tests/test_regime_aware_v1130_crash_rebound_shadow.py
```

Do not allow:

```text
strategies/**
user_data/**
tests/**
*v1130*
```

### Task 60: V11.30 Crash Rebound Shadow Local Implementation

Purpose:

- implement strategy, dry-run config, and tests locally only.

Allowed future paths:

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
user_data/config_multi_futures_v1130_crash_rebound_shadow.json
tests/test_regime_aware_v1130_crash_rebound_shadow.py
reports/audits/task60_v1130_crash_rebound_shadow_implementation.md
tasks/active/TASK-0060-v1130-crash-rebound-shadow-implementation.md
```

Forbidden:

- server copy;
- bot start;
- bot stop;
- deployment;
- live trading;
- backtest;
- modification of V11.29 main strategy/config.

### Task 61: V11.30 Shadow Deployment Plan

Purpose:

- plan server placement and runtime identity.

Draft runtime identity:

```text
container_name: freqtrade-v1130-crash-rebound-shadow
strategy: RegimeAwareV1130CrashReboundShadow
config: /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json
db: /freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
api_server: absent
mode: dry-run only
```

Resource note:

- the server has limited RAM and swap pressure;
- do not run V11.29 ranging-short shadow and V11.30 crash-rebound shadow
  concurrently unless a preflight task proves enough memory;
- recommended later action is to snapshot/stop the old V11.29 ranging-short
  shadow before starting V11.30, but only with explicit authorization.

### Task 62: V11.30 Server Preflight And Exact File Placement

Purpose:

- only after Task 61 plan approval, check server resources and copy exact files.

Allowed server observations:

```bash
hostname
date
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
free -h
docker stats --no-stream
test -f /home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1130CrashReboundShadow.py
test -f /home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1130_crash_rebound_shadow.json
```

Forbidden:

- no `.env`;
- no `user_data/monitor.env`;
- no `docker inspect` full output;
- no bot start/stop/restart unless a later task authorizes it.

### Task 63: V11.30 Shadow Start Authorization

Purpose:

- start the new dry-run shadow only if explicitly authorized.

Draft command shape:

```bash
docker run -d --name freqtrade-v1130-crash-rebound-shadow \
  --restart unless-stopped \
  -v /home/ubuntu/freqtrade-strategies:/freqtrade/project \
  -w /freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --strategy RegimeAwareV1130CrashReboundShadow \
  --strategy-path /freqtrade/project/strategies
```

Stop condition:

- if server available memory is too low;
- if V11.29 current bot becomes unstable;
- if config validation fails;
- if DB path already exists and no snapshot decision has been made.

### Task 64: V11.30 First Observation Check

Purpose:

- read-only observe the new shadow.

Required observations:

```text
container state
logs for strategy load and heartbeat
SQLite file existence, size, mtime
trades count
orders count
entry tag count for v1130_crash_rebound_long
gate telemetry if available from dataframe/logs
resource pressure
```

Observation windows:

```text
1d: stability and whether orders appear
3d: sample sufficiency checkpoint
7d: minimum evidence window
14d: preferred dry-run evidence window
```

## Stop Conditions

Stop and report instead of proceeding if any of these happen:

- clean worktree is dirty outside the current task's allowed files;
- readiness fails;
- Python tests cannot run;
- `RegimeAwareV66AlphaRisk` import path cannot be validated;
- strategy implementation requires reading secrets;
- server memory is too constrained to start another bot safely;
- any command would require `docker inspect` full output, `.env`, or
  `user_data/monitor.env`;
- a future task tries to combine guard exception, implementation, deployment,
  and start into one step.

## Recommended Next Task

Recommended next task:

```text
Task 60R: V11.30 Crash Rebound Guard Exception
```

Reason:

- current guards block `strategies/**` and `user_data/**` by default;
- exact exceptions must be added before local implementation;
- this preserves the high-risk boundary while allowing the V11.30 shadow to
  move quickly.

