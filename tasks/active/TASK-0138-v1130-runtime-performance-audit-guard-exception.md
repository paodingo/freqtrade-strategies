# TASK-0138: V11.30 Runtime Performance Audit Guard Exception

## Status

Completed.

## Objective

Allow only the exact future V11.30 runtime performance audit harness paths
reviewed by Task 135.

## Exact Paths

```text
scripts/build_v1130_runtime_performance_audit.js
reports/v1130_observation/v1130_runtime_performance_audit.json
reports/v1130_observation/v1130_runtime_performance_audit.md
```

## Not Allowed

```text
scripts/build_v1130_*
reports/v1130_observation/**
reports/**/*v1130*
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Next Task

```text
Task 141: V11.30 Runtime Performance Audit Implementation
```

