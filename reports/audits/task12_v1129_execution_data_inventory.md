# Task 12: V11.29 Execution Data Inventory

结论：本任务只读盘点了 V11.29 真实执行验证所需的数据源。当前 clean worktree 可以继续承载后续审计开发，但现有路径级证据还不足以直接生成 V11.29 真实执行验证报告；需要后续 Task 13 先定义报告 schema，再另起采集/导出任务补齐 dry-run trade DB/API/log 样本。

本任务没有判断 V11.29 是否可以替换 V10.8.2。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 11 commit：`ef50185 Inventory trading system surfaces`
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

只读观察命令：

```powershell
git -C D:\code\freqtrade-strategies -c core.quotepath=false status --short --untracked-files=all -- reports user_data scripts dashboard strategies
git -C D:\code\freqtrade-strategies -c core.quotepath=false diff --name-only -- reports user_data scripts dashboard strategies
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
- 未进入 Task 13

## 2. 原始工作区状态摘要

原始工作区仍有交易面 dirty 状态，必须继续作为 evidence-only/quarantine 处理。

`git status` 观察到的相关 tracked modified 路径包括：

```text
dashboard/lib/config.js
dashboard/lib/monitor_store.js
dashboard/lib/trade_supervisor.js
dashboard/public/app.js
dashboard/public/index.html
dashboard/public/styles.css
dashboard/server.js
scripts/check_trades.sh
scripts/format_trade_alert.py
scripts/refresh_data.sh
scripts/run_tests.sh
scripts/start_bot.sh
strategies/RegimeAwareV661AlphaRisk.py
strategies/RegimeAwareV66AlphaRisk.py
strategies/RegimeAwareV67AlphaRisk.py
strategies/regime_aware_base.py
strategies/trade_supervisor_filter.py
```

这意味着 dashboard/API、脚本、策略基类和 supervisor 相关逻辑仍不能被 Codex 自动采纳或修补，后续只能按显式任务做只读审查。

## 3. V11.29 数据源清单

| 数据源 | 路径 | 可用性 | 可信度 | 说明 |
|---|---|---|---|---|
| V11.29 策略候选 | `strategies/RegimeAwareV1129ResidualDragMicroSizer.py` | 存在 | 中 | 只能说明候选策略文件存在；本任务未读取或评判策略逻辑。 |
| V11.29 bot 配置候选 | `user_data/config_multi_futures_v1129.json` | 存在 | 中 | 只能说明配置文件存在；本任务未读取配置内容，不能证明 dry-run/live 实际使用。 |
| V11.29 回测脚本 | `scripts/run_v1129_residual_drag_micro_sizer_backtests.sh` | 存在 | 中 | 可作为研究/回测来源，不等同真实执行数据。 |
| V11.29 专用报告目录 | `reports/reliable_strategy_search_v1129` | 未发现 | 高 | 路径存在性检查为 `False`；`reports/**` 中匹配 `v1129` 的文件数为 `0`。 |
| live window 执行检查 | `reports/live_window_execution_check/live_window_execution_check.json`、`reports/live_window_execution_check/live_window_execution_check.html` | 存在 | 中 | 可作为执行窗口审查候选；本任务未读取内容，不能确认样本或字段。 |
| 监控历史 SQLite | `user_data/monitor_history.sqlite` | 存在 | 中 | 可能包含监控/API/状态历史；本任务未查询数据库，不能确认包含 V11.29 trade 样本。 |
| 常见 Freqtrade dry-run DB | `user_data/tradesv3.sqlite`、`user_data/tradesv3.dryrun.sqlite`、`user_data/freqtrade.sqlite`、`user_data/freqtrade.dryrun.sqlite` | 未发现 | 高 | 路径存在性检查均为 `False`；当前不能直接定位 Freqtrade trade DB。 |
| dashboard API 代码面 | `dashboard/server.js`、`dashboard/lib/monitor_store.js`、`dashboard/lib/trade_supervisor.js` | 存在且 modified | 低到中 | 有可复用入口，但原始工作区 dirty，必须先人工审查或另起只读 API schema 任务。 |
| 系统/交易监控脚本 | `scripts/check_trades.sh`、`scripts/format_trade_alert.py`、`scripts/check_system_health.sh` | 存在，部分 modified | 低到中 | 可作为报警和状态采集线索；不能直接证明 trade 样本。 |
| closed-loop/readiness/opportunity 脚本 | `scripts/build_v11_closed_loop_report.js`、`scripts/record_live_readiness.js`、`scripts/record_system_health.js`、`scripts/record_opportunity_audit.js`、`scripts/validate_live_readiness.js`、`scripts/validate_opportunity_audit.js` | 存在 | 中 | 可复用为后续报告或采集设计参考；本任务未执行。 |

## 4. V10.8.2 对照数据源清单

| 数据源 | 路径 | 可用性 | 可信度 | 说明 |
|---|---|---|---|---|
| V10.8.2 策略候选 | `strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py` | 存在 | 中 | 只能说明候选策略文件存在；未读取策略内容。 |
| V10.8.2 bot 配置候选 | `user_data/config_multi_futures_v1082.json` | 存在 | 中 | 只能说明配置文件存在；未读取配置内容。 |
| V10.8.2 30d/70d 回测结果 | `reports/reliable_strategy_search_v109/v1082_30d/**`、`reports/reliable_strategy_search_v109/v1082_70d/**` | 存在 | 中 | 属于回测/研究证据，不等同真实执行对照。 |
| V10.8.2 复跑结果 | `reports/reliable_strategy_search_v1124/v1082_30d/**`、`reports/reliable_strategy_search_v1124/v1082_70d/**` | 存在 | 中 | 观察到 `json`、`config.json`、`market_change.feather`、`wallet.feather` 等产物。 |
| V10.8.2 报告文件数量 | `reports/**` 匹配 `v1082` | 18 个文件 | 高 | 只统计路径名，不读取内容。 |
| V10.8.2 真实执行 trade DB/API | 常见 Freqtrade DB/API 导出路径 | 未定位 | 高 | 当前路径级证据不能证明 V10.8.2 有可对照的真实执行样本。 |

## 5. 字段可用性矩阵

| 字段 | 候选来源 | 当前可用性 | 可信度 | 说明 |
|---|---|---|---|---|
| V11.29 dry-run trades | Freqtrade dry-run DB、dashboard API、`monitor_history.sqlite` | 未证明 | 低 | 常见 trade DB 未发现；监控库存在但未查询，不能确认含 trade rows。 |
| open trade 记录 | Freqtrade DB/API、dashboard API | 未证明 | 低 | 需要 API/DB 导出。 |
| closed trade 记录 | Freqtrade DB/API、dashboard API | 未证明 | 低 | 需要 API/DB 导出。 |
| order price | Freqtrade orders/trades 表或 API orders | 未证明 | 低 | 当前没有读取 DB/API，不能证明字段存在。 |
| fee | Freqtrade trade/order 字段 | 未证明 | 低 | 需要 `fee_open`、`fee_close` 或 order fee 明细。 |
| funding fee | futures funding 数据或 exchange/order/funding 日志 | 部分候选 | 低 | `user_data/data/futures/*funding_rate.feather` 存在，但它是市场数据，不等同每笔实际 funding fee。 |
| slippage bps | 信号预期价、实际成交价、成交时间 | 未证明 | 低 | 需要 signal snapshot 与 fill record 对齐；当前没有确认采集链。 |
| entry tag | Freqtrade trade 字段或 strategy tag | 未证明 | 低 | 需要 DB/API 导出。 |
| exit reason | Freqtrade closed trade 字段 | 未证明 | 低 | 需要 closed trade 导出。 |
| pair | Freqtrade trade 字段 | 未证明 | 低 | 需要 DB/API 导出。 |
| side | Freqtrade trade 字段 | 未证明 | 低 | 需要 futures trade DB/API 导出。 |
| open time | Freqtrade trade 字段 | 未证明 | 低 | 需要 DB/API 导出。 |
| close time | Freqtrade closed trade 字段 | 未证明 | 低 | 需要 DB/API 导出。 |
| bot running uptime | `record_live_readiness.js`、`record_system_health.js`、dashboard status | 部分候选 | 中 | 有脚本/API 路径，但未读取历史内容，不能证明连续 uptime。 |
| API 异常 | `check_system_health.sh`、dashboard API、monitor history | 部分候选 | 中 | 可另起只读日志/API 审查；本任务未查询。 |
| stopped/API 500/jq parse error 报警 | `check_trades.sh`、`format_trade_alert.py`、monitor history | 部分候选 | 中 | 脚本存在且部分 modified；需要人工审查报警格式和历史记录。 |
| 成交延迟 | signal timestamp、order timestamp、fill timestamp | 未证明 | 低 | 当前未定位完整链路。 |
| 未成交信号 | opportunity audit、order status、signal logs | 未证明 | 低 | `record_opportunity_audit.js` 存在，但未证明覆盖 V11.29。 |
| 被阻断信号 | `trade_supervisor`、opportunity audit、supervisor replay | 部分候选 | 中 | `dashboard/lib/trade_supervisor.js` 和 `scripts/audit_supervisor_blocks.py` 存在；需要另起审查。 |
| 同期 V10.8.2 对照 | V10.8.2 trade DB/API 或 matching window report | 未证明 | 低 | 仅定位到回测/研究报告，未定位真实执行对照样本。 |
| 最近 1d 样本数 | DB/API 按时间窗口聚合 | 当前不能证明 | 低 | 本任务未查询 DB/API。 |
| 最近 7d 样本数 | DB/API 按时间窗口聚合 | 当前不能证明 | 低 | 本任务未查询 DB/API。 |
| 最近 14d 样本数 | DB/API 按时间窗口聚合 | 当前不能证明 | 低 | 本任务未查询 DB/API。 |

## 6. 当前样本是否足够

当前样本不足以生成正式的 V11.29 真实执行验证报告。

原因：

- `reports/reliable_strategy_search_v1129` 未发现，`reports/**` 中 `v1129` 文件数为 `0`。
- 常见 Freqtrade dry-run SQLite 路径未发现：`user_data/tradesv3.sqlite`、`user_data/tradesv3.dryrun.sqlite`、`user_data/freqtrade.sqlite`、`user_data/freqtrade.dryrun.sqlite` 均不存在。
- `user_data/monitor_history.sqlite` 存在，但本任务只做路径级盘点，未查询表结构或数据行，不能证明包含 V11.29 open/closed trade 样本。
- `reports/live_window_execution_check/*` 存在，但未读取内容，不能证明字段覆盖或样本窗口。
- 原始工作区的 dashboard/scripts 处于 modified 状态，API/监控路径可作为线索，不能直接作为可信执行结论。

## 7. 可直接算、需新增采集、当前不能证明

可直接算的字段：当前没有字段可以在不新增 DB/API/log 导出、不读取执行数据的前提下直接计算。

有候选来源但需新增采集/导出的字段：

- open/closed trade count
- pair、side、open time、close time
- entry tag、exit reason
- order price、fee
- bot running uptime
- API 异常、stopped/API 500/jq parse error 报警
- 被阻断信号、未成交信号

必须新增采集或另起任务确认的字段：

- funding fee 的逐笔归因
- slippage bps
- 成交延迟
- 信号到订单、订单到成交、阻断/未成交的事件链
- V11.29 与 V10.8.2 同期真实执行对照样本
- 最近 1d/7d/14d 可用样本数

当前不能证明的事项：

- V11.29 是否已真实 dry-run 执行
- V11.29 是否已有 closed trades
- V11.29 是否有足够样本用于替换判断
- V10.8.2 是否有同窗口真实执行对照
- dashboard API 是否能稳定提供完整 trade/order/fee/funding 字段

## 8. 可复用报告、脚本、API 路径

后续可只读审查或在 clean worktree 中迁移/重建的候选：

- `reports/live_window_execution_check/live_window_execution_check.json`
- `reports/live_window_execution_check/live_window_execution_check.html`
- `user_data/monitor_history.sqlite`
- `dashboard/server.js`
- `dashboard/lib/monitor_store.js`
- `dashboard/lib/trade_supervisor.js`
- `scripts/build_v11_closed_loop_report.js`
- `scripts/record_live_readiness.js`
- `scripts/record_system_health.js`
- `scripts/record_opportunity_audit.js`
- `scripts/validate_live_readiness.js`
- `scripts/validate_opportunity_audit.js`
- `scripts/check_trades.sh`
- `scripts/format_trade_alert.py`

这些路径仍属于原始工作区 evidence-only 候选。本任务没有复制、迁移或执行它们。

## 9. 新增采集需求

新增采集必须另起任务，不应混入 Task 12：

- 只读导出 Freqtrade DB/API 的 trade、order、fee、entry/exit 字段。
- 只读检查 `user_data/monitor_history.sqlite` 表结构和时间窗口覆盖。
- 定义 V11.29 与 V10.8.2 同期比较窗口。
- 采集 bot uptime、API 500、stopped、jq parse error 等状态事件。
- 采集 signal、blocked signal、unfilled signal、order fill 之间的关联键。
- 明确 funding fee 的实际来源：exchange trade/order/funding API、Freqtrade DB 字段，或独立 funding ledger。

## 10. Task 13 推荐

推荐 Task 13：`V11.29 Execution Report Schema`。

建议 Task 13 只定义报告 schema 和字段 contract，不读取 secret、不启动 bot、不登录服务器、不运行回测。Schema 应至少包含：

- 数据源表：DB/API/report/log 路径、时间窗口、采集时间、可信度。
- trade 表：pair、side、open time、close time、order price、average fill price、amount、fee、funding fee、entry tag、exit reason。
- execution quality 表：slippage bps、signal time、order create time、fill time、latency seconds、unfilled reason。
- reliability 表：bot uptime、API exception、stopped/API 500/jq parse error、missing data interval。
- supervisor 表：allowed signals、blocked signals、block reason、unfilled signals。
- comparison 表：V11.29 与 V10.8.2 同期窗口、样本数、字段完整性、不可比较原因。
