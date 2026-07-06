# Task 29: V11.29 Signal Decision Telemetry Plan

## Summary

Task 28 confirmed that V11.29 is currently `running`, API-readable, and has `trades=0/orders=0`, but the runtime does not emit signal-level evidence. This task defines a narrow, read-only telemetry plan to prove where the zero-trade condition comes from before any strategy or bot configuration changes.

Direct answer to the current data freshness question:

- The local futures feather files observed in Task 28 are not updated to the current date. For the 12 V11.29 whitelist pairs, local `15m` data ended at `2026-07-03 08:45:00+00:00`, and local `4h` data ended at `2026-07-03 04:00:00+00:00`.
- Therefore the local downloaded/fallback data set is not a real-time updated data source in the current evidence.
- This does not yet prove that V11.29's live runtime had no usable exchange candles, because Freqtrade may use live exchange/DataProvider data while running.
- Task 28 did not observe `No data found` in the current V11.29 runtime logs, so stale local feather data is a serious risk signal, not yet a proven root cause.

This task does not modify strategies, bot configs, dashboard, deploy scripts, SQLite snapshots, secrets, or the running server.

## Evidence From Task 28

Observed runtime state:

| Item | V11.29 evidence |
| --- | --- |
| API health | `ping`, `show_config`, `count`, `profit`, `status`, `locks`, `whitelist` all returned `200` |
| Bot state | `running` |
| Run mode | `dry_run` |
| Trades | `0` |
| Orders | `0` |
| Active locks | `0` |
| Whitelist | 12 futures pairs |
| Current-window errors | no observed `ERROR`, `Traceback`, `No data found`, `rejected`, or `order` evidence |
| Local `15m` futures data latest candle | `2026-07-03 08:45:00+00:00` |
| Local `4h` futures data latest candle | `2026-07-03 04:00:00+00:00` |

Current unknowns:

- Whether V11.29 receives fresh live candles from exchange/DataProvider.
- Whether any pair produces raw entry conditions.
- Whether upstream gates clear or retag entries.
- Whether `custom_stake_amount` returns a below-minimum or zero stake.
- Whether protections, pairlist, market conditions, or data freshness suppress entries.
- Whether zero trades reflect a valid lack of setups or missing runtime inputs.

## Telemetry Goal

Add a future read-only telemetry layer that can answer these questions per pair and candle:

1. Did V11.29 have fresh market data for the candle it analyzed?
2. Did raw entry conditions trigger?
3. Did inherited V11.x gates allow, retag, or clear the entry?
4. Did final `enter_long` / `enter_short` remain set?
5. Did `custom_stake_amount` allow a tradable stake category?
6. If no order was placed, which observable reason best explains it?

The telemetry must record evidence without placing orders, changing config, running backtests, or printing secrets.

## Proposed Telemetry Artifact

Recommended future Task 30 output artifacts:

```text
scripts/build_v1129_signal_decision_telemetry.js
reports/v1129_execution_validation/signal_decision_telemetry_sample.json
reports/v1129_execution_validation/signal_decision_telemetry_sample.md
reports/audits/task30_v1129_signal_decision_telemetry.md
tasks/active/TASK-0030-v1129-signal-decision-telemetry.md
```

Guard note:

- These paths may require a precise guard exception before implementation.
- Do not allow broad rules such as `reports/v1129_execution_validation/**`, `reports/*v1129*`, or `scripts/build_v1129_*`.

## Telemetry Schema

Recommended JSON shape:

