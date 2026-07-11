# Stage 3A.5-F3 Futures Online/Offline Adapter Certification

Date: 2026-07-10

## Verdict

Stage 3A is complete for the fixed futures acceptance fixture.

The certification run proved:

- FUTURES-ONLINE-BASELINE succeeded.
- FUTURES-OFFLINE-CONTROL succeeded on the same host.
- Online and offline core metrics matched exactly.
- Online and offline normalized futures trade hash matched exactly.
- Only allowlisted Binance USD-M public market-data endpoint requests were observed.
- `RegimeAwareV6` was not modified.

## Fixed Inputs

- Campaign: `research/campaigns/active/demo-futures-stage3a5-acceptance.yaml`
- Certification experiment: `stage3a5-futures-f3-cert-003`
- Strategy: `RegimeAwareV6`
- Strategy SHA256: `1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509`
- Pair: `BTC/USDT:USDT`
- Trading mode: `futures`
- Margin mode: `isolated`
- Timerange: `20260329-20260412`
- Timeframe: `1h`
- Cache: `none`
- Input fingerprint: `c770e0ab66bb76daa1249851d94006e66e2efdb08ceb334ae444c2dd6730bd79`
- Dataset snapshot: `demo-btc-usdt-usdt-futures-acceptance-20260329-20260412`
- Exchange snapshot: `binance-usdm-futures-2025-8-demo`
- Exchange aggregate SHA256: `599d67345bed5b2b3b42669baf460fa336ffde80502cfd1880ea57cd0dc5074d`

## Endpoint Doctor

Direct no-proxy diagnosis:

- Artifact: `research/runtime/provisioning/stage3a5-f3-futures-endpoint-doctor-direct.json`
- DNS succeeded.
- Direct IPv4 TCP 443 timed out.
- Direct TLS timed out.
- Direct `/fapi/v1/time` timed out.
- Direct `/fapi/v1/exchangeInfo` timed out.
- Direct CCXT sync and async `load_markets()` timed out.
- Direct Freqtrade CLI initialization timed out.

Research-only proxy diagnosis:

- Artifact: `research/runtime/provisioning/stage3a5-f3-futures-endpoint-doctor-proxy.json`
- Proxy type: `httpsProxy`
- Proxy host/port: `127.0.0.1:10808`
- `/fapi/v1/time`: HTTP 200
- `/fapi/v1/exchangeInfo`: HTTP 200
- CCXT sync `load_markets()`: success, `831` markets, `BTC/USDT:USDT` present
- CCXT async `load_markets()`: success, `831` markets, `BTC/USDT:USDT` present
- Freqtrade CLI initialization: success

The proxy URL is not stored in campaign YAML, committed config, or sealed
snapshot. Reports store only proxy type, host, port, scheme, and auth-present
boolean.

## Online Request Audit

Artifact:

- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/ONLINE-BASELINE/online-network-audit.json`

Observed requests:

| Method | Host | Path | Classification | Count | Status |
|---|---|---|---|---:|---:|
| GET | `fapi.binance.com` | `/fapi/v1/exchangeInfo` | public market data | 3 | 200 |

Violations: none.

No signed, private, account, balance, order, position, listen-key, or unknown
non-allowlisted endpoint was observed.

## Online Baseline

Artifact:

- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/ONLINE-BASELINE/runner-report.json`

Result:

- Status: accepted
- Total trades: `3`
- Long trades: `2`
- Short trades: `1`
- Total profit: `66.34329576`
- Total profit ratio: `0.006634329576000001`
- Max drawdown: `0.27958697`
- Profit Factor: `238.29037072078145`
- Win rate: `0.6666666666666666`
- Average duration: `1 day, 16:00:00`
- Average leverage: `1.0`
- Funding fees: `0.20088932145673266`
- Enter tags: `ranging_short: 1`, `trending_long: 2`
- Exit reasons: `force_exit: 1`, `ranging_target_middle: 1`, `roi: 1`
- Normalized futures trades SHA256: `74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`

Note: the generated online-only temporary config enables order-book pricing to
pass Freqtrade's real Binance futures exchange capability validation. The final
normalized trade hash matches the sealed offline control exactly, so this
compatibility shim did not change the fixture's trade semantics.

## Offline Control

Artifact:

- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/OFFLINE-CONTROL/runner-report.json`

Result:

- Status: accepted
- Network policy: socket blocker enabled
- Non-loopback network attempts: none
- Total trades: `3`
- Long trades: `2`
- Short trades: `1`
- Normalized futures trades SHA256: `74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`

## Semantic Comparison

Artifact:

- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/online-offline-comparison.json`

Result:

- `consistent`: `true`
- `differences`: `{}`

The following matched exactly:

- total trades
- long trades
- short trades
- total profit
- total profit ratio
- max drawdown
- Profit Factor
- win rate
- average duration
- average leverage
- funding fees
- enter tag distribution
- exit reason distribution
- normalized futures trade hash

## Reproducibility

Artifacts:

- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/RUN-A/runner-report.json`
- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/RUN-B/runner-report.json`
- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/run-a-run-b-comparison.json`

Result:

- RUN-A/RUN-B consistent: `true`
- RUN-A/RUN-B input fingerprint consistent: `true`
- Differences: `{}`

## Final Report

Final machine-readable report:

- `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/stage3a5-final-report.json`

Status:

- `campaign_execution.status`: `completed`
- `stage_acceptance.status`: `passed`
- `stage3a_complete`: `true`

## Safety Notes

This certification did not:

- modify `RegimeAwareV6`;
- modify the fixture window;
- modify sealed exchange or data snapshots;
- run Hyperopt;
- run Lookahead Analysis;
- run Recursive Analysis;
- access private/account/trade endpoints;
- start Docker, server, bot, deploy, or live trading.
