# TASK-0046: V11.29 Ranging-Short Shadow Deployment Plan

## Status

Completed.

## Objective

Define a safe deployment plan for the Task 45 V11.29 ranging-short shadow lane
without performing any server operation.

## Allowed Files

```text
reports/audits/task46_v1129_ranging_short_shadow_deployment_plan.md
tasks/active/TASK-0046-v1129-ranging-short-shadow-deployment-plan.md
```

## Completed Work

- Defined proposed runtime identity.
- Defined exact server paths.
- Defined pre-start validation checklist.
- Drafted a future copy plan.
- Drafted a future container start command.
- Defined monitoring windows and rollback boundaries.
- Preserved the rule that Task 46 is plan-only.

## Validation

```text
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Next Recommended Task

```text
Task 47: V11.29 Ranging-Short Shadow Server Preflight
```
