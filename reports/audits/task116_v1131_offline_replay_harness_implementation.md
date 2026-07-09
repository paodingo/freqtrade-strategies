# Task 116: V11.31 Offline Replay Harness Implementation

## Summary

Implemented and ran the V11.31 offline replay harness.

Conclusion:

```text
v1131_replay_generated_positive_proxy_but_sample_thin
```

This task generated a read-only replay-planning report. It did not run a
Freqtrade backtest, did not deploy V11.31, did not start/restart bots, did not
modify strategy/config files, and did not read secrets.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `3f1b7ed` |
| starting status | clean |
| readiness before implementation | passed |
| guard approval | Task 115 |

## Files Created

```text
scripts/build_v1131_loose_range_replay_report.js
reports/v1131_observation/v1131_loose_range_replay_report.json
reports/v1131_observation/v1131_loose_range_replay_report.md
```

## Data Sources

The harness reads existing local evidence only:

```text
reports/v1130_observation/v1130_loose_range_replay_report.json
strategies/RegimeAwareV1131LooseRangeWatchShadow.py
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
```

It reuses the V11.30 loose-range replay evidence because V11.31 implements the
same loose-range entry thresholds as a local shadow strategy.

## Data Gate

| item | status |
|---|---|
| `15m` | used |
| `4h` | used as inherited context |
| `1h` | `excluded_stale` |
| backtest | not run |
| server operation | not run |

## Replay Result

Counts:

| metric | count |
|---|---:|
| candidates | `29` |
| enabled | `23` |
| blocked | `6` |
| blocked by taker sell pressure | `6` |
| blocked by alpha short | `0` |

Forward returns:

| horizon | samples | mean bps | median bps | win rate |
|---|---:|---:|---:|---:|
| `1_candle` | `23` | `-1.88` | `-5.47` | `0.3913` |
| `4_candle` | `23` | `20.15` | `38.09` | `0.7391` |
| `8_candle` | `23` | `34.13` | `51.09` | `0.5652` |
| `16_candle` | `23` | `16.69` | `-17.67` | `0.4348` |

Fee-adjusted forward returns using `10 bps`:

| horizon | samples | mean bps | median bps |
|---|---:|---:|---:|
| `1_candle` | `23` | `-11.88` | `-15.47` |
| `4_candle` | `23` | `10.15` | `28.09` |
| `8_candle` | `23` | `24.13` | `41.09` |
| `16_candle` | `23` | `6.69` | `-27.67` |

Pair concentration:

```text
max_pair_share = 0.2609
```

Sample status:

```text
thin
```

Reason:

```text
enabled sample count 23 is below the initial gate 30
```

## What This Proves

This proves:

- the V11.31 replay report can be generated from committed evidence;
- the candidate retains positive 4/8 candle fee-adjusted proxy returns;
- pair concentration is not single-pair dominated in the replay evidence;
- stale `1h` was excluded.

## What This Does Not Prove

This does not prove:

- Freqtrade backtest profitability;
- live/dry-run execution quality;
- fill quality, slippage, funding, or latency;
- exit distribution under real strategy lifecycle;
- V11.31 deployment readiness;
- V11.31 replacement readiness.

## Validation Commands

Run:

```text
node --check scripts/build_v1131_loose_range_replay_report.js
node scripts/build_v1131_loose_range_replay_report.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Safety Boundary

This task did not:

- run backtests;
- deploy V11.31;
- start, stop, or restart bots;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- refresh or download data;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- force-close trades;
- produce a replacement conclusion.

## Recommended Next Task

Proceed with:

```text
Task 117: V11.31 Replay Result Review / Backtest Go-No-Go
```

