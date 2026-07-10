# TASK-0160: Ranging Short Alpha/Taker Source Acquisition Plan Guard Exception

## Status

Completed.

## Objective

Allow only the exact future ranging-short alpha/taker source acquisition plan
paths reviewed by Task 157.

## Exact Paths

```text
scripts/build_ranging_short_alpha_taker_source_acquisition_plan.js
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.json
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.md
```

## Not Allowed

```text
scripts/build_ranging_short_*
reports/ranging_short_research/**
reports/**/*ranging_short*
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Next Task

```text
Task 163: Ranging Short Alpha/Taker Source Acquisition Plan Implementation
```
