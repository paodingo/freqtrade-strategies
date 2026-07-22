# Development-only descriptive profile: discovery-bnb-xrp-timeframe-coherence-v1-v1

- Handler: `cross_pair_distribution_profile_v1`
- Datasets: 4 sealed Development manifests
- Windows: 5 (full window plus four frozen slices)
- Network, backtest, signals, trades, Candidate, strategy changes, Validation and Holdout: `0`

## Full-window rankings

| Timeframe | Return | Realized volatility | Tail amplitude | Quote-volume proxy p50 |
|---|---|---|---|---|
| 1h | BNB > BTC > ETH > XRP | XRP > ETH > BNB > BTC | XRP > BNB > ETH > BTC | BTC > ETH > XRP > BNB |
| 4h | BNB > BTC > ETH > XRP | XRP > ETH > BNB > BTC | XRP > ETH > BNB > BTC | BTC > ETH > XRP > BNB |

## 1h—4h timeframe coherence

- Exact UTC 1h→4h OHLCV aggregation check across all assets: `true`
- Mean no-tie Kendall rank concordance across four descriptive metrics: `0.916666666667`

| Metric | Exact order match | Kendall tau |
|---|---:|---:|
| annualized_realized_volatility | true | 1.0 |
| cumulative_return | true | 1.0 |
| quote_volume_proxy_p50 | true | 1.0 |
| tail_amplitude_p01_p99 | false | 0.666666666667 |

## Governance conclusion

This artifact is descriptive evidence only. It does not authorize strategy generalization, backtesting, Candidate creation, promotion, or trading.
