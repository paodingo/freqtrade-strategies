# Cross-Project Harness Protocol P2 只读映射审计

- 日期：2026-07-15
- 状态：`mapping_only_ready`
- 协议基线：`harness-protocol-v0.1`

## 1. 结论

P2 可以进入实施计划，但当前只授权“项目事实到 Protocol contract 的只读映射”。本审计不授权共享 Runtime、CLI、package、plugin、Role Pack 分发、兄弟仓库修改或项目本地 runner 替换。

三个项目都能提供足够的 authority、task、state 或 evidence 来源，但没有任何一个项目能直接、完整地提供全部 11 个 Protocol contract。P2 必须保留三种映射状态：

- `mapped`：存在能够直接表达该 contract 语义的当前权威来源；
- `derived`：需要从多个只读来源做确定性投影，不得扩大原有权限；
- `gap`：不存在语义完整的当前来源，必须显式保留缺口，不得补造字段或推断成功。

P2 的核心成功条件不是“所有格子都变成 mapped”，而是证明每个项目的严格规则不会被共享 Protocol 弱化。

## 2. 冻结的项目身份

| project_id | repository | branch | commit | worktree status |
| --- | --- | --- | --- | --- |
| `freqtrade-strategies` | `paodingo/freqtrade-strategies` | `codex/btc-mvp-system-p1-integrated` | `fc621f1deee152689a2d79b3099a5da581486144` | clean |
| `china-sector-radar` | `ChinaSectorRadar` | `main` | `a8b99c74f43aeb1e34db600bdbd5608a888d2d7f` | clean |
| `rehab-intervention` | `rehab-intervention` | `main` | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` | clean |

这些 commit 只证明本次审计读取的版本。P2 实施前必须重新核对；commit 漂移不能被静默接受。

## 3. Authority 优先级

映射后的 authority 顺序必须固定为：

1. 用户对项目 Phase 的明确批准；
2. 项目本地 `AGENTS.md`、constitution、phase scope、quality baseline 与 approval artifact；
3. 项目本地 protected surface、capability prohibition 和数据治理规则；
4. P2 mapping descriptor；
5. Protocol Core 默认值。

低优先级来源不能覆盖高优先级禁止项。映射器遇到未知 capability、authority fingerprint 不一致、source commit 漂移或 required source 缺失时必须 fail closed。

## 4. 11-contract 映射矩阵

| Protocol contract | freqtrade-strategies | ChinaSectorRadar | rehab-intervention |
| --- | --- | --- | --- |
| `ProjectBinding` | `derived`：`AGENTS.md`、Research Constitution、runtime/evaluation policy、Registry 和 evidence roots | `derived`：`AGENTS.md`、`h1_scope.md`、H1 manifest、schemas 与 harness reports | `derived`：`AGENTS.md`、quality baseline、Phase 2 Campaign、runner 与 local state |
| `PhaseAuthority` | `mapped`：`research-constitution.yaml`、human approvals、current research state | `mapped`：`AGENTS.md` 与 `docs/harness/h1_scope.md` 明确 H1 及 H2 approval gate | `derived`：mandatory rules 与 Phase 2 acceptance 存在，但没有独立 phase fingerprint artifact |
| `CapabilityPolicy` | `mapped`：risk classes、permanent prohibitions、Validation/Holdout rules | `mapped`：H1 allowed/forbidden operations 与 protected business surfaces | `derived`：AGENTS high-risk rules、data-mutating commands 与 Campaign stop policy |
| `RoleContract` | `mapped`：Researcher、Critic、Director 的职责和禁止项可追溯，但仍需规范化 descriptor | `gap`：存在 independent reviewer 事实，没有完整、机器可验的 role input/output/capability contract | `gap`：Phase 2 runner 管理 task，不构成多 Agent role contract |
| `TaskManifest` | `derived`：Campaign YAML、execution authorization 和 task/governance artifacts | `mapped`：`harness/tasks/h1-reliability-harness.json` | `mapped`：`harness/campaigns/phase2.json` |
| `Budget` | `mapped`：Constitution budget 与 Campaign-specific limits | `gap`：H1 manifest 没有完整的 file/time/attempt budget contract | `mapped`：`max_attempts`、`max_changed_files`、`max_seconds` |
| `GateResult` | `mapped`：readiness、baseline verifier、campaign/audit decisions | `mapped`：H1 readiness 明确 `pass=0`、`blocked=1`、`tool_error=2` | `derived`：validation results 和 completed/failed/blocked 存在，但没有完整 portable `error=2` 语义 |
| `RunState` | `mapped`：Director Registry、current-state projection 与 append-only discovery records | `gap`：有 readiness/evidence snapshot，没有通用 resumable state backend | `mapped`：ignored local `harness/state/phase2.state.json` 支持 retry/resume |
| `ApprovalRecord` | `mapped`：fingerprint-bound human/governance approvals | `derived`：Phase approval 和 independent review 可追溯，但没有单一规范化 approval record | `gap`：acceptance 文档存在，没有 artifact-bound approval fingerprint contract |
| `EscalationRecord` | `derived`：blocked decisions、closures、invalidations 与 governance events | `derived`：blocker IDs、readiness result 和 H2 approval gate | `derived`：`blockedTaskId` 与 reason 可投影，但缺 required authority 和 safe resume contract |
| `EvidenceBundle` | `derived`：Registry、reports、approvals、state projection 分布式存在 | `mapped`：`evidence-package.v1` schema、writer 和 canonical artifacts 已存在 | `derived`：Campaign state、validation results、quality baseline 与 acceptance doc 分布式存在 |

## 5. 项目发现

### 5.1 freqtrade-strategies

优势：

- governance、approval fingerprint、budget、role boundary 和 append-only state 最成熟；
- Researcher、Critic、Director 的职责分离已由文档、artifact 和测试共同约束；
- `no_research_recommended` 与 human rejection 能作为合法终态，而不是伪造任务成功。

必须保留的 gap：

- evidence 分散在 Registry、state projection、approval、Campaign 与 report 中，尚无单一项目级 `EvidenceBundle`；
- `current-research-state.json` 生成于 2026-07-13，而 discovery human decision 在 2026-07-15，映射不得把不同时间快照合并成同一“当前状态”；
- project role 不能进入 Core；P2 只记录到 `RoleContract` 的来源和转换，不分发通用 Research Role Pack。

### 5.2 ChinaSectorRadar

P0 设计中的旧映射已经过时：当前 authority 是 `H1 Reliability Harness`，不是 H0；H1 task manifest、readiness、golden fixtures 和 evidence package 已经实现，不再是“planned”。

必须保留的当前事实：

- H1.1 independent review 已通过，但 canonical readiness 当前仍为 `blocked/1`，包含四个明确登记的 H2 业务语义 blocker，不能包装为 full normal；
- `h1_reliability_harness.json` 作为 candidate-time evidence 仍记录 `review.status: pending`，随后提交的独立 review Markdown 记录 `review_status: pass`；P2 必须按 artifact lifecycle 分别保留两个时间点，不能静默覆盖 candidate evidence；
- 当前唯一允许的下一动作是 `request_h2_plan_approval`，不授权执行 H2；
- H1 允许 Harness completion 与业务 blocker 并存，但不授权 H2 remediation、daily job、PostgreSQL 写入、评分修改或 Phase 9B Web；
- H1 manifest 没有通用 Budget、RunState 和完整 RoleContract，这些必须标为 gap。

### 5.3 rehab-intervention

优势：

- Phase 2 Campaign 已真实执行，runner 支持 allowlist、budget、validation、retry、state persistence 与 resume；
- 本地 state 明确记录 5 个 task completed；历史 ESLint debt 保持可见而没有为了变绿被删除。

必须保留的 gap：

- `harness/state/phase2.state.json` 是 ignored local state，不是可移植、已提交的 authority artifact；
- runner 是项目本地 executor，不是共享 Runtime，也不证明存在多 Agent Role Pack；
- phase authority、approval fingerprint、portable tool error 与统一 evidence bundle 都不完整；
- auth/session/database/deploy 和 data-mutating command 约束必须作为项目扩展保留，不能被 Core 默认值覆盖。

## 6. 跨项目不变量

P2 descriptor 和测试必须证明：

1. 每个项目都覆盖全部 11 个 contract，状态只能是 `mapped`、`derived` 或 `gap`；
2. `gap` 不能生成伪造的 contract instance；
3. 项目禁止项只能保持或收紧，不能被 Protocol 默认值放宽；
4. `blocked` 是治理结果，`error` 是工具/环境结果，两者不能互换；
5. Harness completion 与 business readiness 必须独立；
6. source commit、authority fingerprint 和 evidence timestamp 必须显式绑定；
7. sibling repository source 只允许 repo-relative references，不复制 secret、database、market data 或生成物；
8. P2 测试不得 import 或执行任何项目 Runtime。

## 7. P2 写入边界

允许后续计划提出：

- language-neutral mapping descriptor schema；
- 三个项目的 frozen mapping descriptor；
- synthetic failure fixtures 与 isolated conformance tests；
- exact-path guard 和文档更新。

明确禁止：

- 修改 `ChinaSectorRadar` 或 `rehab-intervention`；
- 执行 daily job、Campaign、E2E、database、network、scheduler、trading 或 deployment；
- 创建共享 executor、CLI、package、plugin 或 model-provider interface；
- 将 `derived` 或 `gap` 宣称为 project capability；
- 选择或执行 P3 pilot。

## 8. Gate

本审计建议进入一个单独审批的 P2 implementation plan。计划必须冻结 exact paths、test counts、source commit refresh、independent review 和 clean-worktree baseline；未获审批前不创建 mapping descriptor 或测试。
