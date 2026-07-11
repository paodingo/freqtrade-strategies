# Stage 3C.2-P Runtime Data Contract

- Runtime ID: `local-freqtrade-2025-8`
- Expected Python: `3.12`
- Expected Freqtrade: `2025.8`
- Version command exit code: `0`
- Trading mode: `futures`
- Margin mode: `isolated`
- API key empty: `true`
- API secret empty: `true`
- `download-data` supports `--trading-mode`: `true`
- `download-data` supports `--candle-types`: `false`

## Required Data

- Primary timeframe: `1h`
- Informative timeframe: `4h`
- Candle types required for research: `futures`, `mark`, `funding_rate`
- Funding timeframe: `8h`
- Data format: `feather`

## Contract Note

Freqtrade 2025.8 is the authority for this repository. Its `download-data` CLI does not expose `--candle-types`, so this stage does not pass that unsupported flag.
