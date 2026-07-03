# TASK-0004R Windows Readiness Entrypoint

状态：已新增 Windows PowerShell readiness 入口，未进入 Task 5。

当前工作区：`D:\code\freqtrade-strategies-integration`

## 已修改文件

- `scripts/run_agent_readiness_checks.ps1`
- `scripts/guard_harness_diff.js`
- `.github/workflows/agent-readiness.yml`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task4r_windows_readiness_entrypoint.md`
- `tasks/active/TASK-0004R-windows-readiness-entrypoint.md`

## 行为

PowerShell 入口只运行 Node 静态检查和三个 guard 脚本。任一命令失败时，脚本退出非 0。

## 未执行动作

- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未修改策略
- 未修改 bot 配置
- 未修改 `user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`
- 未读取 `.env`、`user_data/monitor.env` 或 secret
- 未启动、停止、重启 bot
- 未登录服务器
- 未运行回测
- 未修改 V10.8.2 或 V11.29
- 未进入 Task 5
