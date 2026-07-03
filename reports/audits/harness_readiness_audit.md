# Agent-Ready Repository 改造审计

审计日期：2026-07-02  
审计范围：`D:\code\freqtrade-strategies` 本地仓库结构、文档、脚本、测试、报告与 CI/harness 缺口  
执行边界：Task 0 只读分析为主；除本报告外不修改业务逻辑、策略参数、bot 配置、dry-run/live 配置、凭证或服务器状态。

## 结论摘要

当前仓库已经有比较强的“操作纪律”基础：存在 `AGENTS.md`、`docs/agent_operating_playbook.md`、大量脚本、Node/Python 测试、运行健康检查、报告目录和 V11/V10.8.2 对照证据。

距离 harness engineering / agent-ready repository 的主要差距不是缺少脚本，而是缺少机器可执行的默认护栏：

| 维度 | 当前状态 | 缺口 |
| --- | --- | --- |
| agent 入口 | 有 `AGENTS.md`，并有 playbook | `AGENTS.md` 当前为未跟踪文件；README 仍是旧 V6/V6.7 叙事，入口存在冲突 |
| 任务结构 | 有 `docs/superpowers/plans` 和 specs | 无 `tasks/`、任务模板、变更表面声明、停止条件模板 |
| 本地 gate | 有 `scripts/run_tests.sh`、`scripts/check_system_health.sh`、多类 validator | 无专门的 agent diff guard，不能默认阻止策略/配置/凭证类误改 |
| CI | 未发现 `.github/workflows` | 无 PR/push 自动检查，guard 不能在提交前或 PR 中强制执行 |
| 报告沉淀 | 有大量 `reports/` | 本审计前无 `reports/audits/`；缺少固定审计报告入口 |
| 高风险目录 | `strategies/`、`user_data/`、`dashboard/`、server 脚本非常活跃 | 缺少“默认禁止修改”清单的机器校验 |

推荐最小 Task 1：只新增 harness 护栏与 CI skeleton，不触碰策略、参数、bot 配置、dry-run/live 配置或服务器。

## 当前仓库结构概览

本地扫描结果显示：

| 路径 | 数量/状态 | 作用 | agent-ready 评价 |
| --- | ---: | --- | --- |
| `AGENTS.md` | 存在，git 显示未跟踪 | agent 操作规则入口 | 内容方向正确，但需要纳入版本控制并补充机器护栏引用 |
| `README.md` | 存在，git 显示已修改 | 人类入口文档 | 仍描述 V6/V6.7，和当前 V11/V10.8.2 拓扑冲突 |
| `docs/` | 41 个文件 | playbook、架构、计划、规格、HTML 阅读版 | 可复用，但缺 harness 专区和任务模板 |
| `tasks/` | 不存在 | 任务分解与验收模板 | 缺失 |
| `scripts/` | 53 个文件 | 启动、刷新、健康检查、报告、回测、验收 | 资产丰富，但缺 agent 默认 diff guard |
| `tests/` | 63 个文件 | Node 测试、Python 测试、btc_system 测试 | 覆盖较多，但没有 CI 统一入口 |
| `reports/` | 921 个文件 | 回测、验收、运行证据 | 证据充分；本审计前无 `reports/audits/` |
| `.github/workflows` | 不存在 | CI | 缺失 |
| `dashboard/` | 16 个文件 | 监控服务与前端 | 高风险，已有部分静态/行为测试 |
| `strategies/` | 94 个文件 | Freqtrade 策略版本 | 高风险，默认不应由 agent 触碰 |
| `user_data/` | 120 个文件 | bot 配置、数据、SQLite、回测结果 | 极高风险，默认不应由 agent 触碰 |
| `btc_system/` | 34 个文件 | 自研 BTC 系统模块 | 中高风险，需测试驱动 |
| `deploy/` | 1 个文件 | systemd 服务 | 高风险，server 状态相关 |
| `.gitignore` | 存在 | 忽略 live config、sqlite、monitor env 等 | 基础正确，但不等于修改护栏 |

