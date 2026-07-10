# TASK-0168: V11.31 Longer Replay Data Acquisition Execution Report Guard Exception

## Status

Completed.

## Objective

Allow only the exact future V11.31 longer replay data acquisition execution
report paths reviewed by Task 165.

## Exact Paths

```text
scripts/build_v1131_longer_replay_data_acquisition_execution_report.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.md
```

## Not Allowed

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Next Task

```text
Task 171: V11.31 Longer Replay Data Acquisition Execution Report Implementation
```
