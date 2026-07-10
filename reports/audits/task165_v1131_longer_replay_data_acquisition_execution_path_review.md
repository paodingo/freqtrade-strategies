# Task 165: V11.31 Longer Replay Data Acquisition Execution Path Review

## Summary

Reviewed Task 162 and approved only exact future artifact paths for a bounded
V11.31 longer replay data acquisition execution report. This task does not
connect to the server, acquire data, copy data, run backtests, modify strategy or
config files, or start/stop bots.

Decision:

```text
exact_future_paths_approved_for_acquisition_execution_artifacts_only
```

## Source Reviewed

```text
reports/audits/task162_v1131_longer_replay_data_acquisition_execution_authorization.md
```

## Approved Future Paths

Only these exact future paths are approved for a later guard exception:

```text
scripts/build_v1131_longer_replay_data_acquisition_execution_report.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.md
```

## Not Approved

The review does not approve:

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
.env
user_data/monitor.env
```

## Future Execution Boundaries

A later execution task still requires a separate guard exception and must remain
bounded to read-only evidence. It may not read secrets, widen the approved pair
set, refresh broad market data, run backtests, modify live bot data, or make
profitability/deployment claims.

## Recommended Next Task

Proceed with:

```text
Task 168: V11.31 Longer Replay Data Acquisition Execution Report Guard Exception
```

