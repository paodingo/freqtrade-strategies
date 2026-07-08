# Task 94: Market Data Freshness Continuous Audit

## Summary

Audited current V11.30 market data freshness using read-only server checks.

Conclusion:

```text
market_data_content_stale
```

The feather files have recent mtimes, but the latest candle content remains
behind server time.

## Read-Only Observation

Server-side observation time:

```text
2026-07-08T09:38:15Z
```

Checked pairs:

- `ETH`
- `SOL`
- `DOGE`
- `LINK`
- `XRP`
- `BCH`

## 15m Freshness

All six checked 15m futures feather files have latest candle:

```text
2026-07-08T06:15:00+00:00
```

At observation time, this is more than three hours behind expected current
15m candle availability.

## 4h Freshness

All six checked 4h futures feather files have latest candle:

```text
2026-07-08T00:00:00+00:00
```

This may be expected for a closed 4h candle depending on exchange close timing,
but the 15m gap is already enough to mark current data freshness as degraded.

## Important Distinction

File `mtime` is recent, but candle content is stale.

That means a refresh process may have touched or rewrote the files without
actually extending the data to current candles.

## Impact

V11.30 zero-trade diagnosis is currently distorted by stale market data:

- latest gate checks may not reflect current market action;
- live strategy may be analyzing old candles;
- watch-only opportunities in the report may be historical, not current.

## What Was Not Done

This task did not:

- run `freqtrade download-data`;
- run `scripts/refresh_data.sh`;
- modify data files;
- modify bot config;
- restart containers;
- run a backtest.

## Recommended Follow-Up

Proceed with a dedicated safe data refresh task:

```text
Task 94R: V11.30 market data refresh pipeline diagnosis and safe refresh plan
```

That task should inspect the refresh command and logs, then propose the minimum
safe correction. It should not directly change live strategy behavior.
