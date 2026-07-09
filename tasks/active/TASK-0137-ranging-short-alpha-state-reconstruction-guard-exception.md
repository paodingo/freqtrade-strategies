# TASK-0137: Ranging Short Alpha-State Reconstruction Guard Exception

## Status

Completed.

## Objective

Allow only the exact future ranging-short alpha-state reconstruction harness
paths reviewed by Task 134.

## Exact Paths

```text
scripts/build_ranging_short_alpha_state_reconstruction.js
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.json
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.md
```

## Not Allowed

```text
reports/ranging_short_research/**
scripts/build_ranging_short_*
reports/**/*ranging_short*
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Next Task

```text
Task 140: Ranging Short Alpha-State Reconstruction Implementation
```

