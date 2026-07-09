# TASK-0150: V11.30 Live Telemetry Window Guard Exception

## Status

Completed.

## Objective

Allow only the exact future V11.30 live telemetry window report paths reviewed
by Task 146.

## Exact Paths

```text
scripts/build_v1130_live_telemetry_window_report.js
reports/v1130_observation/v1130_live_telemetry_window_report.json
reports/v1130_observation/v1130_live_telemetry_window_report.md
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
Task 153: V11.30 Live Telemetry Window Report Implementation
```

