# Cross-Project Harness Protocol P3 第二消费者 Pilot 实施计划

- 日期：2026-07-15
- 计划状态：`awaiting_explicit_implementation_approval`
- Pilot：`rehab-intervention`
- Protocol source：`049fc4b60182bcbaf7a0b01e40522a53d30c2d45`
- Pilot source：`03ca6e841bf3d840307c5c802bb93d637b60b0c0`

## 1. 目标

在不替换 `rehab-intervention` 本地 Campaign runner、不修改业务行为的前提下，完成一次真实、Harness-only、受预算和审批约束的 Protocol v0.1 第二消费者 Pilot。

交付必须回答：

- rehab 能否以 adapter-only 方式消费 Protocol；
- 哪些 P2 映射可以实例化，哪些 gap 必须继续阻断；
- 本地 runner 的 state/exit/evidence 与 Protocol 的差异是什么；
- Core 是否需要修改；
- P4 是否具备提出 runtime extraction decision 的证据。

本计划不预设 P4 结论。

## 2. 两仓库模型

### Protocol source worktree

- 路径：`D:/code/freqtrade-strategies-p1-integration`
- 分支：`codex/btc-mvp-system-p1-integrated`
- 冻结提交：`049fc4b60182bcbaf7a0b01e40522a53d30c2d45`
- P3 中只允许 Task 0 文档和 Pilot 完成后的结果报告；禁止修改 Core schema、mapping schema、fixtures、tests 或 runner。

### Pilot worktree

- source repo：`D:/book/rehab-intervention`
- source branch：`main`
- source commit：`03ca6e841bf3d840307c5c802bb93d637b60b0c0`
- 实施前创建独立 worktree，建议路径：`D:/book/rehab-intervention-p3-protocol-pilot`
- 建议分支：`codex/harness-protocol-p3-pilot`
- `main` 全程只读。

任一冻结身份或 clean status 漂移都停止，不自动 rebase、stash、clean、merge 或刷新 approval。

## 3. Task 0：选择审计与计划

只写 Protocol source worktree 的四个 exact paths：

