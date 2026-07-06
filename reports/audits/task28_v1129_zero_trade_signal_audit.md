# Task 28: V11.29 Zero-Trade Signal Audit

## Summary

本任务只读审计 V11.29 在进入 `RUNNING` 后仍然 `trades=0/orders=0` 的原因链。结论是：

- V11.29 当前 API 可读，bot state 为 `running`。
- V11.29 当前没有 open trades、closed trades、orders、active locks。
- V11.29 当前日志中没有 `ERROR`、`Traceback`、`Strategy analysis took`、`No data found`、`rejected signal`、`insufficient funds` 或 order 相关事件。
- V11.29 当前白名单为 12 个 futures pairs，StaticPairList 正常返回。
- 现有运行日志没有 signal-level telemetry，因此无法证明是“没有 entry signal”、还是“上游条件/过滤层把信号清掉”、还是“有信号但未进入订单路径”。

本任务没有修改策略、bot 配置、dashboard、deploy、secret 或服务器运行状态，没有启动/停止/restart bot，没有运行回测。

## Runtime Truth

检查时间：

```text
2026-07-06T14:34:30+08:00
```

容器状态：

```text
freqtrade-v1129 Up 2 days 127.0.0.1:8122->8122/tcp
freqtrade-v1082 Up 5 days 127.0.0.1:8091->8091/tcp
```

Task 27 runtime truth monitor 输出：

```json
{
  "V11.29 Current Research Candidate": {
    "ok": true,
    "api_probe_ok": true,
    "runtime_status": "bot_running",
    "execution_status": "bot_running_no_trades_observed",
    "state": "running",
    "runmode": "dry_run",
    "open": 0,
    "total": 0,
    "closed": 0
  },
  "V10.8.2 Historical Profit Benchmark": {
    "ok": true,
    "api_probe_ok": true,
    "runtime_status": "bot_running",
    "execution_status": "bot_running_closed_or_historical_trades_observed",
    "state": "running",
    "runmode": "dry_run",
    "open": 0,
    "total": 6,
    "closed": 6
  }
}
```

## API Evidence

V11.29 API:

| Endpoint | Result |
| --- | --- |
| `ping` | `200` |
| `show_config` | `200` |
| `count` | `200` |
| `profit` | `200` |
| `status` | `200` |
| `locks` | `200` |
| `whitelist` | `200` |

V11.29 `show_config` summary:

```json
{
  "state": "running",
  "runmode": "dry_run",
  "strategy": "RegimeAwareV1129ResidualDragMicroSizer",
  "timeframe": "15m",
  "max_open_trades": 4.0,
  "stake_amount": "2500",
  "dry_run": true,
  "trading_mode": "futures",
  "margin_mode": "isolated"
}
```

V11.29 trade/order API summary:

```json
{
  "count": {"current": 0, "max": 4, "total_stake": 0.0},
  "profit": {"trade_count": 0, "closed_trade_count": 0, "profit_all_coin": 0.0, "latest_trade_date": ""},
  "status_len": 0,
  "locks": {"lock_count": 0, "locks": []}
}
```

V11.29 whitelist:

```text
BTC/USDT:USDT
ETH/USDT:USDT
SOL/USDT:USDT
BNB/USDT:USDT
XRP/USDT:USDT
DOGE/USDT:USDT
ADA/USDT:USDT
LINK/USDT:USDT
AVAX/USDT:USDT
LTC/USDT:USDT
TRX/USDT:USDT
BCH/USDT:USDT
```

## SQLite Evidence

Read-only SQLite counts:

| Bot | trades | orders | pairlocks | open | closed |
| --- | ---: | ---: | ---: | ---: | ---: |
| V11.29 | 0 | 0 | 0 | 0 | 0 |
| V10.8.2 | 6 | 12 | 8 | 0 | 6 |

V11.29 DB file:

```text
path=/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129.dryrun.sqlite
size=94208
mtime=2026-07-02 17:25:44 CST
```

V10.8.2 DB file:

```text
path=/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1082.dryrun.sqlite
size=94208
mtime=2026-06-26 10:22:24 CST
```

## Log Evidence Since V11.29 RUNNING

Window:

```text
since 2026-07-06T03:53:30Z
```

V11.29 counters:

| Pattern | Count |
| --- | ---: |
| `state='RUNNING'` | 159 |
| `state='STOPPED'` | 0 |
| `trader is not running` | 0 |
| `Whitelist with` | 3 |
| `Using Protections` | 1 |
| `Wallets synced` | 54 |
| `No data found` | 0 |
| `Strategy analysis took` | 0 |
| `ERROR` | 0 |
| `Traceback` | 0 |
| `entry` | 0 |
| `signal` | 0 |
| `rejected` | 0 |
| `lock` | 0 |
| `order` | 0 |

