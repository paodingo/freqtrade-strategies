# Cross-project Harness Protocol P4D Closure and Extraction Re-audit

- 日期：`2026-07-16`
- 审计状态：`completed`
- P4 closure：`completed_static_distribution_only`
- 后续运行模式：`maintenance_observation`
- Shared executable Runtime：`deferred`
- Standalone neutral repository：`deferred`
- Role Pack / generic BaseAgent：`deferred / do_not_create`
- 本轮 consumer writes / Campaign / publish：`0 / 0 / 0`

## 1. 结论

P1 至 P4C 已经证明以下模型可以跨三个项目成立：共享版本化 Protocol contracts、项目映射、静态分发 manifest/fingerprint、project-local consumer lock，以及各项目自行保留 authority、runner、state、failure semantics 和领域边界。P4 可以按 `static_distribution_only` 正式收口。

当前证据不支持抽取 shared executable Runtime、standalone repository、通用 `BaseAgent` 或 Role Pack。原因不是静态分发失败，而是执行层仍缺少第二个非 source-project 的真实 governed Protocol Pilot，两个 consumer 仍使用不同语言、runner、state 和风险模型，且尚未发生任何 consumer upgrade cycle 或 rollback rehearsal。

因此，本跨项目抽象工作进入 `maintenance_observation`：v0.1 继续由现有 Protocol source 孵化维护；不自动升级 consumer，不启动 P5，不把项目本地 Agent/Role instance 上移到 Core。后续只有触发条件满足时，才重新进行 extraction audit。

本轮仅写入 Protocol source 的本 Markdown 与中文 HTML 阅读副本。未修改 `freqtrade-strategies-clean`、`rehab-intervention` 或 `ChinaSectorRadar`，未运行 Campaign、H2、业务、数据、网络、build、部署或发布命令。

## 2. 当前冻结证据

| 项目/证据 | 当前身份 | 审计结果 |
| --- | --- | --- |
| Protocol planning source | `codex/btc-mvp-system-p1-integrated@dbe60e4398998c3750d590ff4751a5403bc2fc52` | clean |
| Canonical project state | `codex/btc-mvp-system-harnessed@fc621f1deee152689a2d79b3099a5da581486144` | clean |
| P4A candidate | `62b38952d482fe079341114e67653be38a7389e2` | source verifier `passed/0` |
| Canonical 15-file source | `6363b7f8352a53cbcd709a4d3d6b5c0bc7ba3b93` | frozen |
| Release manifest | `sha256:ed033e8bcf3b468baf08cb3d245029517b45931a5ee6359207216dc3456a8dd9` | verified |
| rehab P3 Pilot | `codex/harness-protocol-p3-pilot@5b923a6e0ec745f30cd54304b1db401cce273069` | clean; governed Pilot completed |
| rehab consumer main | `main@34ff3b8a30e13f06f748cc0673b732f909513b0b` | clean; static verifier `passed/0` |
| China consumer main | `main@32a7024c2948560e0e781a0dd847abc8d9cb4449` | clean; static verifier `passed/0` |

两个 consumer 均锁定 distribution `0.1`、19 个 vendored JSON、15 个 canonical artifacts 和相同 release manifest。consumer lock 中的 `consumer.source_commit` 是安装前 base，不是安装后 commit 的自引用：

- rehab base：`03ca6e841bf3d840307c5c802bb93d637b60b0c0`；
- China base：`a8b99c74f43aeb1e34db600bdbd5608a888d2d7f`。

当前没有 tag 或网络发布证据；v0.1 仍是 source-controlled incubation distribution，而不是 package、CLI、plugin、skill 或 shared service。

## 3. P1–P4 完成矩阵

