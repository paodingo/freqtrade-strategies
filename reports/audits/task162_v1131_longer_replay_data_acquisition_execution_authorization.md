# Task 162: V11.31 Longer Replay Data Acquisition Execution Authorization

## Summary

Reviewed the Task 159 plan-only artifact and authorized a future bounded data
acquisition execution task for V11.31 longer replay evidence. This task does not
connect to the server, acquire data, run backtests, modify strategy/config files,
or start/stop bots.

Decision:

```text
authorize_future_bounded_read_only_data_acquisition_execution
```

## Sources Reviewed

```text
reports/audits/task159_v1131_longer_replay_data_acquisition_plan_implementation.md
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md
```

## Current Evidence State

| field | state |
|---|---|
| approved pair set | `ETH`, `SOL`, `DOGE`, `LINK`, `XRP`, `BCH` |
| observed 15m source rows per pair | `88271` |
| committed replay rows per pair | `240` |
| committed replay days per pair | `2.5` |
| 7d / 14d committed replay support | `false` |
| 4h row-level source path | `unknown` |
| alpha/taker/protection evidence | `missing` / `unknown` |

## Authorized Future Execution Scope

A future task may perform only bounded, read-only data acquisition needed to
turn the current plan into explicit evidence:

- locate approved 15m source files for the exact approved pair set;
- locate aligned 4h informative source files for the exact approved pair set;
- record file existence, size, mtime, and row-count/window metadata;
- copy or generate bounded evidence artifacts only if a later task explicitly
  authorizes the exact target paths;
- keep missing alpha/taker/protection fields marked `missing` or `unknown`
  unless non-secret evidence proves otherwise.

## Explicitly Not Authorized

The future task is not authorized to:

- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- modify `strategies/**`, `user_data/**`, `configs/**`, `dashboard/**`, or
  `deploy/**`;
- start, stop, restart, or deploy any bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- refresh/download broad market data outside an explicitly approved source;
- widen the approved pair set;
- claim V11.31 profitability, stability, deployability, or replacement fitness.

## Stop Conditions For Future Execution

The future task must stop if:

- the worktree is dirty before execution;
- readiness checks fail;
- exact output paths are not pre-authorized by guard review;
- server/source evidence would require reading secrets;
- a command would write to live bot data, strategy files, config files, dashboard
  files, or deploy files.

## Recommended Next Task

Proceed with:

```text
Task 165: V11.31 Longer Replay Data Acquisition Execution Path Review
```

