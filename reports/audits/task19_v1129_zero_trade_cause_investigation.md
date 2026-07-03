# Task 19: V11.29 Zero-Trade Cause Investigation

状态：已完成，未进入 Task 20。

## Summary

本任务只读登录服务器 `ubuntu@43.134.72.69`，调查 V11.29 为何在 Task 17 / Task 18 的 snapshot 中仍为 `trades = 0`、`orders = 0`。

结论：V11.29 容器正在运行，日志确认 runmode 为 `dry_run`，确认使用 DB `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite`，服务器当前 SQLite 只读查询仍为 `trades_total = 0`、`orders_total = 0`。未发现真正的 `ERROR` / `Traceback` / `Exception` / `API 500` / `insufficient funds` / `rejected signal` 日志。最强线索是 V11.29 日志反复出现多个交易对 `4h` 数据缺失，以及一次 `Strategy analysis took 225.62s` 超过 timeframe 25% 的警告；这可能导致无法产生有效 entry signal 或错过信号。但本任务没有读取策略逻辑、没有读取配置内容、没有生成 signal audit，因此不能把 0 trades/orders 解释为策略失败。

## Server/container evidence

只读命令范围：

- `hostname`
- `date -Is`
- `docker ps --format ...`
- `docker logs --tail 500 freqtrade-v1129`
- `docker logs --tail 500 freqtrade-v1082`
- `docker exec ... sqlite3 -readonly ...`
- `ls -lh` / `stat` 检查 SQLite 文件大小、mtime、WAL/SHM

服务器基线：

```text
hostname: VM-0-8-ubuntu
date: 2026-07-03T21:26:56+08:00
```

容器状态：

| Container | Docker status | CreatedAt |
|---|---|---|
| `freqtrade-v1129` | `Up 4 hours` | `2026-07-02 17:25:32 +0800 CST` |
| `freqtrade-v1082` | `Up 3 days` | `2026-06-26 10:22:14 +0800 CST` |

V11.29 日志证据：

```text
Using config: /freqtrade/project/user_data/config_multi_futures_v1129.json
Runmode set to dry_run.
Dry run is enabled
Using DB: "sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite"
Instance is running with dry_run enabled
Using Exchange "Binance"
Using resolved strategy RegimeAwareV1129ResidualDragMicroSizer
Strategy using timeframe: 15m
Strategy using startup_candle_count: 200
Whitelist with 12 pairs: [...]
```

说明：本任务只引用日志中的非 secret 行；未读取 `.env`、`user_data/monitor.env`，未运行 `docker inspect`。

## V11.29 DB evidence

服务器当前只读 SQLite 检查：

| Item | Observed value |
|---|---|
| DB path | `/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite` |
| main DB size | `92K` / `94208` bytes |
| main DB mtime | `2026-07-02 09:25:44.080833317 +0000` |
| WAL | `/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite-wal`, `49K`, mtime `2026-07-03 09:03` |
| SHM | `/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite-shm`, `32K`, mtime `2026-07-03 09:03` |
| `trades_total` | `0` |
| `trades_open` | `0` |
| `trades_closed` | `0` |
| `orders_total` | `0` |
| `orders_open` | `0` |
| `orders_closed` | `0` |
| `min_open_date` | empty |
| `max_open_date` | empty |
| `max_close_date` | empty |
| `pairlocks_total` | `0` |
| `active_pairlocks` | `0` |

WAL/SHM 文件存在，但 `sqlite3 -readonly` 对当前 DB 视图的查询仍显示 `trades/orders` 为 0，因此未 checkpoint 的 WAL 没有改变本任务观察到的交易/订单计数。

## V10.8.2 DB evidence

服务器当前只读 SQLite 检查：

| Item | Observed value |
|---|---|
| DB path | `/freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite` |
| main DB size | `92K` / `94208` bytes |
| main DB mtime | `2026-06-26 02:22:24.247703619 +0000` |
| WAL | `/freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite-wal`, `2.0M`, mtime `2026-07-03 00:07` |
| SHM | `/freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite-shm`, `32K`, mtime `2026-07-03 00:07` |
| `trades_total` | `6` |
| `trades_open` | `0` |
| `trades_closed` | `6` |
| `orders_total` | `12` |
| `orders_open` | `0` |
| `orders_closed` | `12` |
| `min_open_date` | `2026-06-26 06:15:33.352116` |
| `max_open_date` | `2026-07-01 02:16:09.203505` |
| `max_close_date` | `2026-07-01 10:27:37.736000` |
| `pairlocks_total` | `8` |
| `active_pairlocks` | `8` |

V10.8.2 只作为 benchmark data availability；本任务不做 same-window performance comparison，不生成替换结论。

## Log findings

V11.29 `docker logs --tail 500` 摘要：

| Signal | Count / finding |
|---|---:|
| `Bot heartbeat` | `320` |
| `state='RUNNING'` | `319` |
| `No data found` | `68` |
| `Strategy analysis took` | `1` |
| `Whitelist with` | `6` |
| true `ERROR` / `Traceback` / `Exception` / `API 500` / `insufficient funds` / `rejected signal` | no matches |
| process exit / restart lines | observed around `2026-07-03 09:02:51` / restart around `09:03:18` |

Representative V11.29 warnings:

