# Task ID Registry

## Canonical numbering

- `TASK-0001` through `TASK-0189` are reserved for the operational task series under `tasks/active/`.
- Research audit labels historically written as `Task 187`, `Task 188`, and `Task 189` are canonicalized as `Research R187`, `Research R188`, and `Research R189`.
- Historical research audit filenames are preserved to avoid breaking evidence links; their numeric labels are not reusable operational task IDs.
- New repository-wide work starts at `TASK-0190` and increments monotonically.

## Current assignments

| ID | Scope | Status |
|---|---|---|
| `TASK-0190` | Research batch closure, feedback review, rejected Candidate registration, and state refresh | completed |
| `TASK-0191` | BNB/XRP Development-only funding/mark stress profile | completed |
| `TASK-0192` | Freeze non-critical expansion and establish one authoritative paper lane | completed |
| `TASK-0193` | Remediate V11.30 runtime identity, reliability telemetry, and 24-hour acceptance | in progress |

## Governance rule

Before adding a task, check both `tasks/active/` and this registry. Research report labels must use the `Research RNNN` namespace and must not claim an operational `TASK-NNNN` ID.
