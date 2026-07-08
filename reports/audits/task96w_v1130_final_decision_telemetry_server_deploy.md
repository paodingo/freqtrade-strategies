# Task 96W: V11.30 Final Decision Telemetry Server Deploy

## Summary

Deployed the behavior-neutral V11.30 final decision telemetry strategy update to
the server and restarted only the V11.30 shadow container.

Conclusion:

```text
v1130_final_decision_telemetry_live_and_observable
```

The live V11.30 telemetry file was generated successfully after restart. The
current live telemetry shows one recent V11.30 candidate row and zero enabled
entry rows.

Important current observation:

```text
BCH/USDT:USDT had 1 candidate row, blocked by blocked_taker_sell_pressure.
enabled_rows = 0
```

This explains the current observation window without claiming that the strategy
is good, bad, replaceable, or non-replaceable.

## Preconditions

- Local worktree: `D:\code\freqtrade-strategies-clean`
- Local branch: `codex/btc-mvp-system-harnessed`
- Local commit before deploy: `2c3aa38`
- Local `git status --short --untracked-files=all`: empty
- Local readiness before deploy: passed
- Source task:
  `reports/audits/task96v_v1130_behavior_neutral_final_decision_telemetry.md`

## Server Target

| item | value |
|---|---|
| host | `43.134.72.69` |
| user | `ubuntu` |
| hostname | `VM-0-8-ubuntu` |
| deploy time UTC | `2026-07-08T13:31Z` to `2026-07-08T13:35Z` |
| server repo path | `/home/ubuntu/freqtrade-strategies` |
| server branch | `master` |
| server commit before deploy | `5a5d426` |
| target container | `freqtrade-v1130-crash-rebound-shadow` |

The server strategy file existed as an untracked live file on the server repo,
so this task did not run `git pull` on the server. It copied the exact local
strategy file to the live strategy path.

## Files Deployed

Copied exactly:

```text
D:\code\freqtrade-strategies-clean\strategies\RegimeAwareV1130CrashReboundShadow.py
```

to:

```text
/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1130CrashReboundShadow.py
```

No bot config, dashboard, deploy files, secrets, or SQLite files were copied.

## Backup

Before copying, the previous server strategy file was backed up to:

```text
/tmp/v1130_telemetry_deploy/RegimeAwareV1130CrashReboundShadow.py.20260708T213129Z.bak
```

This is a rollback artifact only. It was not committed.

## Hash Verification

Local strategy SHA256:

```text
1df64680927a1adac7786bce116ffbb33bd7ef734120405370db636a789b6cad
```

Server strategy SHA256 after copy:

```text
1df64680927a1adac7786bce116ffbb33bd7ef734120405370db636a789b6cad
```

Container compile check:

```text
compile_ok
```

The compile check used `compile()` from stdin and did not write `__pycache__`.

## Runtime Action

Executed:

```text
docker restart freqtrade-v1130-crash-rebound-shadow
```

Only this V11.30 shadow container was restarted.

Observed after restart:

```text
freqtrade-v1130-crash-rebound-shadow Up
freqtrade-v1129 Up 4 days
```

The logs showed:

- `Runmode set to dry_run`
- strategy resolved from
  `/freqtrade/project/strategies/RegimeAwareV1130CrashReboundShadow.py`
- `max_open_trades: 2`
- pairlist with 6 pairs:
  `ETH`, `SOL`, `DOGE`, `LINK`, `XRP`, `BCH`
- state changed to `RUNNING`

Recent error scan:

```text
no matching error / exception / traceback / failed / critical lines after restart
```

## Live Telemetry Evidence

Server generated:

```text
/home/ubuntu/freqtrade-strategies/reports/v1130_observation/v1130_final_decision_telemetry.json
/home/ubuntu/freqtrade-strategies/reports/v1130_observation/v1130_final_decision_telemetry.md
```

These files were copied back to the clean worktree exact paths:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

Live telemetry summary:

| field | value |
|---|---:|
| safety_verdict | `telemetry_only_no_behavior_change` |
| pairs_observed | `6` |
| rows_observed | `300` |
| candidate_rows | `1` |
| enabled_rows | `0` |
| blocked_rows | `1` |

Pair summary:

| pair | rows | candidates | enabled | blocked |
|---|---:|---:|---:|---:|
| `BCH/USDT:USDT` | `50` | `1` | `0` | `1` |
| `DOGE/USDT:USDT` | `50` | `0` | `0` | `0` |
| `ETH/USDT:USDT` | `50` | `0` | `0` | `0` |
| `LINK/USDT:USDT` | `50` | `0` | `0` | `0` |
| `SOL/USDT:USDT` | `50` | `0` | `0` | `0` |
| `XRP/USDT:USDT` | `50` | `0` | `0` | `0` |

Latest visible blocked row:

```text
pair: BCH/USDT:USDT
candle_time: 2026-07-08T13:00:00+00:00
candidate: true
gate: blocked_taker_sell_pressure
enter_long: 0
enter_tag: empty
```

## Safety Boundary

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print API keys, dashboard passwords, exchange credentials, or tokens;
- modify bot config;
- modify dashboard;
- modify deploy files;
- write SQLite;
- run backtests;
- run `freqtrade trade`;
- restart V11.29;
- restart V10.8.2;
- start any stopped legacy bot;
- change thresholds, pairlist, stake, leverage, ROI, stoploss, or order type;
- decide whether V11.30 can replace V10.8.2.

## Verification

Required local verification:

```text
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected changed paths:

```text
reports/audits/task96w_v1130_final_decision_telemetry_server_deploy.md
tasks/active/TASK-0096W-v1130-final-decision-telemetry-server-deploy.md
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

## Recommended Next Task

Proceed with:

```text
Task 96X: V11.30 live final decision telemetry analysis
```

Task 96X should analyze the live telemetry and classify the current zero-order
cause from observed fields. It should not change strategy behavior or draw a
replacement conclusion.
