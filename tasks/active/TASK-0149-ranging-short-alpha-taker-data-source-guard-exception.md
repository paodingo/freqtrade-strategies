# TASK-0149: Ranging Short Alpha/Taker Data Source Guard Exception

## Status

Completed.

## Objective

Allow only the exact future ranging-short alpha/taker/protection data-source
inventory harness paths reviewed by Task 145.

## Exact Paths

```text
scripts/build_ranging_short_alpha_taker_data_source_inventory.js
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.json
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.md
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
Task 152: Ranging Short Alpha/Taker Data Source Inventory Implementation
```