| Phase | 目标 | 结果 |
| --- | --- | --- |
| P1 | 定义 language-neutral Protocol Core | `completed` |
| P2 | 冻结三个 project mapping descriptors 与 fail-closed gaps | `completed` |
| P3 | 在第二项目执行一次真实 governed Pilot | `completed_in_rehab_only` |
| P4A | 建立 deterministic static distribution contract/tooling | `completed` |
| P4B | 安装到 rehab consumer main | `completed` |
| P4C | 安装到 China consumer main | `completed_with_known_consumer_baseline_debt` |
| P4D | 关闭 P4 并重新评估 extraction | `completed_static_distribution_only` |

P4 closure 只说明静态共享层成立，不说明三个项目共享同一执行 Runtime，也不把 consumer 的 business readiness 或 phase readiness 改写为通过。

## 4. 已证明可共享的层

以下内容已跨三个项目或两个非 source consumer 形成稳定证据：

- 11 个 Protocol contracts 的 language-neutral schema；
- authority precedence 与 explicit human approval；
- exact/narrow path permissions 和 deny-unknown；
- `passed/blocked/error` 与 `0/1/2` portable outcome；
- Harness completion 与 business readiness 分离；
- known baseline debt 不得隐藏；
- ProjectBinding/mapping descriptor 与显式 gap；
- ApprovalRecord/EvidenceBundle 的 contract shape；
- synthetic fixtures、manifest、normalized fingerprint；
- project-local consumer lock、no auto-update、explicit rollback；
- extra-file、symlink、Junction/reparse point fail-closed verification。

这些是静态 contracts 与治理语义，不要求 consumer 使用同一语言或执行引擎。

## 5. 继续留在项目本地的层

以下内容仍属于 project adapter/runner，不进入 shared Runtime：

- command execution、shell/runtime selection；
- retry、lease、resume 与 state persistence；
- project capability registry；
- Research/market/provider/auth/session/database/deployment 语义；
- phase-specific Agent/Role instances；
- model provider、reasoning tier 与 executor routing；
- business readiness、H1/H2、Validation/Holdout 等项目门禁；
- operational data、evidence lifecycle 和 rollback mechanics。

三个项目当前差异仍然是架构事实：

| 项目 | Local execution/control plane | Mapping gaps |
| --- | --- | --- |
| freqtrade-strategies | Python deterministic research control plane | `0` |
| rehab-intervention | Node.js Campaign runner；project-local state/retry/resume | `RoleContract`, `ApprovalRecord` |
| ChinaSectorRadar | Python + PowerShell H1 readiness/evidence harness | `RoleContract`, `Budget`, `RunState` |

## 6. Governed Pilot 判断

真实 governed Protocol Pilot 数量仍是 `1`：

- rehab：有 explicit approval、ProjectBinding、adapter、Campaign execution、GateResult/EvidenceBundle 和 completed result；
- China：只有 static distribution verification，没有 Protocol adapter execution、Campaign 或新 RunState；
- freqtrade-strategies：是 Protocol incubation/source project，不计作非 source consumer Pilot。

China 的 verifier `passed/0` 与项目 H1 readiness `blocked/1` 是独立状态轴。它不能被提升为第二次 Pilot，也不能授权 H2。当前 China authority 的下一步仍是 `request_h2_plan_approval`，不是 Protocol Pilot execution。

## 7. Standalone repository trigger re-audit

| 触发条件 | 当前状态 | 判断 |
| --- | --- | --- |
| 至少两个非 source consumer 完成真实 governed Pilot | rehab `1`；China static-only | `not_met` |
| 至少两个 release cycle 无 domain-driven Core change | 仅有 v0.1 首次安装；无 upgrade cycle | `not_met` |
| publisher/reviewer/versioning/security/rollback owner 明确 | 仅有 v0.x incubation owner 与项目级 review | `partial` |
| consumer upgrade 不依赖 sibling-repo checkout | P4B/P4C 均从本地 exact source checkout 安装 | `not_met` |
| migration plan 保留 project-local authority | 两个 consumer lock 均 preserve/tighten | `met` |

结论：standalone neutral repository 继续 `deferred`。现在拆仓只会增加 ownership、release、sync、security 和 rollback 治理，而不会消除任何已证明的执行耦合。

