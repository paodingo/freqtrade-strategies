# TASK-0156: V11.31 Longer Replay Data Acquisition Plan Guard Exception

## Status

Completed.

## Objective

Allow only the exact future V11.31 longer replay data acquisition plan paths
reviewed by Task 151.

## Exact Paths

```text
scripts/build_v1131_longer_replay_data_acquisition_plan.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md
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
Task 159: V11.31 Longer Replay Data Acquisition Plan Implementation
```

