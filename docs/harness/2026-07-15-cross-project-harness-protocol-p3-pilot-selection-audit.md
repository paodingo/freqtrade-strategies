# Cross-Project Harness Protocol P3 Pilot 选择审计

- 日期：2026-07-15
- 状态：`pilot_selected_plan_required`
- Protocol 基线：`harness-protocol-v0.1`
- Protocol/P2 实现提交：`049fc4b60182bcbaf7a0b01e40522a53d30c2d45`

## 1. 结论

P3 Pilot 选择 `rehab-intervention`，不选择 `freqtrade-strategies` 或当前状态下的 `ChinaSectorRadar`。

本选择只确定 Pilot 项目和计划方向，不授权修改 `rehab-intervention`、执行 Campaign、复制 Protocol snapshot、创建 approval artifact 或进入 P4。

P3 的目标不是证明三个项目应当使用同一个 runner，而是让第二个真实消费者在保留项目本地 runner 的前提下，以 Protocol v0.1 作为兼容边界完成一次 Harness-only governed run，并测量 Core 是否需要修改。

## 2. 冻结身份

| project_id | repository/worktree | branch | commit | status |
| --- | --- | --- | --- | --- |
| `freqtrade-strategies` Protocol source | `D:/code/freqtrade-strategies-p1-integration` | `codex/btc-mvp-system-p1-integrated` | `049fc4b60182bcbaf7a0b01e40522a53d30c2d45` | clean |
| `freqtrade-strategies` P1 source | `D:/code/freqtrade-strategies-clean` | `codex/btc-mvp-system-harnessed` | `fc621f1deee152689a2d79b3099a5da581486144` | clean |
| `china-sector-radar` | `D:/code/ChinaSectorRadar` | `main` | `a8b99c74f43aeb1e34db600bdbd5608a888d2d7f` | clean |
| `rehab-intervention` | `D:/book/rehab-intervention` | `main` | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` | clean |

任何 commit 或 clean status 漂移都必须重新审计，不得自动刷新 descriptor 或 approval。

## 3. 选择门槛

P3 设计要求选择“一个较低成熟度项目的下一次、独立批准的 Harness phase”，同时保留项目本地 runtime，并测量 Core change count。候选必须同时满足：

1. 不是 Protocol/Core 的第一消费者自证；
2. 当前 authority 允许定义一个新的 Harness-only phase；
3. 能使用现有项目本地 runner 完成真实 governed run；
4. 不需要业务代码、数据库、网络、scheduler、E2E、deployment 或 secret；
5. 能保留 P2 的 `mapped` / `derived` / `gap`，不为通过 Pilot 补造能力；
6. 可以独立记录 scope、budget、approval、state、gate 和 evidence；
7. 如果 Core 必须修改，能够 fail closed 并先提交设计修订，而不是在 Pilot 中顺手扩张 Core。

## 4. 候选比较

| 候选 | P2 状态 | 当前可执行的下一 Harness phase | 本地 runner | 作为第二消费者的价值 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `freqtrade-strategies` | `mapped=7`, `derived=4`, `gap=0` | 它是 Protocol/Core 的来源和第一消费者 | 成熟 | 会形成宿主自证，不能证明迁移性 | 排除 |
| `ChinaSectorRadar` | `mapped=5`, `derived=3`, `gap=3` | H1/H1.1 已完成；当前唯一合法下一动作是 `request_h2_plan_approval` | H1 Harness 已实现 | 跨项目价值高，但当前 Pilot 会混入 H2 业务语义修复，或非法重放已关闭 H1 | 当前延后 |
| `rehab-intervention` | `mapped=3`, `derived=6`, `gap=2` | 设计明确允许 future Campaign iteration；可以定义 Harness-only compatibility Campaign | `scripts/harness-campaign.mjs` | 能验证 task/budget/state/retry 与 Protocol 的兼容，同时暴露 approval/role gap | 选择 |

## 5. 为什么不再优先选择 ChinaSectorRadar

在只看“成熟度”和“跨项目差异”时，`ChinaSectorRadar` 看起来是自然候选；当前 authority 证据否定了直接执行这一选择：

- H1.1 independent review 已 `pass`；
- canonical readiness 仍为 `blocked/1`，保留四个 H2 business-semantic blocker；
- candidate-time evidence 的 `review.status` 仍为 `pending`，后续 reviewer artifact 单独记录 `pass`；
- 当前唯一允许的下一动作是请求 H2 计划批准，而不是执行 H2、重放 H1 或创建新的业务 phase。

P3 不能借“Protocol Pilot”绕过这些边界。只有未来出现单独批准的 Harness-only phase，或 H2 完成后重新冻结 authority，才重新评估它。

## 6. rehab Pilot 的适配价值

`rehab-intervention` 已有真实运行过的 Phase 2 Campaign：5 个 task、allowlist、`max_attempts=2`、file/time budget、validation、persisted ignored state 和 resume。它同时保留以下缺口：

- `RoleContract=gap`：普通 coding-agent 指引不是可分发 Role Pack；
- `ApprovalRecord=gap`：Phase 2 acceptance prose 不是 fingerprint-bound approval artifact；
- `GateResult=derived`：本地 runner 没有完整 portable `error=2` 语义；
- local state 是 ignored evidence，不是 committed portable authority；
- 历史 ESLint debt、安全风险和 data-mutating command 边界必须继续可见。

这组“已有真实 runner，但 Protocol 治理不完整”的状态比一个已经高度成熟的宿主更适合作为第二消费者。

## 7. Pilot 冻结边界

P3 Pilot 只能：

- 在独立 `rehab-intervention` worktree/branch 中工作；
- 使用现有 `scripts/harness-campaign.mjs`，不得替换 runner；
- 使用 pinned、hash-bound 的 Protocol v0.1 snapshot 作为一次性 Pilot 兼容边界；
- 创建项目本地 adapter、ProjectBinding、execution request/approval、result 和 acceptance evidence；
- 运行只读/静态验证及现有非数据变更检查；
- 记录 Core change count、adapter-only change count、gap preservation 和 rollback 方法。

P3 Pilot 禁止：

- 修改业务行为、数据库 schema/migration、auth/session、AI key、deployment、UI 或 API；
- 运行 E2E、seed、import、migration 或任何数据变更命令；
- 访问网络、scheduler、browser、Docker、production data 或 secret；
- 创建共享 package、CLI、plugin、通用 executor 或 Role Pack；
- 自动把 `RoleContract` / pre-Pilot `ApprovalRecord` gap 改写为历史上已经存在；
- 修改 Protocol Core 以让 Pilot 通过；
- 进入 P4 runtime extraction decision。

## 8. 成功与失败判定

成功必须同时满足：

1. Protocol snapshot 与 `049fc4b` 的 canonical files hash 完全一致；
2. rehab source commit 与批准时冻结身份一致；
3. 项目本地 runner 完成一次新 Campaign，且 state/evidence lifecycle 可追踪；
4. ProjectBinding 和 Pilot artifacts 通过独立 Protocol conformance；
5. `RoleContract` gap、pre-Pilot approval gap、historical baseline debt 和 unsafe commands 仍可见；
6. Core schema/code change count 为 `0`；若不为 `0`，Pilot 必须停止并进入设计修订；
7. rehab business/protected paths 相对 Pilot 起始 commit 无变化；
8. 独立 reviewer 给出 `Approved`。

合法失败包括：`source_identity_stale`、`authority_mismatch`、`contract_gap`、`scope_violation`、`baseline_regression`、`core_change_required`。它们必须报告为 `blocked`；parser/runtime unavailable 才是 `error`。

## 9. 下一道门

进入单独的 P3 implementation plan。该计划必须冻结两个仓库的 exact write surface、两次人工 approval gate、测试数、Campaign budget、evidence、rollback 和 independent review。

本审计完成后停止；未获得用户明确批准前，不创建 rehab worktree，不修改 sibling repo，不执行 Pilot Campaign。
