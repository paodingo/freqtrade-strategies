# Cross-project Harness Protocol P4 Runtime Extraction Decision Audit

- 日期：`2026-07-15`
- 审计状态：`decision_ready`
- 推荐决策：`distribute_protocol_contracts_defer_shared_runtime`
- Canonical incubation owner：`paodingo/freqtrade-strategies@exact-release-commit`
- Shared executable Runtime：`deferred`
- Standalone repository：`deferred`
- Role Pack distribution：`deferred`

## 1. 结论

P3 已经证明“共享 Protocol contracts + project-local adapter + project-local runner”可以跨项目成立，而且第二消费者没有要求修改 Protocol Core。现在可以进入 P4 的静态 Protocol distribution 实施计划，但不应抽取统一 executable Runtime。

推荐把 P4 限定为：

1. 明确 v0.x canonical source、版本、发布清单和升级责任；
2. 建立可复现的静态 distribution manifest、fingerprint profile、test vectors、builder/verifier；
3. 继续由各项目保留本地 runner、state backend 和项目权限；
4. 不创建通用 `BaseAgent`，只分发 `RoleContract` contract；
5. 不创建 package、CLI、plugin、skill、共享服务或第四仓库。

## 2. 当前证据身份

| Evidence source | Branch / status | HEAD |
| --- | --- | --- |
| Protocol source | `codex/btc-mvp-system-p1-integrated`, clean | `2b253a2347d617b1074c3d608ab598b6808b5d6b` |
| Freqtrade project state | `codex/btc-mvp-system-harnessed`, clean | `fc621f1deee152689a2d79b3099a5da581486144` |
| ChinaSectorRadar | `main`, clean | `a8b99c74f43aeb1e34db600bdbd5608a888d2d7f` |
| Rehab deployment baseline | `main`, clean | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` |
| Rehab P3 Pilot evidence | `codex/harness-protocol-p3-pilot`, clean | `5b923a6e0ec745f30cd54304b1db401cce273069` |

当前 Protocol P1+P2 focused suite 已在 Protocol source HEAD 重跑：`34/34 passed`。

P3 Pilot evidence：

- Campaign 调用 `1` 次；
- 3/3 tasks completed，每项 attempts=1；
- adapter tests `12/12`；
- full check `77 files / 495 tests`；
- protected/business changes `0`；
- Protocol Core changes `0`；
- fresh detached independent review：`Approved`，无 findings。

## 3. P4 extraction prerequisites

| 条件 | 当前判断 | 证据/限制 |
| --- | --- | --- |
| 至少两个 adapter 可表达 Protocol | `met` | 三个 P2 mapping descriptor 通过；rehab project-local adapter 通过 |
| 第二消费者不向 Core 引入 domain literal | `met` | P3 Core change count `0` |
| adapter-only differences 保持隔离 | `met` | rehab 只增加 local binding/adapter/Campaign/evidence |
| 至少两个项目通过同一 shared Runtime 执行 | `not_met` | 目前只有 rehab 通过 Protocol adapter 执行；freqtrade/China 仍用本地控制面 |
| Runtime distribution/upgrade ownership 已明确 | `not_met_before_p4` | 本审计提出 v0.x incubation owner，但尚无发布实现 |
| 回滚到本地 Harness 有定义 | `met` | 三项目 runner 未替换；rehab Pilot 位于独立分支 |

因此：静态 Protocol distribution 的条件已经满足；shared executable Runtime 的条件尚未满足。

## 4. 三个本地执行面的真实差异

| 维度 | Freqtrade | ChinaSectorRadar | rehab-intervention |
| --- | --- | --- | --- |
| 主要实现 | Python deterministic control plane | Python + PowerShell readiness/evidence harness | Node.js Campaign runner |
| State backend | SQLite Registry、leases、append-only events、project state projection | canonical reports/evidence package；无通用 resumable backend | ignored JSON state，retry/resume |
| Role maturity | Researcher/Critic/Director 等机器可追溯职责 | reviewer/coordinator 事实存在，完整 RoleContract 仍是 gap | task runner；RoleContract 仍是 gap |
| Failure semantics | 细分 infra/validation/candidate/guard/budget | portable `0/1/2` readiness，保留 H1 blockers | completed/failed/blocked；portable tool error 仍不完整 |
| Domain safety | Validation/Holdout、market/runtime contamination | Phase authority、provider/report truth、protected H2 paths | auth/session/database/deploy/data mutation |
| Command execution | 固定 Python/runtime contract | readiness scripts and exact manifest commands | `spawnSync(..., shell: true)` |

这些差异不是“待统一的重复代码”，而是项目 authority、domain risk 和 lifecycle 的一部分。现在强行抽取 shared Runtime 会把成熟项目的实现偶然性变成其他项目的依赖。

## 5. 已稳定的共享层

以下语义已跨至少两个项目成立，适合静态分发：

- 11 个 Core contracts；
- authority precedence 与 human approval；
- exact/narrow path permissions；
- budgets、stop conditions 和 consumed-attempt evidence；
- `passed/blocked/error` 与 `0/1/2` portable mapping；
- Harness completion 与 business readiness 分离；
- known baseline debt 不得隐藏；
- ProjectBinding、mapping descriptor 和 fail-closed gap；
- ApprovalRecord/EvidenceBundle contract shape；
- synthetic fixtures 与 conformance tests。

以下内容继续留在项目 Adapter/runner：

- command execution、shell/runtime selection；
- retry/lease/state persistence 实现；
- project capability registry；
- Research/market/provider/auth/deployment 语义；
- phase-specific role instances；
- model provider 和 reasoning level routing。

## 6. 方案比较

| 方案 | 优点 | 主要问题 | 决策 |
| --- | --- | --- | --- |
| A. Versioned static Protocol distribution bundle | language-neutral；低耦合；保留本地 runner；易回滚 | 需要 manifest、fingerprint 和升级治理 | `recommended_now` |
| B. 立即创建 standalone neutral repository | ownership 看起来更中立 | 只有一次第二消费者 Pilot；新增发布/同步/权限治理 | `defer` |
| C. Python/Node package 或 CLI | 安装和验证方便 | 过早选择 runtime/package manager；消费者形成执行依赖 | `defer` |
| D. Codex plugin/skill | 使用体验好，可携带说明和工具 | 平台特定；不能成为项目 authority；无法替代 committed evidence | `defer` |
| E. Shared executable Runtime | 理论上减少 runner 重复 | 三个 state/command/risk 模型尚不等价，耦合最高 | `reject_now` |
| F. 继续手工复制无 manifest | 无新增工具 | 已由 P3 CRLF finding 证明不可持续 | `reject` |

## 7. Ownership decision

### 7.1 v0.x canonical owner

在出现第二个非 source-project 的真实 Protocol execution consumer 前，v0.x canonical source 继续由 `paodingo/freqtrade-strategies` 内的：

- `harness/protocol/v0.1/**`
- `harness/mappings/v0.1/**`

承担。权威身份是 exact release commit + release manifest，不是当前本地 worktree、branch name 或 Freqtrade domain policy。

这是一项 incubation ownership，不代表 Freqtrade 的 Researcher、Campaign、market 或 strategy 语义进入 Core。

### 7.2 neutral repository trigger

只有同时满足以下条件，才重新评估 standalone repository：

1. 至少两个非 source-project consumer 完成真实 governed Protocol Pilot；
2. 至少两个 release cycle 不需要 domain-driven Core change；
3. publisher、reviewer、versioning、security 和 rollback owner 明确；
4. consumer upgrade 不依赖 sibling-repo checkout；
5. migration plan 不替换项目本地 authority。

## 8. Distribution decision

P4A 采用静态、versioned、vendor-friendly distribution：

- release manifest 索引现有 Protocol Core、mapping schema、synthetic fixtures 和 project descriptors；
- 每个 artifact 记录 repo-relative path、component、media type、bytes、fingerprint profile 和 SHA-256；
- consumer 只导入其所需 component，并生成 project-local lock；
- upgrade 必须由项目本地 task/approval 明确触发；禁止 auto-update；
- distribution verifier 只验证静态文件，不 import 或执行 consumer Runtime；
- build/verify 工具可以使用 source repo 的 Python 3.12，但发布物保持 JSON/Markdown，Python 不成为 consumer Runtime requirement。

### Fingerprint profile

P4A 为 release text files 定义 `sha256-text-lf-v1`：

1. 输入必须是 UTF-8 且无 BOM；
2. CRLF 和 lone CR 规范化为 LF；
3. 除 EOL 外不重排 key、不改 whitespace、不补删 trailing newline；
4. 对规范化 UTF-8 bytes 计算 SHA-256；
5. duplicate JSON keys、invalid UTF-8 或未知 profile fail closed。

P3 历史 raw-byte 与 project-local semantic fingerprints 保持历史含义，不被 P4 追溯改写。Approval semantic fingerprint 的跨项目统一留到 future protocol version，不在 P4A 静默重定义。

## 9. Agent 与 Role Pack 决策

- Core 继续只定义 `RoleContract`；
- Freqtrade Researcher/Critic/Director 继续属于 Freqtrade adapter 候选或 future research-discovery Role Pack；
- China audit roles 和 rehab implementation roles 目前没有第二个语义相同消费者；
- P4A 不发布 Role Pack instance，不创建通用 `BaseAgent`；
- `recommended_reasoning_tier`、model name 或 provider routing 只能作为 executor namespaced hint，不能授予 authority，也不能假设 Codex 当前任务可自动升降推理级别。

## 10. Upgrade and rollback

Upgrade：

1. canonical release commit + manifest 形成候选；
2. independent review 验证 source set、fingerprints、fixtures 和 clean checkout；
3. consumer 项目单独审批 import/update exact paths；
4. consumer adapter/conformance 通过后提交 project-local lock；
5. 不自动修改其他项目，不自动重跑 Campaign。

Rollback：

- consumer pin 回上一个 release manifest/lock；
- project-local runner、state backend 和 authority 始终保留；
- distribution verifier 失败时不删除当前 vendor snapshot；
- approval、task 或 governed content 漂移时 fail closed，不自动回滚或重新批准。

## 11. P4A recommendation

建议批准一个独立 P4A implementation plan，只实现 static distribution contract/tooling。Shared Runtime、standalone repository、package/CLI、plugin/skill、Role Pack 和 consumer rollout 都保留为后续独立 Gate。
