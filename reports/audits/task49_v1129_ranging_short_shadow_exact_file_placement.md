# Task 49: V11.29 Ranging-Short Shadow Exact File Placement

## Summary

Copied exactly two Task 45 shadow files to the server file placement paths
identified in Task 48.

This task did not start, stop, or restart any bot. It did not run
`freqtrade trade`, did not run backtests, did not read env files, did not read
secrets, did not create SQLite data, and did not modify any existing strategy or
existing bot config.

## Local Preconditions

```text
cwd: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status before task: clean
readiness before task: pass
```

## Server Target

```text
host: 43.134.72.69
user: ubuntu
key file used: D:\key\openclaw\clf.pem
```

The provided `D:\key\openclaw` path is a directory. The actual key file used
was `D:\key\openclaw\clf.pem`. Key contents were not read or printed.

## Files Copied

| Local source | Server target |
| --- | --- |
| `strategies/RegimeAwareV1129RangingShortShadow.py` | `/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py` |
| `user_data/config_multi_futures_v1129_ranging_short_shadow.json` | `/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json` |

Temporary transfer paths:

```text
/tmp/RegimeAwareV1129RangingShortShadow.py
/tmp/config_multi_futures_v1129_ranging_short_shadow.json
```

Temporary files were removed after install.

## Copy Method

```text
scp exact local strategy file to /tmp
scp exact local config file to /tmp
install -m 0644 exact /tmp files into /home/ubuntu/freqtrade-strategies
rm exact /tmp files
```

No directories were recursively copied.

## Hash Verification

Server SHA256:

```text
25ea45add7ff254816da3f06a28c0c4fe7005fe4b4c110cd39de5a0e1b4b8d70  /home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
285801915aea45e6a48e9528bce0910bb42f923d7e27db973a8d490ef2033d4f  /home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

These match the local Task 45 file hashes observed before copy.

## Container Visibility

The same files are visible inside both existing containers through the bind
mount:

```text
/freqtrade/project/strategies/RegimeAwareV1129RangingShortShadow.py
/freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Observed containers:

```text
freqtrade-v1129: Up 3 days, 127.0.0.1:8122->8122/tcp
freqtrade-v1082: Up 6 days, 127.0.0.1:8091->8091/tcp
```

No container was restarted.

## Port Check

```text
port 8123 listener: none observed
```

This task did not bind or reserve the port.

## Server Git Status For Exact Paths

```text
?? strategies/RegimeAwareV1129RangingShortShadow.py
?? user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

No server commit was made.

## Explicit Non-Actions

This task did not:

- start the shadow bot;
- stop or restart existing bots;
- run `freqtrade trade`;
- run backtests;
- create or write the shadow SQLite DB;
- read `.env`;
- read `user_data/monitor.env`;
- print or copy credentials;
- modify existing V10.8.2 strategy/config;
- modify existing V11.29 strategy/config;
- modify dashboard files;
- modify deploy files;
- commit the server worktree.

## Current Start Readiness

File placement is ready.

Start is still not authorized by this task and should remain blocked until a
separate resource/start decision confirms that a third bot is safe or that
server resources have been freed.

## Recommended Task 50

Recommended next task:

```text
Task 50: V11.29 Ranging-Short Shadow Start Readiness and Resource Gate
```

Task 50 should re-check memory/swap, port `8123`, file presence, config sanity,
and current bot stability. It should either:

1. authorize starting the shadow bot under strict boundaries; or
2. explicitly defer start due to resource pressure.