- `docs/harness/2026-07-15-cross-project-harness-protocol-p3-pilot-selection-audit.md`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p3-pilot-selection-audit.zh-CN.html`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p3-implementation-plan.md`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p3-implementation-plan.zh-CN.html`

Task 0 提交后触发 Approval Gate A，并停止。

## 4. Approval Gate A：实施授权

用户必须明确批准：

- Pilot 项目为 `rehab-intervention`；
- 创建上述独立 worktree/branch；
- 下列 exact write surface；
- vendor snapshot 是一次性 Pilot 方法，不是 P4 distribution decision；
- Task 1–2 只构建 candidate，不执行 Campaign。

“继续”“下一步”不等于 Approval Gate A；需要明确批准本 P3 implementation plan。

## 5. Task 1：冻结 Protocol snapshot

在 Pilot worktree 写入以下 exact paths：

- `harness/protocol/vendor/v0.1/harness-protocol.schema.json`
- `harness/protocol/vendor/v0.1/protocol-manifest.json`
- `harness/protocol/vendor/v0.1/fixtures/normal.json`
- `harness/protocol/vendor/v0.1/fixtures/governed-block.json`
- `harness/protocol/vendor/v0.1/fixtures/tool-error.json`
- `harness/protocol/vendor/v0.1/fixtures/authority-mismatch.json`
- `harness/protocol/vendor/v0.1/fixtures/known-baseline-debt.json`
- `harness/protocol/vendor/v0.1/project-mapping.schema.json`
- `harness/protocol/vendor/v0.1/rehab-intervention.mapping.json`
- `harness/protocol/vendor/v0.1/protocol-lock.json`

前九个文件必须从 Protocol source commit `049fc4b` 对应 canonical files 逐字节复制。`protocol-lock.json` 必须记录：

- Protocol source repository/branch/commit；
- Pilot source repository/branch/commit；
- 每个 vendored file 的 repo-relative source、bytes、SHA-256；
- exact 11 contracts 与 portable exit mapping；
- `distribution_mode: pilot_snapshot`；
- `package_authority: false`；
- `core_mutation_allowed: false`；
- rollback：删除整个 Pilot branch/worktree 即恢复项目本地 Harness。

若 canonical source 漂移、file hash 不匹配或需要复制额外 Runtime，Task 1 为 `blocked`。

## 6. Task 2：构建 adapter candidate

Pilot worktree 的其他 exact paths：

- `harness/protocol/p3/project-binding.json`
- `harness/protocol/p3/pilot-execution-request.json`
- `harness/protocol/p3/pilot-execution-approval.json`
- `harness/protocol/p3/pilot-result.json`
- `harness/campaigns/protocol-pilot.json`
- `scripts/harness-protocol-adapter.mjs`
- `tests/harness-protocol-adapter.test.mjs`
- `docs/quality/protocol-pilot-acceptance.md`
- `docs/quality/protocol-pilot-acceptance.zh-CN.html`

Task 2 candidate 阶段只创建前三者中的 `project-binding.json` 和 `pilot-execution-request.json`，以及 Campaign、adapter 和 tests；`pilot-execution-approval.json`、`pilot-result.json`、acceptance 文档必须在 Approval Gate B 之后按生命周期生成。

### Adapter 边界

`scripts/harness-protocol-adapter.mjs` 只能读取 committed JSON/Markdown 和 ignored Campaign state，不得读取 secret、database、application runtime data 或业务数据。它必须：

- 验证 protocol-lock 和 vendor hashes；
- 验证 source identities；
- 生成/检查一个 project-local `ProjectBinding`；
- 保留 pre-Pilot mapping 的 `RoleContract=gap` 与 `ApprovalRecord=gap`；
- 将本地 runner `completed/failed/blocked` 映射到 Protocol result，同时明确本地 runner 缺少 portable `error=2` 的限制；
- 区分 Harness completion 与 business/product readiness；
- 对 unknown capability、authority mismatch、source drift、gap instance generation 和 Core mutation fail closed；
- 不执行或替换 `scripts/harness-campaign.mjs`。

### Candidate 测试预算

`tests/harness-protocol-adapter.test.mjs` 精确包含 12 个测试：

1. vendor file set/hash；
2. protocol-lock source identities；
3. exact 11-contract order；
4. ProjectBinding required fields；
5. project-local authority precedence；
6. unknown capability blocked；
7. source drift blocked；
8. authority weakening blocked；
9. gap instance generation blocked；
10. local runner state mapping；
11. baseline debt/business readiness preserved；
12. no absolute paths、secret、Runtime import 或 business command。

Task 2 验证：

```powershell
node --test tests/harness-protocol-adapter.test.mjs
node scripts/harness-campaign.mjs validate protocol-pilot
npm run check
git status --short --untracked-files=all
```

禁止 E2E、build、database、network、migration、seed 或 import。

Task 2 candidate 形成精确 commit 后停止，生成 execution request，并触发 Approval Gate B。

## 7. Approval Gate B：Pilot 执行授权

用户必须看到并明确批准：

- candidate commit；
- protocol-lock fingerprint；
- project-binding fingerprint；
- exact Campaign manifest fingerprint；
- changed path count；
- budget、validation commands 和 expected exit mapping；
- business/data/network execution budget 均为 0；
- rollback 和 remaining gaps。

只有 Gate B 批准后，才创建 fingerprint-bound `pilot-execution-approval.json` 并执行 Campaign。Candidate 构建批准不能替代执行批准。

## 8. Task 3：执行本地 Campaign

`harness/campaigns/protocol-pilot.json` 精确包含 3 个 task：

1. `protocol-snapshot-integrity`；
2. `project-binding-conformance`；
3. `failure-semantics-and-evidence`。

Campaign policy：

- `max_attempts: 1`；
- `stop_on_secret: true`；
- `stop_on_scope_violation: true`；
- state file：`harness/state/protocol-pilot.state.json`；
- 每 task `max_seconds <= 60`；
- changed path 只能来自本计划 exact surface；
- network/database/E2E/scheduler/browser/Docker/deployment budget 为 0。

执行命令：

```powershell
node scripts/harness-campaign.mjs run protocol-pilot
node scripts/harness-campaign.mjs status protocol-pilot
```

任何 task failure 都停止；`max_attempts=1`，不得自动重跑。若失败，需要新的人类决定，不得覆盖 state 或伪造 completed。

## 9. Task 4：结果、独立验证与回写

Gate B 后生成：

- `harness/protocol/p3/pilot-execution-approval.json`
- `harness/protocol/p3/pilot-result.json`
- `docs/quality/protocol-pilot-acceptance.md`
- `docs/quality/protocol-pilot-acceptance.zh-CN.html`

结果必须绑定 request、approval、candidate commit、execution commit、Campaign state fingerprint、adapter tests、`npm run check`、protected diff 和 timestamps。

独立 reviewer 必须在 fresh/clean worktree 中验证：

- Protocol snapshot hashes；
- 12/12 adapter tests；
- Campaign state/status；
- project business/protected path diff 为 0；
- Core change count 为 0；
- pre-Pilot gaps 和历史债务未被覆盖；
- no secret/network/database/E2E evidence；
- worktree clean。

Protocol source worktree 只新增最终结果阅读件：

- `docs/harness/2026-07-15-cross-project-harness-protocol-p3-pilot-result.md`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p3-pilot-result.zh-CN.html`

结果报告引用 rehab commit 和 repo-relative evidence paths，不复制 state database、secret、业务数据或 ignored artifacts。

## 10. Core change measurement

P3 的目标值：

- Core schema/code changed files：`0`；
- shared runner/CLI/package/plugin files：`0`；
- project-local adapter files：按本计划 exact surface；
- domain literals added to Core：`0`。

若实现必须修改 `harness/protocol/v0.1/**`、`harness/mappings/v0.1/**` 或 Protocol tests，立即返回 `blocked/core_change_required`，提交设计 amendment，不能在本计划内继续。

## 11. Commit 划分

建议逻辑提交：

### Protocol source

1. `docs: select rehab for P3 protocol pilot`
2. Pilot 完成后：`docs: record P3 protocol pilot result`

### rehab Pilot branch

1. `harness: pin P3 protocol pilot snapshot`
2. `harness: add rehab protocol adapter candidate`
3. Gate B 后：`harness: record approved P3 pilot execution`
4. `docs: accept P3 protocol pilot evidence`
5. review remediation（仅在有 finding 时）

每次只按 exact paths staging，并核对 `git diff --cached --name-only`。禁止 `git add -A`、`git add .`、stash、clean、reset、blind deletion、merge、push 或 PR。

## 12. 明确不做

P3 不做：

- `ChinaSectorRadar` H2 或 H1 replay；
- rehab business/UI/API/auth/database/deployment 改造；
- E2E、migration、seed、import、production validation；
- 通用 Agent orchestration 或 Role Pack；
- shared executable Runtime、CLI、package、plugin、skill；
- P4 ownership/distribution decision；
- 自动执行第二次 Campaign。

## 13. Stop gate

Task 0 完成并提交后停止。只有用户明确批准本 P3 implementation plan，才能创建 rehab Pilot worktree 并开始 Task 1–2；Task 2 candidate 完成后必须再次停止，等待 Gate B 执行批准。
