# Cross-project Harness Protocol P3 Pilot 结果

- 日期：`2026-07-15`
- 状态：`accepted_with_known_gaps`
- 第二消费者：`rehab-intervention`
- Harness completion：`completed`
- Business readiness：`unknown`

## 1. 结论

Harness Protocol v0.1 已完成一次真实的第二消费者 Pilot。`rehab-intervention` 在不替换本地 Campaign runner、不修改业务路径、不修改 Protocol Core 的情况下，通过 project-local adapter 消费了固定 Protocol snapshot，并完成一次由人类明确批准、`max_attempts=1`、业务/数据/网络预算为 0 的 Harness-only Campaign。

P3 结论支持继续讨论 P4 ownership/distribution，但不等于已经批准 shared Runtime、CLI、package、plugin、skill、通用 Agent orchestration 或 Role Pack。

## 2. Repo identities

| 项目 | Commit |
| --- | --- |
| Protocol contract source | `049fc4b60182bcbaf7a0b01e40522a53d30c2d45` |
| P3 plan/result source before this report | `4f05e994ffe0222d87565cc16dc54e33c8532e21` |
| Rehab source | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` |
| Rehab candidate | `6e2d4365cc7b7325441c95d80c24e22e28face89` |
| Execution authority | `4a6423e4124029aa5db97bcbbf901e0aae831930` |
| Fresh-checkout remediation | `84e78d48f25b3611a3da3f148b267c0481da33d3` |
| Rehab final evidence | `5b923a6e0ec745f30cd54304b1db401cce273069` |

## 3. Campaign evidence

- Campaign：`protocol-pilot`
- 实际调用次数：`1`
- Campaign status：`completed`
- Tasks：`3/3 completed`
- 每个 Task attempts：`1`
- Validation commands：`4/4` exit code `0`
- Adapter focused tests：`12/12 passed`
- Candidate/remediation `npm run check`：typecheck passed；ESLint baseline gate passed；Vitest `77 files / 495 tests` passed
- Campaign state semantic fingerprint：`sha256:05fef50a3fb6e3ed66bfad75e5a2437bb8eb08b35ce6dd627dc471ceaaad09ab`
- Approval semantic fingerprint：`sha256:bf6e1771cee3cae3122b8b7b0a15fe11b31274c894a82b7556c7c0efcd3c5bde`
- EvidenceBundle file fingerprint：`sha256:cb67149ae5ccfde2e94507c74f5ef83837fde2ae6134441a68c43292150ec42d`

Repo-relative rehab evidence：

- `harness/protocol/p3/pilot-result.json`
- `docs/quality/protocol-pilot-acceptance.md`
- `docs/quality/protocol-pilot-acceptance.zh-CN.html`

Ignored Campaign state 未复制到 Protocol source。

## 4. 独立复核与 remediation

第一次 fresh Windows checkout 复核给出 `Changes Requested`：`core.autocrlf=true` 把部分 LF JSON 检出为 CRLF，而 adapter 使用 raw-byte SHA，导致相同 Git 内容被误判为 snapshot drift。

Remediation `84e78d48f25b3611a3da3f148b267c0481da33d3` 只修改 rehab adapter/tests，使比较接受同一文本的 LF/CRLF 表示，同时维持 snapshot SHA 与 byte count 成对约束。没有修改 lock、mapping、request、Campaign、approval、业务路径或 Protocol Core，也没有第二次运行 Campaign。

第二次 fresh detached review：`Approved`，无 findings：

- snapshot `9/9`；
- adapter tests `12/12`；
- request bindings `3/3`；
- historical approval bindings `4/4`；
- protected/business diff `0`；
- Protocol Core changes `0`；
- full check `77/495`；
- review worktree clean。

旧 ApprovalRecord 只绑定原 candidate 的一次已完成执行；remediation 后它按 invalidation rule 不再具备未来执行权威。

## 5. Exact surface 与边界

- Rehab 最终 versioned changed paths：`19`
- Rehab protected/business changed paths：`0`
- Protocol Core changed paths：`0`
- Original rehab `main` changed paths：`0`
- Secret/network/database/E2E evidence：`0`
- 自动第二次 Campaign：`0`

未执行：业务逻辑、数据库、网络、浏览器、部署、migration、seed、import、E2E 或 build。

## 6. 保留的兼容性缺口与历史债务

- `role_contract_gap`
- `pre_pilot_approval_record_gap`
- `local_runner_portable_tool_error_semantics_incomplete`
- `exposed_ai_key_rotation_unconfirmed`：仅保留风险状态，不复制敏感值。
- Historical EvidenceBundle 标签：`eslint_locked_baseline_36_errors_30_warnings`
- 当前实际 baseline gate：`29 errors / 10 warnings / 27 resolved`

Harness completion 与 business/product readiness 仍严格分离。

## 7. 对 P4 的含义

P3 已证明“共享 Protocol + project-local adapter + 本地 runner”可以跨项目工作，也证明 raw checkout bytes 不适合作为跨项目文本证据的唯一可移植身份。

P4 若启动，应单独决定：

1. Protocol ownership 与版本发布位置；
2. snapshot/package/plugin/skill 中哪一种分发方式；
3. text fingerprint 的正式规范；
4. Adapter、Agent role contract 与 project binding 的责任边界；
5. 是否仍保留项目本地 runner，还是引入 shared Runtime。

这些均需要新的明确计划和批准；P3 不自动进入 P4。
