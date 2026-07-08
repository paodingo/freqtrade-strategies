# TASK-0073: V11.30 Data Maintenance Plan For Stale Local Feather Files

## Status

Completed.

## Objective

Define a safe plan to handle stale local feather files without immediately
downloading data or touching the running bot surface.

## Result

- Existing `scripts/refresh_data.sh` was identified as unsafe for direct V11.30
  use because it is hard-coded to an old V6.5 config.
- A future exact-command data refresh task was proposed.
- This task did not update market data.

## Boundary

No data files were modified, no bot was restarted, no strategy/config was
changed, and no secret was read.

## Output

- `reports/audits/task73_v1130_data_maintenance_plan_for_stale_local_feather_files.md`

## Next

Proceed to Task 74: V11.30 signal telemetry persistence design.