## 8. Shared Runtime trigger re-audit

| 条件 | 当前状态 | 判断 |
| --- | --- | --- |
| 两个非 source consumer 通过同一 Runtime 执行 | rehab local Node；China local Python/PowerShell | `not_met` |
| RoleContract 可在至少两个 consumer 表达同一语义 | 两个 consumer 均为 gap，且角色语义不同 | `not_met` |
| RunState/lease/retry backend 等价 | rehab 有 local state；China RunState gap | `not_met` |
| portable tool-error semantics 完整 | static verifier 完整；project runner 仍不等价 | `partial` |
| shared Runtime rollback 已演练 | 没有 shared Runtime，也没有跨 consumer rollback rehearsal | `not_met` |
| extraction 不削弱 project authority | 设计上可约束，但尚无 execution evidence | `unproven` |

结论：shared executable Runtime 继续 `deferred`，当前不创建 package、CLI、service、plugin 或 Runtime dependency。

## 9. Agent 与 Role Pack 决策

- Core 继续只定义 `RoleContract` contract，不定义通用角色实例；
- Freqtrade Researcher/Critic/Director 继续属于 Freqtrade domain；
- rehab implementation/task roles 继续属于 rehab；
- China reviewer/coordinator/H1 roles 继续属于 China；
- 不创建通用 `BaseAgent`；
- 不发布 Role Pack；
- model name、provider 或 reasoning level 只能是 executor namespaced hint，不能授予 authority；
- 在出现第二个语义相同的 role consumer 前，不抽取角色模板。

## 10. v0.1 maintenance policy

进入 `maintenance_observation` 后：

1. canonical owner 继续是 exact `paodingo/freqtrade-strategies` source commit + release manifest；
2. consumer 不自动更新，也不通过 sibling checkout 自动同步；
3. Core change 必须先证明是跨项目 contract change，而不是 domain request；
4. consumer upgrade 必须有新版本、新 manifest、新 lock 和项目级明确批准；
5. static verifier failure 不自动删除或回滚当前 snapshot；
6. 不自动重跑 P3 Campaign；
7. 不为了“收集样本”强行把 China 或其他项目改造成 Pilot；
8. known baseline debt 保持可见，不通过共享层隐藏或修复。

## 11. 各项目下一步

P4D 不为各项目自动创建任务：

- `freqtrade-strategies`：继续自己的研究治理路线；Protocol 只做低频维护；
- `rehab-intervention`：回到产品/质量路线；无需因 P4D 再运行 Campaign；
- `ChinaSectorRadar`：若用户希望推进，应另行制定 H2 plan；P4D 不授权 H2 或业务修复。

项目工作不需要等待 shared Runtime，也不应为了满足 extraction 指标制造不自然的通用性。

## 12. Future P5 entry gate

只有下列证据同时出现，才允许提出 P5 extraction implementation plan：

1. 第二个非 source consumer 完成真实、独立批准的 governed Protocol Pilot；
2. 至少两个 versioned release/upgrade cycle 完成且无 domain-driven Core change；
3. 至少一个 consumer rollback rehearsal 有 committed evidence；
4. upgrade 不再依赖 sibling-repo checkout 或人工复制；
5. publisher、reviewer、versioning、security、rollback owner 明确；
6. 至少两个 consumer 对同一 Runtime/Role/RunState 语义给出等价证据；
7. extraction plan 证明不会替换 project-local authority、runner 或 state backend。

即使触发条件满足，也必须先做新的 read-only extraction audit；不得从本 P4D 文档直接推导 implementation approval。

## 13. Stop condition

P4D 到此完成。当前 cross-project Harness Protocol 的下一状态是：

```text
P4 = completed_static_distribution_only
Protocol v0.1 = maintenance_observation
P5 = not_started
shared Runtime = deferred
standalone repository = deferred
new P4D Campaign executions = 0
```

除非未来触发条件出现或用户另行指定新的审计问题，本路线不继续扩张抽象层。
