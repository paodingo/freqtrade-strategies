# TASK-0161: V11.30 Live Telemetry Server Collection Plan Guard Exception

## Status

Completed.

## Objective

Allow only the exact future V11.30 live telemetry server collection plan paths
reviewed by Task 158.

## Exact Paths

```text
scripts/build_v1130_live_telemetry_server_collection_plan.js
reports/v1130_observation/v1130_live_telemetry_server_collection_plan.json
reports/v1130_observation/v1130_live_telemetry_server_collection_plan.md
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
Task 164: V11.30 Live Telemetry Server Collection Plan Implementation
```