工作区状态风险：`git status --short` 有 262 条记录，说明当前本地仓库有大量未提交/未跟踪内容。agent-ready 的下一步应先用 guard 和任务模板约束“可以改什么”，而不是直接重排或清理工作区。

## 现有可复用脚本

| 脚本 | 可复用点 | 注意事项 |
| --- | --- | --- |
| `scripts/run_tests.sh` | 本地生产烟测入口；执行 Node syntax check、Node tests、`format_trade_alert.py` 编译和 Freqtrade Docker unittest | 依赖 Docker 与 `freqtradeorg/freqtrade:stable`，CI 可先拆出 static subset |
| `scripts/check_system_health.sh` | server/runtime 健康 gate；检查 Docker、API、dashboard summary、alpha-risk、regime-router、trade-supervisor、closed-loop report | 会读取 `user_data/monitor.env` 路径但不 source；运行时会访问本机服务，CI 不应默认执行 |
| `scripts/ensure_dry_run_bots_started.sh` | 确保 dry-run 容器与 trader state 为 running | 会启动容器和调用 `/api/v1/start`，agent 默认不能运行 |
| `scripts/refresh_data.sh` | 数据刷新、dry-run autostart、V11 closed-loop、system health、acceptance、live readiness、opportunity audit 串联 | 会操作 Docker/bot 状态，不能作为默认只读检查 |
| `scripts/check_trades.sh` | 交易告警状态采集，区分 API 异常、bot state、持仓变化 | 会读取/写入 `user_data/trade_monitor_state.json`，只应在 incident 任务中使用 |
| `scripts/format_trade_alert.py` | 告警格式化，已有测试覆盖 | 可纳入静态/单元测试 gate |
| `scripts/preflight_live.sh` | live config 启动前预检，检查 dry_run、API 绑定、密钥占位、stoploss on exchange 等 | 只用于实盘前检查；Task 1 不应触碰 live config |
| `scripts/validate_trading_system_acceptance.js` | 历史/配置验收 gate | 当前脚本内部仍含较多旧 V9.7 语义，适合后续单独审计，不应在 Task 1 修改业务逻辑 |
| `scripts/validate_live_readiness.js` | live readiness gate | 可作为 read-only validator 复用 |
| `scripts/validate_opportunity_audit.js` | opportunity audit gate | 可作为 read-only validator 复用 |
| `scripts/build_v11_closed_loop_report.js` | V11.29 真实执行闭环报告 | 高风险：涉及 V11.29 叙事和 dashboard auth，不应在 Task 1 修改 |
| `scripts/run_v11_high_attack_backtests.sh` | V10.8.2 vs V11.x 回测入口 | 研究脚本，成本高，不适合 CI 默认运行 |
| `scripts/run_v1129_residual_drag_micro_sizer_backtests.sh` | V11.29 isolated 回测脚本 | 用户明确要求本轮不改 V11.29 |
| `scripts/record_*.js` | 将 acceptance/readiness/opportunity/system_health 写入 monitor store | 可作为报告链路的一部分，Task 1 不应变更 |

## 缺失的 harness 文件

| 缺失文件/目录 | 建议优先级 | 建议作用 |
| --- | --- | --- |
| `.github/workflows/agent-readiness.yml` | P0 | PR/push 静态检查、guard 检查、Node/Python syntax tests |
| `scripts/guard_harness_diff.js` | P0 | 根据 `git diff --name-status` 阻止默认改动高风险路径 |
| `scripts/guard_no_secret_material.js` | P0 | 扫描 diff 中的 secret-like 内容，禁止提交 `.env`、key、token、password 值 |
| `scripts/guard_trading_surface.js` | P0 | 阻止策略参数、`user_data/config*.json`、dry_run/live、stake/leverage/ROI/stoploss/pairlist 的默认变更 |
| `scripts/run_agent_readiness_checks.sh` | P0 | 本地/CI 统一入口，只运行安全静态检查，不启动 bot |
| `tasks/README.md` | P1 | 说明任务如何声明 scope、允许修改面、停止条件 |
| `tasks/templates/agent_task.md` | P1 | 新任务模板：目标、禁改范围、允许文件、验证命令、server 是否涉及 |
| `docs/harness/change_surface_matrix.md` | P1 | 将文件路径分为 safe/edit-with-approval/forbidden |
| `docs/harness/ci_checks.md` | P1 | 记录 CI gate 设计与不能覆盖的 server/runtime gate |
| `CODEOWNERS` | P2 | 对 `strategies/`、`user_data/`、`dashboard/`、`scripts/start*` 等路径增加审阅人 |
| `.pre-commit-config.yaml` | P2 | 本地提交前 guard；可后置，避免先引入工具链负担 |
| `docs/harness/agent_ready_scorecard.md` | P2 | 长期评分，不作为 Task 1 必需 |

