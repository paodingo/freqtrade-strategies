# TASK-0026: Trade Monitor Alert Stability Patch

## Goal

Reduce noisy Telegram `API 异常` alerts caused by transient Freqtrade API read failures or notification-chain failures.

## Trigger

At 2026-07-06 13:40 CST, Telegram reported:

```text
[V10.8.2 历史赚钱基准] API 异常
端口：localhost:8091
说明：无法完整读取 bot 状态，请检查容器/API。
```

Read-only evidence showed V10.8.2 was still `RUNNING` during that window.

## Allowed Changes

- `scripts/check_trades.sh`
- `scripts/notify_trades.sh`
- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task26_trade_monitor_alert_stability_patch.md`
- `tasks/active/TASK-0026-trade-monitor-alert-stability-patch.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**` bot configs
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- V10.8.2 strategy/config
- V11.29 strategy/config
- live trading operations

## Completed Work

- Confirmed V10.8.2 was `RUNNING` around the alert time.
- Confirmed monitor log contained repeated `jq parse error` and OpenClaw delivery failures.
- Updated `scripts/check_trades.sh` with retry and consecutive-failure debounce.
- Limited monitor targets to active V11.29 and V10.8.2 lanes.
- Updated `scripts/notify_trades.sh` so delivery failures emit `TRADE_NOTIFY:` instead of `TRADE_ALERT:`.
- Added exact guard exceptions for monitor stability scripts.
- Updated harness change-surface matrix.

## Verification

- `bash -n scripts/check_trades.sh`
- `bash -n scripts/notify_trades.sh`
- `node --check scripts/guard_harness_diff.js`
- `node --check scripts/guard_trading_surface.js`
- Server dry-run with temporary state file
- Server wrong-auth debounce self-test
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, push, and server script deployment. Do not enter Task 27 automatically.
