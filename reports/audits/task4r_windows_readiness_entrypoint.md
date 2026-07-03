# Task 4R Windows Readiness Entrypoint Report

日期：2026-07-03

工作区：`D:\code\freqtrade-strategies-integration`

## 目标

新增 Windows PowerShell 版 agent readiness 检查入口，避免 Windows 本地执行依赖 WSL 或 Git Bash。

## 变更范围

- 新增 `scripts/run_agent_readiness_checks.ps1`
- 更新 `scripts/guard_harness_diff.js`，仅允许 `scripts/run_agent_readiness_checks.ps1` 作为低风险 harness surface
- 更新 `.github/workflows/agent-readiness.yml`，增加 Windows PowerShell 静态检查 job
- 更新 `docs/harness/change_surface_matrix.md`，说明 Windows 本地优先使用 `.ps1`
- 新增本审计报告和任务记录

## PowerShell 入口行为

`scripts/run_agent_readiness_checks.ps1` 只执行静态检查：

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_no_secret_material.js
node --check scripts/guard_trading_surface.js
node scripts/guard_harness_diff.js
node scripts/guard_no_secret_material.js
node scripts/guard_trading_surface.js
```

任一命令返回非 0，PowerShell 脚本立即以同样的非 0 状态退出。

## 安全边界

本入口不执行：

- Docker
- server 访问
- bot 启动、停止、重启
- 回测
- `.env` 或 `user_data/monitor.env` 读取
- API key、交易所凭证、服务器密钥、dashboard 密码读取

`scripts/run_agent_readiness_checks.sh` 保留，用于 Linux、Git Bash 和 Linux CI。

## Guard 变更说明

`scripts/guard_harness_diff.js` 只新增一条低风险允许规则：

```js
{ path: "scripts/run_agent_readiness_checks.ps1" }
```

未放宽以下阻断：

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- secret 路径
- bot/server/live 操作脚本
- V10.8.2 / V11.29 保护面

## 后续边界

不进入 Task 5。
