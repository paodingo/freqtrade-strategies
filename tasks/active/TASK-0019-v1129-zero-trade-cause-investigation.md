# TASK-0019: V11.29 Zero-Trade Cause Investigation

状态：已完成，未进入 Task 20。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只读调查 V11.29 为什么没有 trades/orders，定位可能原因：bot 未真正交易、无信号、pairlist 无机会、保护/过滤器阻断、配置指向错误 DB、API/交易所异常、启动时间太短、日志报错、策略条件过严等。

## 只读服务器证据

- server：`ubuntu@43.134.72.69`
- hostname：`VM-0-8-ubuntu`
- server date：`2026-07-03T21:26:56+08:00`
- `freqtrade-v1129`：`Up 4 hours`
- `freqtrade-v1082`：`Up 3 days`

## 主要发现

- V11.29 日志确认 `dry_run`，确认使用 DB `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite`。
- V11.29 日志确认加载策略 `RegimeAwareV1129ResidualDragMicroSizer`。
- V11.29 服务器当前 DB 只读查询仍为 `trades_total = 0`、`orders_total = 0`。
- V11.29 当前 `pairlocks_total = 0`、`active_pairlocks = 0`。
- V11.29 最近 500 行日志中多次出现 `No data found for (..., 4h, )`。
- V11.29 最近 500 行日志中出现一次 `Strategy analysis took 225.62s`，日志提示可能 delayed orders / missed signals。
- 最近 500 行未发现真正的 `ERROR`、`Traceback`、`Exception`、`API 500`、`insufficient funds`、`rejected signal`。
- V10.8.2 DB 中存在 `closed_trades = 6`、`orders = 12`，但本任务不做 same-window comparison。

## 判断

当前最可能的方向是 V11.29 的数据/信号链不足：`4h` 数据缺失、策略分析耗时、无信号或信号被过滤仍需后续 signal/data availability audit 证明。

本任务不把 `0 trades/orders` 解释为策略失败，也不判断 V11.29 是否可以或不可以替换 V10.8.2。

## 未执行事项

- 未运行 `docker inspect`
- 未读取 `.env`
- 未读取 `user_data/monitor.env`
- 未读取 secret
- 未启动、停止或重启 bot
- 未运行 `freqtrade trade`
- 未运行回测
- 未写 SQLite
- 未修改服务器文件
- 未修改策略
- 未修改 bot 配置
- 未修改原始脏工作区
- 未进入 Task 20

## 输出

- `reports/audits/task19_v1129_zero_trade_cause_investigation.md`

## 下一步

推荐 Task 20：`V11.29 Signal and Data Availability Audit`。
