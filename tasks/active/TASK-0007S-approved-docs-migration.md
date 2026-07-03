# TASK-0007S: Extend Narrow Docs Allowlist And Migrate Approved Docs

状态：已完成，未进入 Task 8。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

根据 `reports/audits/task7r_blocked_docs_review.md`，只迁移 Task 7R 明确建议迁移的 4 个 `docs/*` 文件，并对 `guard_harness_diff.js` 做精确路径白名单扩展。

## 前置条件结果

- Task 7R：通过，commit `486df3d Review blocked A-class docs`
- `git status --short`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过
- 已先读取 `reports/audits/task7r_blocked_docs_review.md`

## 实际迁移

- `docs/agent_operating_playbook.md`
- `docs/agent_operating_playbook.html`
- `docs/opensource_reference_audit.md`
- `docs/验收报告格式.md`

## guard 变更

`scripts/guard_harness_diff.js` 只新增上述 4 个精确 docs 路径；未新增 `docs/**`、`docs/*.md` 或 `docs/*.html` 泛化规则。

## 文档变更

`docs/harness/change_surface_matrix.md` 已记录 Task 7S 的精确 docs 白名单。

## 本任务未执行

- 未修改 `strategies/**`
- 未修改 `user_data/**`
- 未修改 `configs/**`
- 未修改 `dashboard/**`
- 未修改 `deploy/**`
- 未修改 `.env`
- 未修改 `user_data/monitor.env`
- 未读取 API key、交易所凭证、服务器密钥、dashboard 密码
- 未触碰 V10.8.2、V11.29、live/server 操作面
- 未删除或移动原始工作区文件
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略或 bot 配置
- 未进入 Task 8

## 输出

- `reports/audits/task7s_approved_docs_migration.md`
