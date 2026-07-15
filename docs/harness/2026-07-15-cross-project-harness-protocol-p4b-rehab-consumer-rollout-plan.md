# Cross-project Harness Protocol P4B rehab-intervention Consumer Rollout Plan

- 日期：`2026-07-15`
- 计划状态：`awaiting_explicit_implementation_approval`
- 首个 consumer：`rehab-intervention`
- rollout 方式：`vendored_static_release`
- 本轮 consumer writes：`0`
- 本轮 publish / Campaign / shared Runtime：`0`

## 1. 审计结论

`rehab-intervention` 适合作为 P4B 首个 consumer，但 P4B 必须是一次新的静态分发安装，不能把 P3 Pilot 分支整体合并到 `main`，也不能复用 P3 的一次性 execution approval、Campaign state 或 result/evidence 作为新执行权威。

推荐方案是：从 clean `rehab-intervention main` 建立专用 worktree/branch，完整 vendoring P4A v0.1 的 15 个 canonical artifacts 与 4 个 distribution metadata 文件，新增一个 consumer lock、一个 project-local 静态 verifier 和对应 tests。项目现有 `scripts/harness-campaign.mjs` 保持原样；不引入 shared Runtime、CLI、package、plugin、skill、Role Pack 或网络下载。

本计划仅写入 Protocol source 中的本文件及中文 HTML 阅读副本。未修改 `D:/book/rehab-intervention`，未运行 Campaign，也未执行 `npm`、E2E、数据库、build 或 deployment 命令。

## 2. 冻结身份

