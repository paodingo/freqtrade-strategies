# Task 151: V11.31 Longer Replay Data Acquisition Exact Path Review

## Summary

Reviewed the future exact path surface for a V11.31 longer replay data
acquisition plan artifact.

Decision:

```text
approve_exact_paths_only_for_future_guard_exception
```

This task does not execute acquisition, access the server, copy files, download
data, run a backtest, or modify strategy/config files.

## Source Reviewed

```text
reports/audits/task148_v1131_longer_replay_data_acquisition_authorization.md
```

## Approved Future Exact Paths

Only these exact paths should be considered for a later guard exception task:

```text
scripts/build_v1131_longer_replay_data_acquisition_plan.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md
```

## Explicitly Not Approved

Do not approve broad patterns such as:

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
```

Do not approve changes under:

```text
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Required Future Guard Rules

A future guard exception must allow only the three exact paths above and keep
strategy/config/dashboard/deploy/server/secret/backtest surfaces blocked.

## Recommended Next Task

Proceed with:

```text
Task 156: V11.31 Longer Replay Data Acquisition Plan Guard Exception
```

