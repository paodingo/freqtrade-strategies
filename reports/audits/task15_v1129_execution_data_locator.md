# Task 15: V11.29 Execution Data Locator

状态：已完成，未进入 Task 16。

结论：本任务只读定位了原始工作区 `D:\code\freqtrade-strategies` 中可能支持 V11.29 真实执行验证的数据源。当前没有在本地原始工作区定位到 V11.29 dry-run trade SQLite 文件；只发现候选监控库、live window execution check 报告、dashboard/API 脚本和大量回测/研究产物。基于本任务的路径级证据，不能生成真实执行验证报告，只能继续使用 insufficient 报告，直到后续任务获得授权读取候选内容并确认真实 trade/order 数据存在。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 14 commit：`7be3ff7 Add V11.29 empty execution report generator`
- 原始工作区：`D:\code\freqtrade-strategies`

前置 gate：

```text
git status --short --untracked-files=all
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

只读检查命令：

```powershell
git -C D:\code\freqtrade-strategies -c core.quotepath=false status --short --untracked-files=all -- user_data reports dashboard scripts
git -C D:\code\freqtrade-strategies -c core.quotepath=false ls-files --others --exclude-standard -- user_data reports dashboard scripts
```

执行边界确认：

- 未修改原始工作区 `D:\code\freqtrade-strategies`
- 未复制、删除、移动文件
- 未 stash
- 未 commit 原始工作区
- 未读取 secret、`.env`、`user_data/monitor.env`
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未进入 Task 16

## 2. 原始工作区 git 状态摘要

观察到原始工作区仍为 dirty/quarantine-only 状态。

tracked modified 相关面：

```text
M dashboard/lib/config.js
M dashboard/lib/monitor_store.js
M dashboard/lib/trade_supervisor.js
M dashboard/public/app.js
M dashboard/public/index.html
M dashboard/public/styles.css
M dashboard/server.js
M scripts/check_trades.sh
M scripts/format_trade_alert.py
M scripts/refresh_data.sh
M scripts/run_tests.sh
M scripts/start_bot.sh
```

untracked 相关面包括：

- `reports/live_window_execution_check/live_window_execution_check.json`
- `reports/live_window_execution_check/live_window_execution_check.html`
- `scripts/build_v11_closed_loop_report.js`
- `scripts/record_live_readiness.js`
- `scripts/record_opportunity_audit.js`
- `scripts/record_system_health.js`
- `scripts/validate_live_readiness.js`
- `scripts/validate_opportunity_audit.js`
- `scripts/run_v1129_residual_drag_micro_sizer_backtests.sh`
- `user_data/config_multi_futures_v1129.json`
- `user_data/backtest_results/**`

这些路径没有被修改或清理。

## 3. V11.29 execution 数据候选路径

| 候选路径 | 类型 | 大小 / mtime | 可能含真实 dry-run trades | 可能含 open/closed trades | 可能含 orders/fees/funding/slippage/latency | 1d/7d/14d window | V10.8.2 same-window | 结论 |
|---|---|---:|---|---|---|---|---|---|
| `user_data/monitor_history.sqlite` | SQLite | 229376 bytes / 2026-07-01 17:27:02 | 未知 | 未知 | 可能含 runtime/API/monitor events；trade/order/fee 未证明 | 未知 | 未知 | 候选，需要后续授权做 SQLite schema inspection。 |
| `reports/live_window_execution_check/live_window_execution_check.json` | JSON | 2518 bytes / 2026-07-03 17:24:25 | 未知 | 未知 | 未知；可能是 execution window 检查摘要 | 未知 | 未知 | 候选，需要后续授权读取结构。 |
| `reports/live_window_execution_check/live_window_execution_check.html` | HTML | 5283 bytes / 2026-07-03 17:24:25 | 未知 | 未知 | 未知；可能是 JSON 的可读报告 | 未知 | 未知 | 候选，需要后续授权读取结构。 |
| `user_data/config_multi_futures_v1129.json` 中 `db_url` 指向 `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite` | config path reference | config 文件 1906 bytes / 2026-07-02 16:24:47 | 可能，若容器路径实际存在 | 可能 | 可能，取决于 Freqtrade DB schema | 可能，取决于 DB 数据 | 需要 V10.8.2 对照 DB | 只读取了 `db_url` 行；本地对应 SQLite 未发现。 |
| `dashboard/server.js` | dashboard/API code | modified | 不直接含数据 | 不直接含数据 | 可能定义 API route | 不适用 | 不适用 | 代码路径候选，需后续只读代码/API schema 审查。 |
| `dashboard/lib/monitor_store.js` | monitor store code | modified | 不直接含数据 | 不直接含数据 | 可能定义 monitor cache/source | 不适用 | 不适用 | 代码路径候选，需后续只读代码/API schema 审查。 |
| `dashboard/lib/trade_supervisor.js` | supervisor code | modified | 不直接含数据 | 不直接含数据 | 可能定义 blocked signal 逻辑 | 不适用 | 不适用 | 代码路径候选，不能作为 execution 数据。 |
| `scripts/check_trades.sh` | script/log source candidate | modified | 不直接含数据 | 不直接含数据 | 可能采集 API/trade alert | 不适用 | 不适用 | 脚本候选，需后续只读审查；本任务未执行。 |
| `scripts/format_trade_alert.py` | script | modified | 不直接含数据 | 不直接含数据 | 可能格式化 fee/pnl/alert | 不适用 | 不适用 | 脚本候选，需后续只读审查；本任务未执行。 |
| `scripts/build_v11_closed_loop_report.js` | script | untracked | 不直接含数据 | 不直接含数据 | 可能生成 closed-loop report | 不适用 | 不适用 | 生成器候选，非数据源；本任务未执行。 |
| `scripts/record_live_readiness.js`、`scripts/record_system_health.js`、`scripts/record_opportunity_audit.js` | scripts | untracked | 不直接含数据 | 不直接含数据 | 可能采集 runtime/API/opportunity events | 不适用 | 不适用 | 采集逻辑候选，非数据源；本任务未执行。 |

## 4. 明确未找到的 V11.29 本地 trade DB / report evidence

本地原始工作区未发现：

```text
user_data/tradesv3_v1129.dryrun.sqlite
user_data/tradesv3_v1129.dryrun.sqlite-wal
user_data/tradesv3_v1129.dryrun.sqlite-shm
user_data/tradesv3.dryrun.sqlite
user_data/tradesv3.sqlite
reports/reliable_strategy_search_v1129/
reports/v1129_execution_validation/
reports/v11_closed_loop_report.json
reports/v11_closed_loop_report.html
```

因此，虽然 V11.29 config 的 `db_url` 指向容器路径：

```text
sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite
```

但本地 `D:\code\freqtrade-strategies\user_data\tradesv3_v1129.dryrun.sqlite` 不存在。本任务不登录服务器、不读取容器、不启动 bot，因此无法确认该 DB 是否存在于服务器或容器内。

## 5. 只是回测/报告产物，不能当真实执行数据

以下路径类别只能作为研究/回测/市场数据证据，不能直接作为真实 execution 数据：

- `user_data/backtest_results/reliable_strategy_search_v11_data/**`
- `user_data/backtest_results/reliable_strategy_search_v1122_data/**`
- `user_data/backtest_results/reliable_strategy_search_v1119_local/**`
- `reports/btc_mvp/backtests/**`
- `reports/reliable_strategy_search_v1123/**`
- `reports/reliable_strategy_search_v1124/**`
- `reports/reliable_strategy_search_v1125/**`
- `reports/reliable_strategy_search_v1126/**`
- `reports/reliable_strategy_search_v1127/**`
- `reports/*_backtest*`
- `reports/*_high_attack_report*`

这些路径可能含 backtest trades、wallet、market data、funding rate 或 report JSON，但不等同于 V11.29 dry-run/live execution trade/order records。

## 6. 字段覆盖判断

| 字段/能力 | 当前路径级判断 | 后续要求 |
|---|---|---|
| dry-run trades | 未找到本地 V11.29 Freqtrade SQLite；`monitor_history.sqlite` 和 live window JSON 仅为候选 | Task 16 需授权读取 SQLite schema / JSON structure。 |
| open/closed trades | 未证明 | 需要真实 Freqtrade DB/API 或 live window report 内容确认。 |
| orders | 未证明 | 需要 Freqtrade DB/API order table 或 dashboard API schema。 |
| fees | 未证明 | 需要 Freqtrade trade/order fee 字段。 |
| funding | 未证明；backtest market data中的 funding rate 不能代表实际 funding fee | 需要逐笔 funding ledger 或 Freqtrade/exchange 数据。 |
| slippage | 未证明 | 需要 signal expected price + fill price + timestamp chain。 |
| latency | 未证明 | 需要 signal/order/fill timestamps。 |
| blocked signals | 未证明；`trade_supervisor` 和 opportunity audit 脚本是代码候选 | 需要读取 supervisor/opportunity audit 数据。 |
| API errors / stopped / jq parse errors | 未证明；monitor/history 和 scripts 是候选 | 需要读取 monitor DB/log/API cache。 |
| 1d / 7d / 14d observation window | 未证明 | 需要读取候选内容后按 timestamp 统计。 |
| V10.8.2 same-window comparison | 未证明 | 需要定位同窗口 V10.8.2 DB/API/report；当前仅看到 V10.8.2 回测/研究产物。 |

## 7. 需要后续人工授权读取内容的候选

建议后续 Task 16 只读 inspect 以下候选的结构，不读取 secret、不启动 bot、不登录服务器：

- `user_data/monitor_history.sqlite`：读取 SQLite schema、表名、时间字段、是否有 runtime/API/trade-like events。
- `reports/live_window_execution_check/live_window_execution_check.json`：读取 JSON keys，不做交易结论。
- `reports/live_window_execution_check/live_window_execution_check.html`：仅在 JSON 不足时读取结构。
- `dashboard/server.js`、`dashboard/lib/monitor_store.js`：确认 API/cache 路径和数据字段。
- `scripts/check_trades.sh`、`scripts/format_trade_alert.py`：确认 trade alert 字段和 jq/API error 来源。
- `scripts/build_v11_closed_loop_report.js`、`scripts/record_live_readiness.js`、`scripts/record_system_health.js`、`scripts/record_opportunity_audit.js`：确认是否能定位采集输出。

`user_data/config_multi_futures_v1129.json` 本任务只读取了 `db_url` 行。后续若要读取更多配置内容，必须单独授权并先做 secret 过滤策略。

## 8. 是否可以进入 Task 16

可以进入 Task 16：`Read-only Data Source Schema Inspection`，但边界必须收紧：

- 只读读取 `monitor_history.sqlite` schema，不读 secret。
- 只读读取 `live_window_execution_check.json` 的 top-level keys 和字段结构。
- 只读读取 dashboard/monitor store 代码中 API/cache schema，不执行脚本。
- 不读取 `.env`、`user_data/monitor.env`。
- 不启动 bot、不登录服务器、不运行回测。
- 不修改原始工作区。

## 9. 最终判断

当前没有找到可直接用于真实 V11.29 execution validation 的本地 dry-run trade DB。`monitor_history.sqlite` 和 `reports/live_window_execution_check/*` 是候选，但内容未授权读取，不能证明含真实 trades、orders、fees、funding、slippage 或 latency。

因此：当前不能生成真实执行验证报告，只能继续 insufficient 报告，直到 Task 16 或后续任务确认真实 execution 数据源存在且字段足够。
