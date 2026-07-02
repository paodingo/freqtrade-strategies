# Agent Tasks

This directory holds task briefs for harness-only agent work. The default rule is
to keep agents away from strategy behavior, bot configuration, server operations,
deployment files, dashboard runtime surfaces, and secret material unless a human
explicitly opens a separate task for that surface.

Use `tasks/templates/agent_task.md` for new briefs. Each task should state:

- allowed files and directories
- blocked files and directories
- whether server access is allowed
- whether bot lifecycle commands are allowed
- required static checks before handoff

For the default harness workflow, run:

```bash
bash scripts/run_agent_readiness_checks.sh
```

Guard exit codes are shared across the Node scripts:

- `0`: pass
- `1`: blocked high-risk diff
- `2`: tool or configuration error
