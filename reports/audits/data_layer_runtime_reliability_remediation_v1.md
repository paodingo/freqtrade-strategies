# Data Layer Runtime Reliability Remediation V1

## Outcome

Implemented a bounded Dashboard data-path repair without changing strategy or
bot lifecycle surfaces.

- Binance Futures public requests now use an environment-aware fetch adapter.
- When `HTTPS_PROXY` or `HTTP_PROXY` is configured, public GET requests use
  Node's native environment-proxy support on Node 24.5+, or a `curl`
  compatibility path on older Node versions.
- Local Freqtrade requests always bypass the proxy.
- Freqtrade API and shadow SQLite failures now expose explicit runtime states
  instead of being conflated with Binance market-data failure.
- The monitor service enables Node's native environment-proxy support where the
  installed Node version supports it, while the application adapter remains the
  compatibility path.

## Existing Refresh Automation

No new market-data timer was added. Audit history proves that the dedicated
`freqtrade-v1130-market-data-refresh.timer` was already installed and verified
on the server in Task 94V. Creating a second timer would introduce duplicate
downloads and ambiguous ownership.

## Verification

Unit and syntax checks:

```text
node --check dashboard/lib/env_aware_fetch.js: pass
node --check dashboard/server.js: pass
node --test tests/test_env_aware_fetch.js tests/test_binance_futures_alpha.js:
12 passed, 0 failed
```

Local end-to-end probe with the Docker engine and Freqtrade API intentionally
unavailable:

```json
{
  "sourceType": "binance_futures",
  "fallback": true,
  "candles": 40,
  "tickerSource": "Binance Futures",
  "alphaStatus": "ok",
  "alphaErrors": 0,
  "botRuntimeStatus": "unreachable",
  "botErrorCode": "ECONNREFUSED",
  "shadowRuntimeStatus": "not_provisioned"
}
```

This proves that current price and candle data remain available through the
Binance fallback while simulated PnL correctly remains unavailable until a
dry-run runtime or shadow database exists.

## Safety Boundary

This remediation did not:

- start, stop, or restart any bot;
- execute `freqtrade trade`;
- modify a strategy or trading config;
- run a backtest;
- read secrets;
- deploy to the server.

## Deployment Requirement

Repository implementation is complete, but the running server will not use it
until this branch is reviewed, merged, deployed, and
`freqtrade-monitor.service` is restarted. The already-installed V11.30 refresh
timer should be checked separately during deployment; it must not be duplicated.