```json
{
  "metadata": {
    "strategy": "RegimeAwareV1129ResidualDragMicroSizer",
    "generated_at": "observed timestamp",
    "mode": "read_only_signal_telemetry",
    "source": "server_runtime_or_snapshot",
    "can_place_orders": false
  },
  "data_freshness": [
    {
      "pair": "BTC/USDT:USDT",
      "timeframe": "15m",
      "latest_candle": "observed_or_unknown",
      "source": "dataprovider_live | local_fallback | unknown",
      "status": "fresh | stale | missing | unknown",
      "reason": "observed explanation"
    }
  ],
  "pair_decisions": [
    {
      "pair": "BTC/USDT:USDT",
      "candle_time": "observed_or_unknown",
      "enter_long": "observed | missing | unknown",
      "enter_short": "observed | missing | unknown",
      "enter_tag": "observed | missing | unknown",
      "raw_signal_count": "observed | derived | unknown",
      "gate_results": {
        "v1118": "allowed | blocked | retagged | unknown",
        "v1122": "allowed | blocked | retagged | unknown",
        "v1124": "allowed | blocked | retagged | unknown",
        "v1127": "allowed | blocked | retagged | unknown",
        "v1129": "allowed | blocked | retagged | unknown"
      },
      "stake_decision": {
        "category": "normal | micro | probe | zero_below_min_stake | unknown",
        "secret_free": true
      },
      "not_entered_reason": "no_signal | gate_blocked | stale_data | stake_zero | lock | capacity_full | unknown"
    }
  ],
  "runtime_context": {
    "api_state": "running | stopped | unknown",
    "locks": "observed | unknown",
    "open_trade_slots": "observed | unknown",
    "orders_observed": "observed | unknown"
  },
  "verdict": {
    "can_explain_zero_trades": false,
    "reason": "plan only; implementation required",
    "next_required_task": "Task 30: V11.29 Read-Only Signal Telemetry Implementation"
  }
}
```

## Required Fields

Per pair/candle:

- `observed_at`
- `pair`
- `base_timeframe`
- `informative_timeframes`
- latest `15m` candle timestamp
- latest `4h` candle timestamp
- `data_source`: `dataprovider_live`, `local_fallback`, or `unknown`
- `data_freshness_status`: `fresh`, `stale`, `missing`, or `unknown`
- final `enter_long`
- final `enter_short`
- final `enter_tag`
- raw signal flags and counts
- inherited gate flags from V11.18 / V11.22 / V11.24 / V11.27 / V11.29 layers where observable
- stake category, without balance or credential values
- `not_entered_reason`

Runtime context:

- API `state`
- `runmode`
- active locks count
- current open trades
- max open trades
- SQLite trades/orders count, read-only
- latest log window metadata, without secrets

## Evidence Semantics

The telemetry must explicitly distinguish:

| State | Meaning |
| --- | --- |
| `observed` | Directly read from runtime, API, SQLite, log, or generated signal dataframe |
| `derived` | Calculated from observed fields |
| `missing` | Expected field/source is absent |
| `unknown` | Source exists but cannot prove the value safely |
| `insufficient` | Available evidence is not enough for a conclusion |

Rules:

- Do not write missing values as `0`.
- Do not translate "no observed error" into "no error".
- Do not translate "no observed signal log" into "no signal".
- Do not translate "0 trades/orders" into "strategy failed".
- Do not conclude V11.29 can or cannot replace V10.8.2.

## Data Freshness Check Design

Task 30 should prove data freshness using the safest available source:

1. Prefer runtime/DataProvider-accessible candle timestamps if a safe read-only route exists.
2. If only local files are checked, label the source as `local_fallback`, not `live`.
3. Record latest `15m` and `4h` timestamps per whitelist pair.
4. Mark stale local data as `stale`, but do not call it the root cause until telemetry connects stale data to missing signals.
5. If DataProvider freshness cannot be inspected without strategy/config changes, mark it `unknown` and recommend a narrower follow-up.

## Implementation Boundaries For Task 30

Allowed direction:

- Build a read-only telemetry generator.
- Read non-secret runtime/API/SQLite/log evidence.
- Produce JSON/Markdown evidence files.
- Avoid Telegram alert spam.

Forbidden direction:

- No strategy behavior changes.
- No bot config changes.
- No order placement.
- No `freqtrade trade`.
- No backtests.
- No server restart/stop/start.
- No secret reads or prints.
- No broad guard allowlists.

## Validation Plan

Task 30 should run:

```powershell
node --check scripts/build_v1129_signal_decision_telemetry.js
node scripts/build_v1129_signal_decision_telemetry.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

If the implementation uses Python instead of Node.js, replace the syntax check with the exact Python runtime available in this workspace and document it.

## What This Plan Cannot Conclude

This plan does not prove:

- V11.29 failed.
- V11.29 has no entry signals.
- V11.29 has fresh or stale live exchange data.
- stale local feather files caused zero trades.
- V11.29 can replace V10.8.2.
- V11.29 cannot replace V10.8.2.

## Recommended Task 30

Recommended next task:

```text
Task 30: V11.29 Read-Only Signal Telemetry Implementation
```

Goal:

- Implement the narrow telemetry generator described here.
- Preserve all high-risk boundaries.
- Use telemetry to decide whether the next step is data refresh, signal gate audit, stake sizing audit, or runtime configuration review.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.
