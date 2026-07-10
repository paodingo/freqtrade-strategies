# Task 174: V11.31 Longer Replay Data Acquisition Execution Authorization With Exact Output Paths

## Summary

Defined the exact future output paths for a real V11.31 longer replay data
acquisition execution task. This task does not connect to the server, acquire
data, copy files, run backtests, modify strategy/config files, or start/stop
bots.

Decision:

```text
authorize_future_execution_only_after_exact_output_path_guard_review
```

## Sources Reviewed

```text
reports/audits/task171_v1131_longer_replay_data_acquisition_execution_report_implementation.md
reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.md
```

## Exact Future Output Paths To Review

Only these future paths should be considered for a later guard exception:

```text
scripts/build_v1131_longer_replay_data_acquisition_actual_execution_report.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.md
```

## Exact Future Evidence Fields

A future real execution task may report only bounded read-only evidence:

- approved-pair 15m source existence, size, mtime, row count, and time range;
- approved-pair 4h source existence, size, mtime, row count, and time range;
- whether aligned 7d and 14d windows can be derived;
- whether alpha/taker/protection timelines remain `missing`, `unknown`, or are
  supported by non-secret evidence;
- whether a later replay gate review can consider backtest authorization.

## Explicitly Not Authorized

The future task is not authorized to:

- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- modify `strategies/**`, `user_data/**`, `configs/**`, `dashboard/**`, or
  `deploy/**`;
- write source data or SQLite data;
- start, stop, restart, or deploy any bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- widen the approved pair set;
- claim V11.31 profitability, deployability, or replacement fitness.

## Stop Conditions For Future Execution

The future task must stop if:

- exact output paths are not pre-authorized by guard review;
- readiness checks fail;
- server/source evidence would require reading secrets;
- a command would write live bot data, strategy/config/dashboard/deploy files,
  SQLite data, or source market data;
- a command would start, stop, restart, or deploy a bot.

## Recommended Next Task

Proceed with:

```text
Task 177: V11.31 Actual Data Acquisition Execution Report Path Review
```

