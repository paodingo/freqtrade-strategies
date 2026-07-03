# Task 5: Clean Harnessed Development Base

结论：`D:\code\freqtrade-strategies-clean` 可以作为后续正式开发目录，替代原始脏工作区继续开发。当前 clean worktree 满足分支、干净状态和 PowerShell readiness gate。

## 1. 当前目录、分支、commit

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 当前 commit：`a79ca095aca6ec431444184e2b69c36dd9084529`

## 2. `git status --short` 结果

前置检查时输出为空：

```text

```

判断：工作区干净，符合 Task 5 前置条件。

## 3. PowerShell readiness check 结果

执行命令：

```powershell
.\scripts\run_agent_readiness_checks.ps1
```

结果：

```text
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

判断：PowerShell 入口可在本机 Windows 环境执行，且当前 clean base 在无改动状态下通过全部静态 guard。

## 4. 当前 harness 已包含的能力

- `scripts/run_agent_readiness_checks.ps1`：Windows PowerShell readiness 入口，执行 `node --check` 和运行态 guard 检查。
- `scripts/run_agent_readiness_checks.sh`：Linux、Git Bash、CI 可用的 readiness 入口。
- `scripts/guard_harness_diff.js`：限制 agent diff 只能落在低风险 harness、文档、任务、审计和 guard 文件面；默认阻断策略、bot 配置、runtime、dashboard、deploy、V11.29 报告面和 secret-adjacent 路径。
- `scripts/guard_no_secret_material.js`：阻断 `.env`、`user_data/monitor.env`、key material 路径，并扫描变更文件中的常见 secret material 模式。
- `scripts/guard_trading_surface.js`：默认阻断 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`、bot lifecycle 脚本、server health/trade monitor 脚本、V10.8.2/V11.29 相关路径和 secret env 路径。
- `.github/workflows/agent-readiness.yml`：提供 CI 侧静态 readiness 检查。
- `docs/harness/change_surface_matrix.md`、`tasks/**`、`reports/audits/**`：提供变更面边界、任务约束和审计记录载体。

## 5. 原始脏工作区仍然不应自动清理的原因

原始工作区 `D:\code\freqtrade-strategies` 仍应作为人工证据来源，而不是自动清理对象。原因：

- 其中可能混有策略、bot 配置、runtime 数据、dashboard、deploy、server 操作脚本、V10.8.2/V11.29 相关材料和 secret-adjacent 路径。
- 自动 `git add -A`、stash、删除、移动、格式化或清理都可能改变证据边界，误纳入交易行为或运行面改动。
- 对旧目录的任何处理都需要人工按文件来源和风险分级迁移，不能由 clean base 的后续开发任务隐式吸收。
- 当前 Task 5 的目标是确认 clean base 可用，不是修复、整理或归档原始脏工作区。

## 6. 后续工作建议

- 新开发默认进入 `D:\code\freqtrade-strategies-clean`。
- 每个新任务先确认目录、分支、`git status --short` 和 readiness gate。
- 旧目录 `D:\code\freqtrade-strategies` 只做人工挑选后的证据迁移；迁移前必须明确文件清单、风险分类和允许变更面。
- 后续 agent 不应自动读取或修改 `.env`、`user_data/monitor.env`、bot 配置、策略、dashboard、deploy、V10.8.2/V11.29 或 live/server 操作面。

## 7. 下一步 Task 6 推荐

推荐 Task 6：在 clean worktree 中创建第一个正式开发任务的受控任务单，明确允许修改路径、禁止触碰交易/runtime/server/secret 面，并以 `.\scripts\run_agent_readiness_checks.ps1` 作为进入和完成 gate。

Task 6 不应从旧脏工作区自动搬运文件；如需引用旧目录，只能由人工先给出明确证据文件清单。