```text
No data found for (BTC/USDT:USDT, 4h, ).
No data found for (ETH/USDT:USDT, 4h, ).
No data found for (SOL/USDT:USDT, 4h, ).
No data found for (BNB/USDT:USDT, 4h, ).
No data found for (XRP/USDT:USDT, 4h, ).
No data found for (DOGE/USDT:USDT, 4h, ).
Strategy analysis took 225.62s, more than 25% of the timeframe (225.00s). This can lead to delayed orders and missed signals.
```

V10.8.2 `docker logs --tail 500` 摘要：

| Signal | Count / finding |
|---|---:|
| `Bot heartbeat` | `305` |
| `state='RUNNING'` | `305` |
| `No data found` | `166` |
| `Strategy analysis took` | `2` |
| `Whitelist with` | `7` |
| true `ERROR` / `Traceback` / `Exception` / `API 500` / `insufficient funds` / `rejected signal` | no matches |

V10.8.2 近期日志同样有 `No data found` 和 strategy analysis slow warning，因此这些现象不能单独证明 V11.29 策略失败；它们只是当前最值得后续审查的数据/信号链线索。

## Most likely zero-trade causes

基于当前只读证据，最可能的原因按强度排序：

1. `observed`: V11.29 当前运行中，但其指定 DB 当前没有 trade/order rows。日志与 DB 路径一致，因此“查询了完全错误的本地 snapshot”不是主要解释。
2. `observed`: V11.29 日志反复出现多个 pair 的 `4h` 数据缺失。若策略依赖 `4h` informative data，这可能导致 entry 条件无法形成或样本不足。
3. `observed`: V11.29 出现 strategy analysis slow warning，日志明确提示可能导致 delayed orders / missed signals。这是可能的执行链风险。
4. `unknown`: V11.29 可能没有产生 entry signal；当前日志没有 signal audit，不能确认是无信号、信号被过滤、还是信号产生后没有进入订单。
5. `unknown`: pairlist / protection / filter 可能影响信号链。当前 V11.29 DB 中 `pairlocks_total = 0` 且 `active_pairlocks = 0`，没有 active pairlock 证据，但 StoplossGuard 已加载，其他过滤器或策略内部条件未被本任务证明。
6. `unknown`: 启动窗口可能较短。`freqtrade-v1129` 当前 `Status` 是 `Up 4 hours`，如果策略需要更多 warmup / market regime 条件，当前窗口可能不足；但这不能从当前日志单独证明。

## Causes ruled out

当前证据可以排除或降低优先级的原因：

- bot 未运行：`docker ps` 显示 `freqtrade-v1129 Up 4 hours`，日志有持续 heartbeat。
- 非 dry-run：日志显示 `Runmode set to dry_run` 和 `Dry run is enabled`。
- 明显 DB 路径错配：日志显示使用 `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite`，只读查询同一路径。
- active pairlock 直接阻断：V11.29 当前 DB `pairlocks_total = 0`、`active_pairlocks = 0`。
- 明确 exchange/API crash：严格扫描最近 500 行未发现真正的 `ERROR`、`Traceback`、`Exception`、`API 500`。
- 资金不足：最近 500 行未发现 `insufficient funds`。
- 信号被明确拒绝：最近 500 行未发现 `rejected signal`。

## Unknowns

仍无法确认：

- V11.29 是否产生过 entry signal。
- V11.29 的 entry signal 是否被策略内部条件、pairlist、protection、supervisor、资金/仓位规则或订单参数过滤。
- `4h` 数据缺失是否直接导致 V11.29 无信号。
- strategy analysis slow warning 是否实际导致 missed signals。
- V11.29 当前 pairlist 的完整 12 个 pair 是否都有足够 `15m` 与 `4h` 数据。
- V10.8.2 的历史 6 笔 closed trades 与当前 V11.29 观察窗口是否可比；当前仍不能证明 same-window comparison。
- dashboard / monitor history / signal audit 中是否记录了被阻断或未成交信号。

## Blocking gaps

- 缺少 V11.29 signal audit：无法区分“无信号”和“信号被过滤/阻断”。
- 缺少 V11.29 pair/timeframe data availability audit：无法证明 `4h` 数据缺失是否覆盖所有 pair 或只是临时刷新延迟。
- 缺少 strategy runtime decision trace：无法证明策略条件是否过严。
- 缺少 monitor/dashboard runtime event history：无法证明 API 异常、stopped alert、jq parse error、blocked signal 链路。
- 缺少 V11.29 与 V10.8.2 same-window 样本：仍不能做执行质量比较或替换判断。

## Recommended Task 20

推荐 Task 20：`V11.29 Signal and Data Availability Audit`。

建议范围：

- 只读检查 V11.29 pairlist 中每个 pair 的 `15m` 与 `4h` 数据可用性、最后 K 线时间、缺口数量。
- 只读生成或定位 signal audit，不下单、不启动/停止 bot、不回测。
- 区分 no signal、data unavailable、protection/filter blocked、supervisor blocked、order rejected、runtime/API error。
- 若需要新增采集，只新增 harness/report 层的只读采集计划，不修改策略或 bot 配置。

## Boundary confirmation

- 未运行 `docker inspect`
- 未读取 `.env`
- 未读取 `user_data/monitor.env`
- 未打印、复制、读取 API key / secret / password / token
- 未执行 `docker restart` / `docker stop` / `docker start`
- 未执行 `freqtrade trade`
- 未运行回测
- 未写 SQLite
- 未修改任何服务器文件
- 未修改 bot 配置
- 未修改策略
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 20