## 高风险文件和目录

| 路径 | 风险原因 | 默认动作 |
| --- | --- | --- |
| `strategies/` | 直接改变交易行为、信号、仓位、止损、ROI、保护逻辑 | 默认禁止修改 |
| `strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py` | V10.8.2 benchmark，用户明确要求不改 | 禁止修改 |
| `strategies/RegimeAwareV1116SelectiveAltRecoverySizer.py` | 当前 V11 dry-run candidate | 禁止默认修改 |
| `strategies/RegimeAwareV1129ResidualDragMicroSizer.py` | V11.29 scout/闭环报告相关，用户明确要求不改 | 禁止修改 |
| `user_data/config_*.json` | bot_name、port、stake、pairlist、dry_run、db_url、API server 等运行配置 | 默认禁止修改 |
| `user_data/config_multi_futures_v1082.json` | V10.8.2 benchmark 配置 | 禁止修改 |
| `user_data/config_multi_futures_v1116.json` | 当前 V11 candidate 配置 | 禁止默认修改 |
| `user_data/config_multi_futures_v1129.json` | V11.29 配置 | 禁止修改 |
| `user_data/*live*.json` | live config 示例或真实配置相邻路径 | 默认禁止修改；真实 live config 禁止读取内容 |
| `user_data/*.sqlite`, `user_data/data/`, `user_data/backtest_results/` | 运行/回测数据，可能很大且可被误删 | 默认只读，不清理 |
| `user_data/monitor.env` | dashboard/API 凭证环境 | 禁止读取和修改 |
| `.env`, `*.pem`, `*.key`, `*.secret` | 密钥/凭证 | 禁止读取、修改、打印 |
| `scripts/start_bot.sh` | 会 stop/rm/run Docker bot | 默认禁止修改；禁止随意运行 |
| `scripts/ensure_dry_run_bots_started.sh` | 会启动容器并启动 trader state | 默认禁止运行/修改 |
| `scripts/refresh_data.sh` | 会下载数据、启动 bot、运行健康 gate | 默认禁止运行/修改 |
| `scripts/check_system_health.sh` | server/runtime authority gate | 修改需同步测试和 server 验证 |
| `scripts/check_trades.sh` | 告警链路和状态文件写入 | incident 任务外默认只读 |
| `dashboard/lib/config.js` | bot lane/端口/角色拓扑 | 修改需同步 dashboard/scripts/tests |
| `dashboard/server.js`, `dashboard/public/*` | 用户看到的运行状态和 auth/API 行为 | 修改需本地和 server 验证 |
| `deploy/freqtrade-monitor.service` | systemd 服务 | 默认禁止修改 |
| `reports/` | 研究证据，失败候选也应保留 | 禁止静默删除或覆盖关键证据 |
| `.tmp_v1127_analysis/`, `.tmp_v1128_analysis/`, `output/` | 临时/分析产物 | 可审计，但不应被 Task 1 清理 |

## 不允许 Codex 默认修改的文件

以下路径应进入 `guard_harness_diff.js` 的默认 deny list。只有用户在任务中显式授权，且任务写明修改目的、验证命令和 server 是否涉及时，才允许进入变更范围。

```text
.env
*.pem
*.key
*.secret
user_data/monitor.env
user_data/*live*.json
user_data/*.sqlite
user_data/*.sqlite-*
user_data/data/**
user_data/backtest_results/**
user_data/config_*.json
strategies/**
dashboard/lib/config.js
scripts/start_bot.sh
scripts/ensure_dry_run_bots_started.sh
scripts/refresh_data.sh
scripts/check_system_health.sh
scripts/check_trades.sh
deploy/**
reports/**/raw/**
reports/**/backtest-result-*.zip
reports/**/backtest-result-*.feather
```

