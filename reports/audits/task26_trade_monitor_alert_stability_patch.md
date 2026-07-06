# Task 26: Trade Monitor Alert Stability Patch

## Summary

本任务针对 2026-07-06 13:40 CST 收到的 `[V10.8.2 历史赚钱基准] API 异常` 提醒做最小修复。

调查结论：该时间窗口内 `freqtrade-v1082` 日志连续显示 `state='RUNNING'`，当前 API 也可读；更可能的问题是交易监控脚本把单次 endpoint 读取失败或 JSON 解析失败直接升级为 Telegram `API 异常`，同时通知链路本身存在 `OpenClaw notification failed` 噪音。

本任务没有判断 V11.29 是否可以替换 V10.8.2。

## Root-Cause Evidence

服务器检查时间：

```text
Mon Jul  6 14:11:50 CST 2026
```

容器状态：

```text
freqtrade-v1129 Up 2 days 127.0.0.1:8122->8122/tcp
freqtrade-v1082 Up 5 days 127.0.0.1:8091->8091/tcp
```

V10.8.2 在 13:35-13:45 CST 对应窗口的日志：

```text
2026-07-06 05:35:57 ... state='RUNNING'
2026-07-06 05:36:57 ... state='RUNNING'
2026-07-06 05:37:57 ... state='RUNNING'
2026-07-06 05:38:57 ... state='RUNNING'
2026-07-06 05:40:11 ... state='RUNNING'
2026-07-06 05:41:11 ... state='RUNNING'
2026-07-06 05:42:11 ... state='RUNNING'
2026-07-06 05:43:11 ... state='RUNNING'
2026-07-06 05:44:11 ... state='RUNNING'
```

交易监控日志尾部统计：

```text
39 jq: parse error: Unmatched '}' at line 1, column 1308
161 TRADE_ALERT: OpenClaw notification failed for openclaw-weixin.
```

## Changes

### `scripts/check_trades.sh`

- 将监控目标收窄到当前真实运行的两条线：
  - `V11.29 Current Research Candidate:8122`
  - `V10.8.2 Historical Profit Benchmark:8091`
- 移除已停止的历史容器监控目标：
  - `V11.16 / 8109`
  - `V11.27 / 8120`
- 增加 endpoint 读取重试：
  - `TRADE_MONITOR_API_RETRY_ATTEMPTS`，默认 `2`
  - `TRADE_MONITOR_API_RETRY_SLEEP_SECONDS`，默认 `1`
- 增加连续失败防抖：
  - `TRADE_MONITOR_API_FAILURE_ALERT_THRESHOLD`，默认 `3`
  - 第 1、2 次 API 读取失败只写入 state，不输出 Telegram alert
  - 第 3 次连续失败才输出 `api_error`
- 在 state 中记录：
  - `api_probe_ok`
  - `consecutive_api_failures`
  - `api_failure_alert_threshold`
  - `failed_endpoints`

### `scripts/notify_trades.sh`

- 通知渠道自身失败时输出 `TRADE_NOTIFY:`，不再输出 `TRADE_ALERT:`。
- 目的：避免 OpenClaw / Telegram delivery failure 被误认为新的交易运行提醒。

### Guard

增加精确 guard 例外：

- `scripts/check_trades.sh`
- `scripts/notify_trades.sh`

该例外只用于交易监控告警稳定性维护，不允许策略、bot 配置、dashboard、deploy、生命周期脚本、secret 或交易参数变更。

## Verification

本地语法检查：

```text
bash -n scripts/check_trades.sh
bash -n scripts/notify_trades.sh
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
```

结果：通过。

服务器临时 dry-run，使用临时 state 文件，不发送通知、不改 bot：

```text
V11.29 Current Research Candidate:
  ok=true
  api_probe_ok=true
  consecutive_api_failures=0
  state=running
  total=0

V10.8.2 Historical Profit Benchmark:
  ok=true
  api_probe_ok=true
  consecutive_api_failures=0
  state=running
  total=6
  closed=6
```

错误 auth 防抖自测：

```text
run 1: consecutive_api_failures=1, no TRADE_ALERT
run 2: consecutive_api_failures=2, no TRADE_ALERT
run 3: consecutive_api_failures=3, TRADE_ALERT emitted
```

## Server Deployment

本任务将修复后的监控脚本部署到服务器：

```text
/home/ubuntu/freqtrade-strategies/scripts/check_trades.sh
/home/ubuntu/freqtrade-strategies/scripts/notify_trades.sh
```

部署不需要重启交易 bot，也不修改 bot 配置。

## Boundary Confirmation

本任务没有：

- 修改 `strategies/**`
- 修改 `user_data/config*.json`
- 修改 `configs/**`
- 修改 dashboard 代码
- 修改 deploy 代码
- 读取 `.env`
- 读取或打印 `user_data/monitor.env`
- 打印 API key、交易所凭证、服务器密钥或 dashboard 密码
- 启动、停止或重启交易 bot
- 运行回测
- 修改 V10.8.2 或 V11.29 策略/config
- 得出 V11.29 替换 V10.8.2 的结论

## Expected Effect

13:40 这类单次 API 读取抖动将不再立即触发 Telegram `API 异常`。只有连续 3 次读取失败时才会发出 API 异常提醒。

通知渠道自身失败会进入 delivery log 和 `TRADE_NOTIFY:` 输出，不再伪装成新的 `TRADE_ALERT`。

## Recommended Next Task

推荐下一步：

```text
Task 27: Trade Monitor Message Encoding and Formatter Cleanup
```

目标：

- 修复服务器和仓库中提醒 formatter 的历史乱码文本；
- 将 `api_error` 文案升级为明确分类：endpoint timeout、JSON parse failure、unauthorized、bot stopped、delivery failure；
- 保持不改策略、不改 bot 配置、不读取 secret。
