# Task 21: V11.29 4h Data Availability Root-Cause Plan

状态：已完成。只读检查 V11.29 `4h` 数据可用性线索，并制定安全补数据 / root-cause 计划；未下载数据、未修改配置、未重启 bot。

## Summary

V11.29 日志持续报告 12 个 whitelist pair 的 `4h` 数据缺失：

```text
No data found for (..., 4h, ).
```

只读检查发现：服务器磁盘上确实存在这些 pair 的 futures `4h` feather 文件，并且每个目标 pair 的 `4h` 文件都有约 `5486` 行。因此，“服务器完全没有 4h 文件”不是当前最佳解释。

更可能的问题是以下之一：

- historical data 文件存在但已经过旧；
- live/dry-run 运行时没有使用这些本地 feather 文件；
- runtime candle cache 没有拿到 `4h` informative 数据；
- strategy informative pair / candle type / market type 映射与 Freqtrade 实际数据源不一致；
- pairlist 与 informative pair 注册方式导致 4h 数据未进入 DataProvider；
- strategy analysis 过慢导致数据/信号链路延迟，但这需要 Task 22 单独审计。

本任务不直接补数据，因为当前证据不足以证明“下载更多 4h 文件”就是正确修复。

## Execution boundary

本任务只执行只读操作：

- `docker ps --format ...`
- `docker logs --tail ...`
- `docker exec -i freqtrade-v1129 python -` 读取 feather metadata

本任务没有：

- 执行 `download-data`
- 执行 `docker restart`
- 执行 `docker stop`
- 执行 `docker start`
- 执行 `freqtrade trade`
- 运行回测
- 读取 `.env`
- 读取 `user_data/monitor.env`
- 读取 API key / secret / password / token
- 修改服务器文件
- 修改策略
- 修改 bot 配置
- 修改原始脏工作区

## Server evidence

服务器：

```text
host: VM-0-8-ubuntu
date: 2026-07-03T22:45:52+08:00
```

运行容器：

```text
freqtrade-v1129|Up 6 hours|127.0.0.1:8122->8122/tcp
freqtrade-v1082|Up 3 days|127.0.0.1:8091->8091/tcp
```

Legacy containers `freqtrade-v1127` and `freqtrade-v1116` had already been stopped in the authorized Task 20S-STOP.

## Runtime log evidence

`docker logs --tail 800 freqtrade-v1129` showed repeated `4h` no-data warnings for all 12 observed whitelist symbols:

| Pair | Count in tail 800 |
|---|---:|
| `LTC/USDT:USDT` | 15 |
| `BCH/USDT:USDT` | 15 |
| `AVAX/USDT:USDT` | 15 |
| `XRP/USDT:USDT` | 14 |
| `ETH/USDT:USDT` | 14 |
| `DOGE/USDT:USDT` | 14 |
| `BTC/USDT:USDT` | 14 |
| `ADA/USDT:USDT` | 14 |
| `TRX/USDT:USDT` | 13 |
| `SOL/USDT:USDT` | 13 |
| `LINK/USDT:USDT` | 13 |
| `BNB/USDT:USDT` | 13 |

The same log window still includes the earlier performance warning:

```text
Strategy analysis took 225.62s, more than 25% of the timeframe (225.00s). This can lead to delayed orders and missed signals.
```

## Disk data evidence

Read-only feather metadata from `/freqtrade/project/user_data/data/futures`:

| Pair | 15m rows | 15m last candle UTC | 4h rows | 4h last candle UTC |
|---|---:|---|---:|---|
| `BTC/USDT:USDT` | 8100 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `ETH/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `SOL/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `BNB/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `XRP/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `DOGE/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `ADA/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `LINK/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `AVAX/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `TRX/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `LTC/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |
| `BCH/USDT:USDT` | 87780 | `2026-07-03 08:45:00+00:00` | 5486 | `2026-07-03 04:00:00+00:00` |

Observed file naming pattern:

```text
/freqtrade/project/user_data/data/futures/<PAIR>_USDT_USDT-4h-futures.feather
```

## Interpretation

The disk files are present and structurally readable. Therefore:

