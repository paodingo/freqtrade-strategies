# Task 122: V11.31 Replay Coverage Extension Implementation

## Summary

Implemented a read-only V11.31 replay coverage extension generator.

Generated outputs:

```text
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md
```

The generator does not run a backtest, does not modify strategy/config, does not
read secrets, does not access server state, and does not start/stop bots.

## Source Evidence

| source | purpose |
|---|---|
| `reports/v1131_observation/v1131_loose_range_replay_report.json` | alpha-screened V11.31 proxy replay |
| `reports/v1130_observation/v1130_watch_only_telemetry_report.json` | wider OHLCV watch-only layer |
| `reports/v1130_observation/v1130_gate_telemetry_report.json` | strict-gate and sensitivity reference |
| `reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json` | candidate ranking context |

## Key Result

| layer | enabled | status |
|---|---:|---|
| alpha-screened replay | `23` | `thin` |
| OHLCV watch-only layer | `29` | `thin` |
| sensitivity combined-looser reference | `34` | not exact V11.31 thresholds |

The coverage extension does not clear the backtest gate. The alpha-screened
layer remains at `23` enabled samples, and the wider OHLCV-only layer reaches
only `29` while alpha/taker/protection decisions are still unknown.

## Safety Boundary

This task did not:

- run a Freqtrade backtest;
- deploy V11.31;
- modify strategy code;
- modify bot config;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- access server state;
- write SQLite.

## Verification

Required commands:

```text
node --check scripts/build_v1131_loose_range_replay_coverage_extension.js
node scripts/build_v1131_loose_range_replay_coverage_extension.js
.\scripts\run_agent_readiness_checks.ps1
```

## Recommended Next Task

Proceed with:

```text
Task 123: V11.31 Expanded Replay Result Review / Backtest Reconsideration
```