| 身份 | 冻结值 |
| --- | --- |
| Protocol source branch | `codex/btc-mvp-system-p1-integrated` |
| P4A candidate commit | `62b38952d482fe079341114e67653be38a7389e2` |
| Canonical 15-file source commit | `6363b7f8352a53cbcd709a4d3d6b5c0bc7ba3b93` |
| Distribution version | `0.1` |
| Fingerprint profile | `sha256-text-lf-v1` |
| Release manifest fingerprint | `sha256:ed033e8bcf3b468baf08cb3d245029517b45931a5ee6359207216dc3456a8dd9` |
| Consumer source branch | `main` |
| Consumer source commit | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` |
| Consumer source status | `clean` |
| P3 final evidence commit | `5b923a6e0ec745f30cd54304b1db401cce273069` |

P4A distribution metadata 的 `sha256-text-lf-v1` 绑定：

| Source path | Fingerprint | Normalized bytes |
| --- | --- | ---: |
| `harness/distribution/v0.1/distribution-manifest.schema.json` | `sha256:70507d138a20b4616761dbabf3505cd90ae7194d8e599862644efe02978dacda` | 4114 |
| `harness/distribution/v0.1/fingerprint-profiles.json` | `sha256:a01682e9fa7f8bc57bd85a6464837e88039cdbfab9d903b85c281d92628186a5` | 490 |
| `harness/distribution/v0.1/fingerprint-test-vectors.json` | `sha256:160c6cd779bfd0a9d6023d0a04e474bdffc51482f46337df1eb9e47a5efa8cdb` | 1977 |
| `harness/distribution/v0.1/release-manifest.json` | `sha256:ed033e8bcf3b468baf08cb3d245029517b45931a5ee6359207216dc3456a8dd9` | 6320 |

任一 commit、status、fingerprint、文件集合或 authority 漂移，都使本计划的 implementation approval 请求失效，必须重新审计。

## 3. Consumer authority 审计

当前 `rehab-intervention main` 的权威优先级保持：

1. `AGENTS.md` 的 mandatory rules；
2. `docs/quality/quality-baseline.md` 的项目 baseline；
3. `harness/campaigns/phase2.json` 的 phase scope；
4. `docs/quality/phase2-campaign-acceptance.md` 的历史 state evidence。

Static Protocol distribution 只能提供兼容合同和映射描述，不能覆盖项目 policy、human approval 或本地 runner。P2 mapping 的 `mapped=3`、`derived=6`、`gap=2` 继续保留；特别是：

- `RoleContract=gap` 不因 vendoring 自动补齐；
- pre-Pilot `ApprovalRecord=gap` 不被 P3 approval 追溯改写；
- `local_runner_portable_tool_error_semantics_incomplete` 继续可见；
- ignored Campaign state 不提升为 committed truth；
- 当前 `main` 的 locked ESLint baseline 仍是 authority，不用 P3 branch 上后来的数字覆盖它；
- previously exposed AI key rotation risk 只保留风险状态，不复制或打印 secret。

## 4. P3 可复用结论与禁止复用内容

P3 已证明：共享 Protocol + project-local adapter + local runner 能工作，并发现 raw checkout bytes 不能作为跨 Windows LF/CRLF 的唯一文本身份。P4A 已用 `sha256-text-lf-v1` 正式解决该问题。

P4B 可复用：

- repo-relative path 和 deny-unknown 规则；
- project authority 高于 shared contract 的原则；
- local runner 不替换；
- CRLF/LF portable fingerprint 测试方法；
- fresh detached independent review 流程。

P4B 禁止复制或重新激活：

- `harness/protocol/p3/pilot-execution-approval.json`；
- `harness/protocol/p3/pilot-execution-request.json`；
- `harness/protocol/p3/pilot-result.json`；
- `harness/campaigns/protocol-pilot.json`；
- ignored `harness/state/protocol-pilot.state.json`；
- P3 acceptance/evidence 作为新的 rollout approval；
- P3 `pilot_snapshot` lock 中已被 P4A 替代的 source commit 和 raw fingerprint 语义。

## 5. 选定的 consumer model

`vendored_static_release` 具有以下约束：

- 19 个 vendored JSON 文件来自 exact P4A candidate checkout，不从网络获取；
- 15 个 canonical artifacts 完整安装，不做未定义的 consumer subset projection；
- source paths 与 target paths 由 `consumer-lock.json` 一一绑定；
- verifier 使用 `sha256-text-lf-v1`，拒绝 BOM、invalid UTF-8、duplicate JSON keys、unknown profile、absolute path、missing/extra/duplicate artifacts 和 fingerprint drift；
- verifier 仅允许 Node built-ins `node:crypto`、`node:fs`、`node:path`、`node:url`，不得 import project Runtime 或 `node:child_process`；
- `scripts/harness-campaign.mjs`、业务代码、数据库、auth、deployment 与 existing Campaign files 不修改；
- 不自动更新；升级必须产生新的 consumer lock 和新的显式批准；
- rollback 通过恢复前一个 approved consumer commit/lock 完成，不自动清理 project-local Runtime。

## 6. P4B exact 26-path implementation surface

只有在用户另行明确批准 P4B implementation 后，才允许在新的 consumer worktree 修改以下精确路径：

1. `AGENTS.md`
2. `package.json`
3. `docs/quality/harness-protocol-distribution.md`
4. `docs/quality/harness-protocol-distribution.zh-CN.html`
5. `scripts/verify-harness-protocol-distribution.mjs`
6. `tests/harness-protocol-distribution.test.mjs`
7. `harness/protocol/vendor/v0.1/consumer-lock.json`
8. `harness/protocol/vendor/v0.1/distribution/distribution-manifest.schema.json`
9. `harness/protocol/vendor/v0.1/distribution/fingerprint-profiles.json`
10. `harness/protocol/vendor/v0.1/distribution/fingerprint-test-vectors.json`
11. `harness/protocol/vendor/v0.1/distribution/release-manifest.json`
12. `harness/protocol/vendor/v0.1/protocol/harness-protocol.schema.json`
13. `harness/protocol/vendor/v0.1/protocol/protocol-manifest.json`
14. `harness/protocol/vendor/v0.1/protocol/fixtures/normal.json`
15. `harness/protocol/vendor/v0.1/protocol/fixtures/governed-block.json`
16. `harness/protocol/vendor/v0.1/protocol/fixtures/tool-error.json`
17. `harness/protocol/vendor/v0.1/protocol/fixtures/authority-mismatch.json`
18. `harness/protocol/vendor/v0.1/protocol/fixtures/known-baseline-debt.json`
19. `harness/protocol/vendor/v0.1/mappings/project-mapping.schema.json`
20. `harness/protocol/vendor/v0.1/mappings/mapping-manifest.json`
21. `harness/protocol/vendor/v0.1/mappings/projects/freqtrade-strategies.json`
22. `harness/protocol/vendor/v0.1/mappings/projects/china-sector-radar.json`
23. `harness/protocol/vendor/v0.1/mappings/projects/rehab-intervention.json`
24. `harness/protocol/vendor/v0.1/mappings/fixtures/source-stale.json`
25. `harness/protocol/vendor/v0.1/mappings/fixtures/authority-weakening.json`
26. `harness/protocol/vendor/v0.1/mappings/fixtures/unmapped-gap.json`

禁止用 `harness/**`、`docs/**`、`scripts/**` 或 `tests/**` 代替 exact paths。禁止 `git add .`、`git add -A`、stash、clean、reset、merge、push 或 PR。

## 7. Consumer lock contract

`consumer-lock.json` 必须是 closed shape，并至少绑定：

- `lock_version`、`distribution_version`、`fingerprint_profile`；
- consumer repository/branch/base commit；
- Protocol source repository/candidate commit/canonical source commit；
- release manifest fingerprint；
- ordered 19-file `source_path -> target_path` 映射、fingerprint 与 normalized bytes；
- authority mode `preserve_or_tighten`；
- `project_local_runner_preserved=true`；
- `auto_update=false`；
- invalidation triggers；
- rollback commit/lock policy；
- `publish_authority=false`、`campaign_authority=false`、`runtime_replacement=false`。

Unknown/duplicate/missing field、source identity drift、artifact drift 或 authority weakening 必须是 `blocked/1`；parser/encoding/tool failure 必须是 `error/2`。

## 8. Implementation tasks and commits

### Task 0 — fresh consumer worktree gate

- 从 `D:/book/rehab-intervention main@03ca6e8...` 创建新的 `codex/harness-protocol-p4b-static-rollout` worktree；
- 确认 source、consumer、P3 evidence repos 全部 exact HEAD/status；
- consumer gate 非 clean、branch/base 漂移或 26 个目标路径任一预存在时立即停止；
- 不 merge P3 branch。

### Task 1 — vendor static release

- 从 P4A candidate `62b38952...` 复制 exact 19 JSON 文件；
- 保留文本内容，不进行项目化改写；
- 创建 closed `consumer-lock.json`；
- commit：`feat: vendor harness protocol static distribution v0.1`。

### Task 2 — local verification

- 新增 source-side/local-only Node verifier；
- 新增精确 14 项 tests；
- `package.json` 只增加 `harness:protocol:verify` script，不新增依赖、不更新 lockfile；
- commit：`test: verify vendored harness protocol distribution`。

### Task 3 — project documentation

- `AGENTS.md` 只增加 distribution doc 和静态 verify 入口；
- 文档明确 authority、upgrade、rollback、历史债务及禁止操作；
- commit：`docs: record rehab harness protocol distribution lock`。

### Task 4 — verification and independent review

- 运行静态 verifier、14 项 focused tests 和 `npm run check`；
- 不运行 Campaign、E2E、build、database、seed、import、migration、network 或 deployment；
- fresh detached reviewer 复核 exact 26 paths、19 fingerprints、CRLF checkout、baseline、protected diff 和 sibling zero-write；
- remediation 只能在 exact 26 paths 内，之后必须重新复核。

## 9. Exact 14-test contract

1. distribution metadata 4/4 fingerprints match；
2. canonical artifacts 15/15 fingerprints and bytes match；
3. source-to-target mapping is exact, ordered and unique；
4. LF and CRLF normalize to the same fingerprint；
5. lone CR normalizes to LF；
6. UTF-8 BOM is rejected；
7. invalid UTF-8 is `error/2`；
8. duplicate JSON keys are rejected；
9. release manifest binds exact source commit/profile/components；
10. consumer lock is closed and binds exact consumer/source identities；
11. `AGENTS.md` remains first project authority and authority weakening is blocked；
12. local runner is preserved and verifier imports no Runtime/network/process executor；
13. source/artifact drift blocks without auto-update；
14. P3 approval, request, Campaign state and result are not rollout authority or vendored inputs。

## 10. Verification commands

Future implementation approval 之后才允许执行：

```powershell
node --check scripts/verify-harness-protocol-distribution.mjs
node --test tests/harness-protocol-distribution.test.mjs
npm run harness:protocol:verify
npm run check
git diff --check
git status --short --untracked-files=all
```

明确禁止：

```text
node scripts/harness-campaign.mjs run ...
npm run test:e2e:local
npm run test:e2e
npm run build
npm run verify
npm run db:*
prisma migrate / db push / seed
network / browser / Docker / deploy
```

注意：当前 `scripts/harness-campaign.mjs validate` 在加载 Campaign 时也会创建 state directory/state，因此 P4B static verification 不复用该命令。

## 11. Budgets and protected surfaces

| Budget | Limit |
| --- | ---: |
| Consumer implementation paths | 26 exact paths |
| Vendored JSON files | 19 |
| Canonical artifacts | 15 |
| Focused tests | 14 |
| Consumer worktrees written | 1 dedicated worktree only |
| Original consumer main writes | 0 |
| Protocol source implementation writes | 0 |
| P3 evidence writes | 0 |
| Campaign executions | 0 |
| Network/database/E2E/build/deploy executions | 0 |
| Business/protected path changes | 0 |

Protected paths include `src/**`、`prisma/**`、`data/**`、`.env*`、deployment files、existing Campaign definitions/runner/state、auth/session、AI key handling、business docs/evidence 和 P3 artifacts。

## 12. Rollback

- implementation 未验收：删除专用 worktree/branch；consumer `main` 保持不变；
- implementation 已 commit 但未 merge：丢弃该独立 branch，不改 consumer `main`；
- 未来若另行批准 merge 后回滚：revert 精确 P4B commits，使 previous approved consumer lock 再次成为 authority；
- 不自动删除项目本地 runner、state、baseline 或 business artifacts；
- 不用 P3 branch 替代 rollback point。

## 13. Approval Gate P4B-A

本计划完成后停止。进入 consumer implementation 需要用户明确批准：

> 批准 P4B rehab-intervention static vendoring implementation，绑定 Protocol candidate `62b38952d482fe079341114e67653be38a7389e2`、release manifest fingerprint `sha256:ed033e8bcf3b468baf08cb3d245029517b45931a5ee6359207216dc3456a8dd9`、consumer base `03ca6e841bf3d840307c5c802bb93d637b60b0c0`，允许仅修改计划中的 exact 26 paths；不允许 publish、Campaign、shared Runtime、business/data/network/E2E/build/deployment 或 merge 到 main。

“继续”“执行下一步”或对方向的认可不等于 P4B-A implementation approval。

## 14. Approval Gate P4B-B

即使 implementation、验证和独立复核全部通过，也必须再次停止并报告：candidate commit、consumer lock fingerprint、19-file fingerprints、14/14 tests、`npm run check`、protected diff、sibling status、rollback。没有新的显式批准，不得 merge 到 `main`、publish、运行 Campaign 或扩展到第二 consumer。