Interpretation:

- Bot is running and looping.
- No observed runtime crash.
- No observed active protection lock.
- No observed explicit order rejection.
- No signal-level logs are emitted by the current runtime configuration, so signal presence cannot be inferred from absence of log text.

## Data Availability

Container strategy files:

```text
/freqtrade/project/strategies/RegimeAwareV1129ResidualDragMicroSizer.py
/freqtrade/project/strategies/RegimeAwareV1127DualTrapMicroSizer.py
/freqtrade/project/strategies/regime_aware_base.py
```

Local futures data files exist for V11.29 whitelist pairs:

- `15m-futures.feather`
- `4h-futures.feather`
- `1h-futures.feather`
- funding-rate / mark files for many pairs

Observed local futures file ranges:

| Timeframe | Pair coverage | Latest local candle |
| --- | --- | --- |
| `15m` | 12/12 pairs | `2026-07-03 08:45:00+00:00` |
| `4h` | 12/12 pairs | `2026-07-03 04:00:00+00:00` |

Important boundary:

- These local feather files are stale relative to `2026-07-06`.
- However the current V11.29 runtime window did not emit `No data found`, so this is a risk signal, not a proven direct cause of zero trades.
- Live Freqtrade DataProvider may be using exchange data instead of local fallback for the active runtime.

## Strategy Signal Chain

V11.29 class:

```text
RegimeAwareV1129ResidualDragMicroSizer
```

Observed inheritance path:

```text
RegimeAwareV1129ResidualDragMicroSizer
<- RegimeAwareV1127DualTrapMicroSizer
<- RegimeAwareV1124ReboundChaseSizer
<- RegimeAwareV1122AdaCapitulationHalfSizer
<- RegimeAwareV1118VolatilityShockSmallShortPruner
<- earlier V10/V11 short-core layers
```

V11.29 itself mostly retags or micro-sizes selected short entries:

- `v1129_ada_capitulation_micro_short`
- `v1129_eth_core_watch_micro_short`
- `v1129_ltc_rebound_micro_short`
- residual probe tags for SOL/LTC/BTC/XRP/DOGE

V11.29 does not appear to introduce a broad direct block in its own class. But upstream layers include:

- pair tier gates;
- volatility shock pruning;
- capitulation/rebound/chop-drag retagging;
- custom stake sizing that can return `0.0` if below `min_stake`;
- base strategy conditions requiring informative `4h` regime/DI/ADX/EMA/RSI/volume context.

Current evidence is insufficient to decide which layer produced no orders.

## Ruled Out

Current evidence lowers the likelihood of these causes:

- container down: V11.29 container is up.
- API inaccessible: all checked V11.29 API endpoints return `200`.
- bot stopped after start: logs show `state='RUNNING'`; runtime monitor says `bot_running`.
- active pairlock: API `locks` returns `lock_count=0`; SQLite `pairlocks=0`.
- open trade slot full: API `count.current=0`, `max=4`.
- obvious exchange/API crash: no `ERROR` / `Traceback` in current V11.29 window.
- explicit order rejection: no `order`, `rejected`, `insufficient funds` evidence in current V11.29 logs.

## Not Proven

Current evidence cannot prove:

- V11.29 had zero entry signals.
- V11.29 generated entry signals that were then cleared by filters.
- V11.29 generated entries but custom stake returned `0.0`.
- local stale feather files caused zero entries.
- current market offered no valid setup.
- V11.29 strategy is bad or good.
- V11.29 can or cannot replace V10.8.2.

## Most Likely Current Explanation

The strongest evidence-backed statement is:

```text
V11.29 is running and observable, but the current runtime provides no signal-level telemetry. It has not produced trades/orders yet in the observed running window. The absence of trades is not currently attributable to API failure, active locks, open-trade capacity, or explicit order rejection.
```

The most likely investigation gap is not strategy logic itself yet; it is missing signal-decision instrumentation.

## Recommended Task 29

Recommended next task:

```text
Task 29: V11.29 Signal Decision Telemetry Plan
```

Scope:

- Add a read-only signal decision telemetry plan before changing strategy behavior.
- Define exactly what to record per pair/candle:
  - final `enter_long` / `enter_short`
  - final `enter_tag`
  - base short-core signal count
  - blocked/retagged gate columns such as `v1118_*`, `v1122_*`, `v1127_*`, `v1129_*`
  - custom stake result category, without printing balances or secrets
  - data freshness for 15m and 4h inputs
- Prefer a report or monitor artifact, not Telegram spam.
- Do not place orders, do not run backtests, do not modify bot config in the planning task.

Follow-up after Task 29:

```text
Task 30: V11.29 Read-Only Signal Telemetry Implementation
```

Only after telemetry proves the cause should we consider strategy changes.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**` bot configs;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.
