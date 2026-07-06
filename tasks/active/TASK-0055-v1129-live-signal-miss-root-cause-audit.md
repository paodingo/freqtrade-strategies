# TASK-0055: V11.29 Live Signal Miss Root-Cause Audit

## Objective

只读审计 V11.29 在强波动行情中没有产生 trades/orders 的根因，确认是运行故障、数据链路问题、dashboard 展示问题，还是策略 entry / filter 体系过度防守。

## Preconditions

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- `git status --short --untracked-files=all` 在写入前为空
- `.\scripts\run_agent_readiness_checks.ps1` 在写入前通过

## Allowed Changes

- `reports/audits/task55_v1129_live_signal_miss_root_cause_audit.md`
- `tasks/active/TASK-0055-v1129-live-signal-miss-root-cause-audit.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key、交易所凭证、服务器密钥、dashboard 密码
- V10.8.2 策略/config
- V11.29 策略/config
- live/server 运行面
- 原始脏工作区 `D:\code\freqtrade-strategies`

## Evidence Collected

- 本地 branch/status/readiness。
- 服务器容器状态：`freqtrade-v1129`、`freqtrade-v1129-ranging-short-shadow`、`freqtrade-v1082`。
- V11.29 API：`show_config`、`count`、`status`、`locks`、`profit`、`balance`。
- SQLite 只读查询：V11.29 main、V11.29 shadow、V10.8.2 baseline。
- `/api/v1/pair_candles` 最近 96 根 15m K 线 signal/gate 统计。
- 策略过滤代码只读定位：`alpha_risk_filter.py`、`regime_aware_base.py`、`RegimeAwareV1129RangingShortShadow.py`。

## Result

V11.29 当前无交易不是 dashboard 展示错误，也不是 stopped/locked/insufficient balance。根因集中在 entry/gate 层：

- long 被 `topTraderAccountLongCrowding` 触发的 `alpha_filter_block_long` 全面阻断；
- short 侧 ADX/EMA/range 条件过窄；
- shadow lane 启动晚且覆盖面有限；
- 高波动行情没有被有效转化为 orders。

## Next Task

推荐执行 Task 56：`High-Volatility Strategy Candidate Search Plan`。

目标是尽快从 V11.29 小修小补转向下一代策略候选搜索，并用最近强波动事件做 replay / miss matrix。