额外冻结项：

```text
strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py
user_data/config_multi_futures_v1082.json
strategies/RegimeAwareV1129ResidualDragMicroSizer.py
user_data/config_multi_futures_v1129.json
scripts/run_v1129_residual_drag_micro_sizer_backtests.sh
reports/reliable_strategy_search_v1129/**
```

## 推荐新增或补充的 AGENTS.md 内容

当前 `AGENTS.md` 已经覆盖 server authority、V11/V10.8.2 拓扑、交易约束、dashboard 规则和 DoD。建议补充以下段落，而不是替换现有内容。

```markdown
## Agent Harness Defaults

Default mode is read-first and diff-guarded. Unless the user explicitly grants
scope, agents may only modify documentation, tests, harness scripts, CI files,
and new audit reports.

Agents must not modify strategy code, `user_data/config*.json`, live/dry-run
bot configuration, dashboard topology, start/refresh/health scripts, or server
deployment files by default.

For every task, state:

- allowed edit surface,
- forbidden edit surface,
- whether server authority is involved,
- verification commands,
- stop condition.

Before finalizing a code or repo-harness change, run:

```bash
bash scripts/run_agent_readiness_checks.sh
```

If `scripts/run_agent_readiness_checks.sh` is not available yet, run the
equivalent static checks listed in `docs/agent_operating_playbook.md` and do not
claim runtime health.

## Frozen Benchmark And Scout Surfaces

V10.8.2 benchmark files and V11.29 scout/research files are frozen unless the
user names them explicitly in the task. Do not edit, relabel, delete, or replace
them as cleanup.

Frozen by default:

- `strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py`
- `user_data/config_multi_futures_v1082.json`
- `strategies/RegimeAwareV1129ResidualDragMicroSizer.py`
- `user_data/config_multi_futures_v1129.json`
- `scripts/run_v1129_residual_drag_micro_sizer_backtests.sh`
- `reports/reliable_strategy_search_v1129/**`

## Secret And Environment Boundary

Do not read, print, diff, summarize, or rewrite `.env`, `user_data/monitor.env`,
private keys, exchange credentials, dashboard passwords, API tokens, or live
config secrets. If a check requires credentials, derive them only inside the
server-local command and redact them from all responses and reports.

## Report-Only Tasks

For audit/report tasks, write only the requested report artifact. Do not perform
cleanup, reformatting, strategy updates, bot restarts, data refreshes, or server
sync unless the user explicitly asks for those actions.
```

## 推荐新增的 guard scripts

| 脚本 | 优先级 | 行为 | 允许范围 |
| --- | --- | --- | --- |
| `scripts/guard_harness_diff.js` | P0 | 读取 `git diff --name-status --cached` 和工作区 diff；若触碰 deny list 则失败 | 可用 `ALLOW_TRADING_SURFACE=1` 解锁部分路径，但密钥路径永远不可解锁 |
| `scripts/guard_no_secret_material.js` | P0 | 扫描 diff 内容，拦截 `api_key`、`secret`、`password`、`token`、PEM header、Basic Auth 明文 | 只扫描 diff，不读取 `.env` 或 monitor env |
| `scripts/guard_trading_surface.js` | P0 | 对策略和 config diff 做关键词拦截：`stake_amount`、`leverage`、`stoploss`、`minimal_roi`、`pair_whitelist`、`max_open_trades`、`dry_run`、`db_url`、`listen_port` | 默认阻止；仅显式交易任务允许 |
| `scripts/run_agent_readiness_checks.sh` | P0 | 串联 bash syntax、Node syntax、Node tests、Python compile、guard scripts | 不启动 Docker，不访问 server，不读 secret |
| `scripts/guard_dashboard_topology.js` | P1 | 验证默认 dashboard lanes 仍为 V11.16 current、V10.8.2 benchmark，scout 只在配置允许时出现 | 可复用现有 `tests/test_start_bot_static.js` 逻辑 |
| `scripts/guard_reports_append_only.js` | P1 | 阻止删除历史报告、zip、feather、raw evidence | 允许新增 `reports/audits/*.md` |
| `scripts/guard_agent_task_contract.js` | P1 | 验证 task 文件包含目标、允许修改面、禁止修改面、验证命令、server 状态 | 配合 `tasks/templates/agent_task.md` |

建议 P0 guard 的默认退出语义：

```text
0 = pass
1 = blocked high-risk diff
2 = tool usage/config error
```

## 推荐新增的 CI checks

建议先做轻量、无凭证、无 server、无 Docker runtime 的 CI。不要在 GitHub Actions 中 SSH server，也不要读取或注入交易所/API 凭证。

`.github/workflows/agent-readiness.yml` 建议包含：

| Job | 命令 | 目的 |
| --- | --- | --- |
| shell syntax | `bash -n scripts/*.sh` | 防止 shell 脚本语法损坏 |
| Node syntax | `node --check dashboard/server.js`、`node --check dashboard/lib/config.js`、`node --check dashboard/public/app.js`、`node --check scripts/*.js` | 防止 JS 语法损坏 |
| Node tests | `node --test tests/test_dashboard_phase2_summary.js tests/test_start_bot_static.js tests/test_live_readiness.js tests/test_opportunity_audit.js tests/test_v11_closed_loop_report.js` | 锁住 dashboard/topology/readiness/report 基础行为 |
| Python compile | `python -m compileall scripts btc_system tests` | 不导入 Freqtrade 的前提下捕捉 Python 语法错误 |
| secret guard | `node scripts/guard_no_secret_material.js --base origin/main` | 防止密钥进入 diff |
| trading surface guard | `node scripts/guard_trading_surface.js --base origin/main` | PR 默认禁止策略/config/参数改动 |
| harness diff guard | `node scripts/guard_harness_diff.js --base origin/main` | 默认 deny list 执行 |

后续可加 nightly/manual CI：

| Job | 触发 | 命令 | 注意 |
| --- | --- | --- | --- |
| docker smoke | `workflow_dispatch` 或 nightly | `bash scripts/run_tests.sh` | 需要 Docker；成本高，不应阻塞所有文档/报告 PR |
| server health | 手工，不在 CI secrets 中保存交易凭证 | `ssh ... './scripts/check_system_health.sh'` | 只在用户明确要求 server 验证时执行 |

## P0/P1/P2 改造清单

### P0：防误改最小闭环

| 项 | 目标 | 验收 |
| --- | --- | --- |
| 新增 `scripts/guard_harness_diff.js` | 默认阻止策略、配置、密钥、server 操作脚本被误改 | 对当前 Task 0 只允许 `reports/audits/harness_readiness_audit.md` 通过 |
| 新增 `scripts/guard_no_secret_material.js` | diff 中出现密钥/密码/token/PEM 时失败 | 人造测试 diff 能触发失败；正常报告 diff 通过 |
| 新增 `scripts/guard_trading_surface.js` | 默认阻止交易参数和 bot config 变更 | 修改 `stake_amount`、`leverage`、`pair_whitelist` 的 diff 被拦截 |
| 新增 `scripts/run_agent_readiness_checks.sh` | 本地统一静态 gate | 不启动 bot、不访问 server、不读 `.env` |
| 新增 `.github/workflows/agent-readiness.yml` | PR/push 自动执行 static gate | CI 无 server/secret 依赖 |

### P1：任务协议与文档一致性

| 项 | 目标 | 验收 |
| --- | --- | --- |
| 新增 `tasks/README.md` | 说明任务如何声明范围、禁改面、验证命令 | 新 agent 能从 task 文件判断是否可改策略/config |
| 新增 `tasks/templates/agent_task.md` | 标准任务模板 | 模板包含 allowed/forbidden/server/verification/stop |
| 新增 `docs/harness/change_surface_matrix.md` | 路径级风险矩阵 | 覆盖 `strategies`、`user_data`、`dashboard`、`scripts`、`reports` |
| 更新 README | 将旧 V6/V6.7 入口改为指向当前 V11/V10.8.2 topology 和 `AGENTS.md` | 不改业务逻辑，只修入口叙事 |
| 新增 `scripts/guard_dashboard_topology.js` | 将 dashboard lane 规则从测试中抽成明确 guard | 默认检查 V11.16/V10.8.2，V11.29 仅 scout |

### P2：长期治理

| 项 | 目标 | 验收 |
| --- | --- | --- |
| 新增 `CODEOWNERS` | 高风险路径要求人工审阅 | PR 触碰 `strategies/` 或 `user_data/` 时自动请求审阅 |
| 新增 `.pre-commit-config.yaml` | 本地提交前运行 guard | 不强制开发者先安装，作为可选增强 |
| 新增 `docs/harness/agent_ready_scorecard.md` | 长期评分 | 每次大改造后更新分数和剩余风险 |
| 新增报告索引 | 审计、验收、闭环报告可被快速找到 | `reports/README.md` 或 `reports/audits/README.md` |

## 推荐最小 Task 1

任务名：`Task 1: Add Static Agent Guardrails`

目标：新增最小静态护栏，让 future agent 在默认情况下无法误改策略、bot 配置、密钥、V10.8.2、V11.29 或 server 操作面。

允许修改：

```text
scripts/guard_harness_diff.js
scripts/guard_no_secret_material.js
scripts/guard_trading_surface.js
scripts/run_agent_readiness_checks.sh
.github/workflows/agent-readiness.yml
tasks/README.md
tasks/templates/agent_task.md
docs/harness/change_surface_matrix.md
```

禁止修改：

```text
strategies/**
user_data/**
dashboard/lib/config.js
dashboard/server.js
dashboard/public/**
scripts/start_bot.sh
scripts/ensure_dry_run_bots_started.sh
scripts/refresh_data.sh
scripts/check_system_health.sh
scripts/check_trades.sh
deploy/**
reports/reliable_strategy_search_v1129/**
```

推荐验证：

```bash
bash -n scripts/run_agent_readiness_checks.sh
node --check scripts/guard_harness_diff.js
node --check scripts/guard_no_secret_material.js
node --check scripts/guard_trading_surface.js
bash scripts/run_agent_readiness_checks.sh
```

Task 1 停止条件：

```text
guard scripts 能拦截禁止路径；
static CI workflow 能运行；
任务模板存在；
不修改策略、不修改配置、不启动 bot、不登录服务器。
```

## 最小可执行任务拆分表

| 顺序 | 任务 | 文件范围 | 验证 | 是否触碰业务 |
| ---: | --- | --- | --- | --- |
| 0 | 本审计报告 | `reports/audits/harness_readiness_audit.md` | 检查报告存在且包含必需章节 | 否 |
| 1 | Static Agent Guardrails | `scripts/guard_*.js`、`scripts/run_agent_readiness_checks.sh`、`.github/workflows/agent-readiness.yml` | Node check、bash -n、guard 自测 | 否 |
| 2 | Task Contract | `tasks/README.md`、`tasks/templates/agent_task.md` | 模板字段完整 | 否 |
| 3 | Change Surface Matrix | `docs/harness/change_surface_matrix.md` | deny/allow path 覆盖高风险目录 | 否 |
| 4 | README Entry Repair | `README.md` | 文案指向 `AGENTS.md` 和当前 V11/V10.8.2；不改配置 | 否 |
| 5 | Dashboard Topology Guard | `scripts/guard_dashboard_topology.js`、相关测试 | 锁定 V11.16 current、V10.8.2 benchmark、V11.29 scout | 否，除非发现现有测试冲突 |
| 6 | Optional Pre-commit | `.pre-commit-config.yaml` | 本地可运行 guard | 否 |

## 本轮未执行事项

- 未执行 Task 1。
- 未修改 V10.8.2。
- 未修改 V11.29。
- 未新增策略版本。
- 未修改 dry-run/live 配置。
- 未修改交易参数、杠杆、仓位、止损、ROI、pairlist。
- 未读取或触碰 `.env`、API key、交易所凭证、服务器密钥。
- 未 SSH 服务器，未运行 server health gate，未启动/停止任何 bot。
