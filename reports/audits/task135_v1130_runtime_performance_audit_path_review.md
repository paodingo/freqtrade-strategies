# Task 135: V11.30 Runtime Performance Audit Exact Path Review

## Summary

Reviewed the future path surface proposed by Task 132 for a telemetry-only
V11.30 runtime performance audit.

Decision:

```text
approve_exact_paths_only_for_future_guard_exception
```

This review does not access the server, does not inspect live logs, does not
restart bots, and does not modify strategy or bot config files.

## Source Reviewed

```text
reports/audits/task132_v1130_instrumented_runtime_performance_audit_plan.md
```

## Approved Future Exact Paths

Only these exact paths should be considered for a later guard exception task:

```text
scripts/build_v1130_runtime_performance_audit.js
reports/v1130_observation/v1130_runtime_performance_audit.json
reports/v1130_observation/v1130_runtime_performance_audit.md
```

## Explicitly Not Approved

Do not approve broad patterns such as:

```text
scripts/build_v1130_*
reports/v1130_observation/**
reports/**/*v1130*
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

A future guard exception must:

- allow only the three exact paths listed above;
- avoid broad directory or wildcard rules;
- keep strategy/config/dashboard/deploy surfaces blocked;
- keep secrets blocked;
- keep bot start/stop/restart forbidden unless separately authorized;
- keep the performance audit telemetry-only.

## Recommended Next Task

Proceed with:

```text
Task 138: V11.30 Runtime Performance Audit Guard Exception
```

