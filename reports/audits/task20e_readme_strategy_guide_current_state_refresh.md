# Task 20E: README and Strategy Guide Current-State Refresh

状态：已完成。只更新 `README.md` 和 `STRATEGY_GUIDE.md` 的当前状态叙述，未修改 deploy/live 文档、策略、配置或服务器操作面。

## Summary

本任务承接 Task 20D 的文档时效审计，将入口文档中“V6.5 / V6.6 是当前主线”的过期叙事改为“V11.29 正在真实执行验证，但当前 evidence 为 `insufficient`”。同时保留 V6.5 / V6.6 作为历史版本说明。

本任务没有声称 V11.29 已通过真实执行验证，也没有声称 V11.29 可以替换 V10.8.2。

## Files changed

- `README.md`
- `STRATEGY_GUIDE.md`
- `scripts/guard_harness_diff.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task20e_readme_strategy_guide_current_state_refresh.md`
- `tasks/active/TASK-0020E-readme-strategy-guide-current-state-refresh.md`

## README changes

- 将仓库当前重点改为 clean harness + V11.29 真实执行验证准备。
- 明确 V11.29 当前为 `validation insufficient`。
- 明确 V11.29 snapshot 中 `trades = 0`、`orders = 0`。
- 将 V6.5 / V6.6 标记为 historical。
- 删除旧的“启动当前 V6.5 dry-run bot”叙述。
- 明确 `DEPLOY.md` / `LIVE_TRADING.md` 仍是高风险旧文档，不能作为当前 V11.29 操作手册。

## STRATEGY_GUIDE changes

- 将“当前目标”从 V6.5 / V6.6 双 bot 对比改为 V11.29 真实执行验证链路。
- 保留 V6.5 / V6.6 历史策略解释。
- 增加 V11.29 当前 insufficient 状态和后续观察指标。
- 明确没有真实 trades/orders 前，不能计算 winrate、PF、slippage、fee quality、latency quality。
- 明确不能把缺失字段写成 `0`，应保持 `missing`、`unknown` 或 `insufficient`。

## Guard update

`scripts/guard_harness_diff.js` 增加了一个精确低风险文档例外：

```text
STRATEGY_GUIDE.md
```

这不是通配规则，不允许 `docs/**`、`strategies/**`、`user_data/**`、`configs/**`、`dashboard/**` 或 `deploy/**`。

## Explicit non-goals

本任务没有：

- 修改 `DEPLOY.md`
- 修改 `LIVE_TRADING.md`
- 修改 `strategies/**`
- 修改 `user_data/**`
- 修改 `configs/**`
- 修改 `dashboard/**`
- 修改 `deploy/**`
- 读取 `.env` 或 `user_data/monitor.env`
- 启动、停止、重启 bot
- 登录服务器
- 运行回测
- 生成 V11.29 替换结论

## Remaining stale docs

仍需单独处理：

- `DEPLOY.md`
- `LIVE_TRADING.md`

这两个文档包含运行、部署、live 或 server 操作面内容，应先做 historical freeze / split plan，不应直接改写成 V11.29 可执行操作手册。

## Recommended next tasks

1. Task 20F: `Deploy and Live Docs Historical Freeze Plan`
   - 只生成计划，决定 `DEPLOY.md` / `LIVE_TRADING.md` 应标记 historical、拆分，还是人工授权后重写。

2. Task 20: `V11.29 Data Coverage and Runtime Performance Audit`
   - 技术主线任务，继续调查 zero-trade 的数据覆盖和运行性能原因。

## Verification

最终验证命令：

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

预期最终可见变更：

```text
README.md
STRATEGY_GUIDE.md
scripts/guard_harness_diff.js
docs/harness/change_surface_matrix.md
reports/audits/task20e_readme_strategy_guide_current_state_refresh.md
tasks/active/TASK-0020E-readme-strategy-guide-current-state-refresh.md
```
