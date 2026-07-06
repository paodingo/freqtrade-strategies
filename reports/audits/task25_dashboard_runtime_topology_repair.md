# Task 25: Dashboard Runtime Topology Repair

## Summary

本任务修复了服务器 dashboard runtime topology，使 web 主视图匹配当前真实运行的 bot：

- `V11.29 Current Research Candidate` -> `http://localhost:8122`
- `V10.8.2 Historical Profit Benchmark` -> `http://localhost:8091`

并将已停止的历史 lane 移出当前 dashboard 主拓扑：

- `V11.16` / `localhost:8109`
- `V11.27` / `localhost:8120`

本任务只重启了 `freqtrade-monitor.service` dashboard 服务；没有启动、停止、重启任何 Freqtrade trading bot。

## Initial Evidence

Server time:

```text
Mon Jul  6 04:01:37 AM UTC 2026
```

Container reality before repair:

```text
freqtrade-v1129    Up 2 days                  127.0.0.1:8122->8122/tcp
freqtrade-v1127    Exited (137) 2 days ago
freqtrade-v1116    Exited (137) 2 days ago
freqtrade-v1082    Up 5 days                  127.0.0.1:8091->8091/tcp
```

Old dashboard runtime env:

```text
BOT_BASE_LABEL=V11.16 高进攻收益密度策略
BOT_BASE_URL=http://localhost:8109
BOT_CHALLENGER_LABEL=V10.8.2 历史赚钱基准
BOT_CHALLENGER_URL=http://localhost:8091
BOT_SCOUT_AS_THIRD_LANE=1
BOT_SCOUT_LABEL=V11.27 Dual Trap Scout
BOT_SCOUT_URL=http://localhost:8120
BOT_EXTRA_SCOUTS=v1129|V11.29 Best Research Scout|http://localhost:8122
```

Lane health before repair:

```text
v1116 port=8109 ping=000
v1082 port=8091 ping=200
v1127 port=8120 ping=000
v1129 port=8122 ping=200
```

This explains why the web UI appeared to show only V10.8.2 normally: the configured base/scout lanes pointed to stopped containers.

## Server Change

Added systemd drop-in:

```text
/etc/systemd/system/freqtrade-monitor.service.d/35-exec-current-v1129-v1082-topology.conf
```

The drop-in overrides dashboard process runtime environment at `ExecStart` time, without editing or printing `monitor.env` secrets.

Effective topology:

```text
BOT_BASE_KEY=v1129
BOT_BASE_LABEL=V11.29 Current Research Candidate
BOT_BASE_URL=http://localhost:8122
BOT_CHALLENGER_KEY=v1082
BOT_CHALLENGER_LABEL=V10.8.2 Historical Profit Benchmark
BOT_CHALLENGER_URL=http://localhost:8091
BOT_SCOUT_AS_THIRD_LANE=0
BOT_EXTRA_SCOUTS=
BOT_EXTRA_HEALTH_SCOUTS=
```

`freqtrade-monitor.service` was restarted to load the dashboard-only runtime change.

## Cleanup

Two intermediate drop-ins created during troubleshooting were removed:

```text
/etc/systemd/system/freqtrade-monitor.service.d/25-current-v1129-v1082-topology.conf
/etc/systemd/system/freqtrade-monitor.service.d/30-current-v1129-v1082-topology.conf
```

Final drop-ins:

```text
/etc/systemd/system/freqtrade-monitor.service.d/20-v1129-scout.conf
/etc/systemd/system/freqtrade-monitor.service.d/35-exec-current-v1129-v1082-topology.conf
```

The older `20-v1129-scout.conf` remains on disk, but the `35` drop-in's `ExecStart` wrapper supplies the effective runtime lane values.

## Final Verification

Dashboard service:

```text
freqtrade-monitor.service: active
```

Final dashboard process environment:

```text
BOT_BASE_KEY=<redacted>
BOT_BASE_LABEL=V11.29 Current Research Candidate
BOT_BASE_URL=http://localhost:8122
BOT_CHALLENGER_KEY=<redacted>
BOT_CHALLENGER_LABEL=V10.8.2 Historical Profit Benchmark
BOT_CHALLENGER_URL=http://localhost:8091
BOT_EXTRA_HEALTH_SCOUTS=
BOT_EXTRA_SCOUTS=
BOT_SCOUT_AS_THIRD_LANE=0
```

Direct lane health:

```text
v1129 show_config=200
v1082 show_config=200
```

Final bot container state:

```text
freqtrade-v1129    Up 2 days                  127.0.0.1:8122->8122/tcp
freqtrade-v1127    Exited (137) 2 days ago
freqtrade-v1116    Exited (137) 2 days ago
freqtrade-v1082    Up 5 days                  127.0.0.1:8091->8091/tcp
```

## Boundary Confirmation

This task did not:

- read `.env`;
- read or print `user_data/monitor.env`;
- print dashboard password;
- print Freqtrade API credentials;
- modify bot configs;
- modify strategy files;
- start, stop, or restart trading bots;
- run backtests;
- claim V11.29 replacement readiness.

## Current Assessment

Dashboard runtime topology now matches the active comparison surface:

- Current research candidate: V11.29 on `8122`
- Benchmark: V10.8.2 on `8091`

The stopped historical containers remain stopped and are no longer part of the dashboard main lane topology.

## Recommended Next Task

Recommended next task:

```text
Task 26: Trade Monitor Alert Debounce Plan
```

Goal:

- Reduce noisy Telegram `API 异常` alerts by requiring retries or consecutive failures before alerting.
- Preserve real alerts for sustained API outages or stopped bots.