- `observed`: the files exist for all 12 pairs.
- `observed`: each `4h` file contains thousands of rows.
- `observed`: the latest `4h` row is `2026-07-03 04:00:00+00:00`.
- `observed`: the V11.29 runtime still logs `No data found for (..., 4h, )`.
- `unknown`: whether live/dry-run mode is reading these local files at all.
- `unknown`: whether the strategy requests `4h` data with a candle type or naming pattern that does not match the stored futures files.
- `unknown`: whether the runtime candle cache is empty because exchange fetch failed, pairlist/informative registration is wrong, or the current 4h candle is considered too stale.

The data files appear stale relative to the task check time, but staleness alone does not fully explain repeated `No data found` if Freqtrade live mode should fetch candles from the exchange.

## Root-cause hypotheses

Ranked hypotheses:

1. `runtime informative cache missing`: V11.29 strategy asks DataProvider for `4h` informative data, but runtime did not load/populate that pair/timeframe cache.
2. `candle_type mismatch`: files are `*-4h-futures.feather`, while the log prints an empty candle type in `(pair, 4h, )`. The runtime may be looking for default candle type rather than futures candle type.
3. `stale historical data`: local `4h` files stop at `2026-07-03 04:00:00+00:00`, while the check happened around `2026-07-03 14:45:52+00:00` equivalent server UTC window; recent 4h candles may be unavailable from local files.
4. `strategy informative registration issue`: the strategy may not return the expected informative pairs, or may call `get_pair_dataframe` manually for pairs/timeframes not subscribed by the bot.
5. `performance interaction`: slow analysis may delay cache refresh or make signal windows stale. This needs Task 22.

## Safe remediation plan

Do not immediately download or restart. Recommended sequence:

1. Read-only confirm V11.29 non-secret config fields:
   - `datadir`
   - `dataformat_ohlcv`
   - `trading_mode`
   - `candle_type_def`
   - `timeframe`
   - `pair_whitelist`
   This must avoid printing exchange keys, API server credentials, Telegram tokens, or any secrets.

2. Read-only inspect strategy informative pair declarations:
   - identify whether V11.29 requests `4h` via `informative_pairs()`;
   - identify whether it uses candle type explicitly;
   - identify whether it manually calls `get_pair_dataframe(pair, "4h")`.
   This should be a separate task because strategy files are normally guarded.

3. Read-only inspect runtime logs around startup:
   - data directory line;
   - data format line;
   - exchange / futures market mode line;
   - informative timeframe subscription clues.

4. Only if root cause is confirmed as stale/missing historical futures data, prepare a safe data refresh command draft:

```bash
docker run --rm \
  -v /home/ubuntu/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "BTC/USDT:USDT" "ETH/USDT:USDT" "SOL/USDT:USDT" "BNB/USDT:USDT" "XRP/USDT:USDT" "DOGE/USDT:USDT" "ADA/USDT:USDT" "LINK/USDT:USDT" "AVAX/USDT:USDT" "TRX/USDT:USDT" "LTC/USDT:USDT" "BCH/USDT:USDT" \
  --timeframes 15m 4h \
  --trading-mode futures \
  --config /freqtrade/project/user_data/config_multi_futures_v1129.json \
  -d /freqtrade/project/user_data/data
```

This is a draft only. Do not execute it until a future task explicitly authorizes data refresh and reviews whether the config can be used without exposing secrets.

5. After any future data refresh or config/strategy fix, observe V11.29 without replacement claims:
   - logs should stop reporting repeated `No data found for (..., 4h, )`;
   - `trades/orders` may still remain 0, which would then point to signal/filter/performance rather than data availability.

## What this task cannot conclude

This task cannot conclude:

- V11.29 strategy failed.
- V11.29 can or cannot replace V10.8.2.
- Downloading more data will fix zero trades.
- No signal exists.
- Performance is the sole cause.

## Recommended next task

Recommended `Task 21A: V11.29 Non-Secret Config and Informative Mapping Audit`.

Goal:

- inspect only non-secret config fields and strategy informative data mapping;
- do not modify strategy or config;
- do not print secrets;
- determine whether the `4h` issue is stale data, candle type mismatch, or informative registration/runtime cache mismatch.

If Task 21A confirms stale data as root cause, then run a separate `Task 21B: Safe V11.29 Futures Data Refresh Plan`.

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task21_v1129_4h_data_availability_root_cause_plan.md
tasks/active/TASK-0021-v1129-4h-data-availability-root-cause-plan.md
```
