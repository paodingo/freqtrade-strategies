# Cross-Project Harness Protocol P2 实施计划

- 日期：2026-07-15
- 计划状态：`awaiting_explicit_implementation_approval`
- 依赖：Protocol P1 `fc621f1deee152689a2d79b3099a5da581486144`

## 1. 目标

实现一个 language-neutral、只读、fail-closed 的项目映射层，使三个项目能够声明其当前 Harness 概念如何对应 Protocol v0.1 的 11 个 contract，同时保留项目本地 authority、禁止项、known debt、状态新鲜度和证据分裂。

本计划交付 mapping descriptors，不交付共享 Runtime 或可执行 Adapter。

## 2. 实施前重新冻结

执行前必须重新核对以下身份；任一 commit 或 clean status 变化都停止并重新审计：

| project_id | approved audit commit |
| --- | --- |
| `freqtrade-strategies` | `fc621f1deee152689a2d79b3099a5da581486144` |
| `china-sector-radar` | `a8b99c74f43aeb1e34db600bdbd5608a888d2d7f` |
| `rehab-intervention` | `03ca6e841bf3d840307c5c802bb93d637b60b0c0` |

兄弟仓库全程只读。所有版本化写入只发生在 `codex/btc-mvp-system-p1-integrated` 的独立 clean worktree。

## 3. 计划写入面

### Task 0：审计与计划

精确文件：

- `docs/harness/2026-07-15-cross-project-harness-protocol-p2-mapping-audit.md`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p2-mapping-audit.zh-CN.html`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p2-implementation-plan.md`
- `docs/harness/2026-07-15-cross-project-harness-protocol-p2-implementation-plan.zh-CN.html`

### Task 1：exact-path guard

精确文件：

- `scripts/guard_harness_diff.js`
- `docs/harness/change_surface_matrix.md`
- `tests/test_harness_project_mapping_guard.py`

Guard 只能授权本计划列出的 mapping files 和 tests；不得授权 `harness/mappings/**`、`tests/**` 或 sibling repo wildcard。

### Task 2：mapping schema、manifest 与三项目 descriptor

精确文件：

- `harness/mappings/v0.1/project-mapping.schema.json`
- `harness/mappings/v0.1/mapping-manifest.json`
- `harness/mappings/v0.1/projects/freqtrade-strategies.json`
- `harness/mappings/v0.1/projects/china-sector-radar.json`
- `harness/mappings/v0.1/projects/rehab-intervention.json`
- `tests/test_harness_project_mapping_contracts.py`

`project-mapping.schema.json` 至少要求：

- `mapping_version`、`protocol_version`、`project_id`；
- `source_repository_identity`、`source_commit`、`source_branch`；
- `authority_precedence`；
- exact 11-contract coverage；
- 每个 contract 的 `mapping_status`、`source_refs`、`transformation`、`preserved_rules`、`gaps`；
- `forbidden_inferences`、`refreshed_at`。

所有 object 必须 `additionalProperties: false`。`source_refs` 必须是 normalized POSIX repo-relative paths；descriptor 不得包含本机绝对路径。

### Task 3：failure conformance

精确文件：

- `harness/mappings/v0.1/fixtures/source-stale.json`
- `harness/mappings/v0.1/fixtures/authority-weakening.json`
- `harness/mappings/v0.1/fixtures/unmapped-gap.json`
- `tests/test_harness_project_mapping_conformance.py`

必须证明：

- source commit 漂移是 `blocked`，不是自动刷新；
- authority weakening 是 `blocked`；
- unknown capability 在 `deny_unknown` 下是 `blocked`；
- `gap` 不能生成 contract instance；
- missing source 是 `blocked`，解析器/环境失败是 `error`；
- business readiness 与 Harness completion 不互相覆盖；
- ChinaSectorRadar 的 H1.1 review pass、blocked readiness、四个 H2 blocker 与 candidate/reviewer lifecycle split 保持可见；
- rehab local ignored state 不被宣称为 portable authority；
- freqtrade 不同 timestamp 的 state/approval 不被合并成一个新鲜快照。

### Task 4：隔离与整体验证

只修改 Task 1–3 已列文件，不增加 CLI、runner、Adapter code 或 sibling writes。

## 4. 测试预算

P2 新增测试方法精确为 18 个：

- guard：2；
- contracts：8；
- conformance：8。

最终 focused suite 应为：

- Protocol P1：16；
- Project Mapping P2：18；
- 合计：34。

测试只能使用 Python standard library、`jsonschema` 和 frozen JSON fixtures；不得 import project Runtime，不得访问 network、database、scheduler、browser、Docker 或 secret。

## 5. Descriptor 语义

### `mapped`

当前权威来源直接表达目标 contract 语义。Descriptor 仍只记录映射，不复制业务数据。

### `derived`

必须列出所有 source refs、确定性 transformation 和 freshness rule。任何 source 缺失、commit 漂移或时间冲突都 fail closed。

### `gap`

必须列出缺失字段和安全影响。`gap` 不得被默认值填成 `mapped`，也不得生成 approval、role、budget、state 或 readiness 的假 artifact。

## 6. Authority 防弱化规则

- project-local forbidden capability 永远覆盖 Core allow；
- human approval requirement 不得由 mapping 自动满足；
- protected path 不得因共享 path category 变成 allowed；
- known baseline debt 必须保留原始 blocker/evidence reference；
- project-local `blocked` 不得因 Harness structure 完整而改写为 `passed`；
- Role Pack 缺失不影响 mapping completion，但必须保持 `gap`。

## 7. 验证命令

实施后运行：

```powershell
.\.venv-freqtrade\Scripts\python.exe -B -m unittest `
  tests.test_harness_protocol_guard_contract `
  tests.test_harness_protocol_contracts `
  tests.test_harness_protocol_conformance `
  tests.test_harness_project_mapping_guard `
  tests.test_harness_project_mapping_contracts `
  tests.test_harness_project_mapping_conformance -v
.\scripts\run_agent_readiness_checks.ps1
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv-freqtrade\Scripts\python.exe -B scripts/verify_test_baseline.py --run --profile clean_worktree_portable
Remove-Item Env:PYTHONDONTWRITEBYTECODE
git status --short --untracked-files=all
```

验收要求：

- focused `34/34`；
- readiness 三项通过；
- full baseline 不出现 P2 新 failure；既有 `missing=0:extra=418` 只能原样披露，不得清理或隐藏；
- sibling repo HEAD/status 与冻结前一致；
- versioned worktree clean；
- 独立 reviewer 对完整 P2 range 给出 `Approved`。

## 8. Commit 与 review 划分

建议逻辑提交：

1. `docs: audit cross-project P2 mappings`
2. `harness: authorize exact P2 mapping surface`
3. `harness: add read-only project mapping descriptors`
4. `test: prove P2 mapping failure semantics`
5. review remediation（仅在 reviewer 有 finding 时）

每个 Task 使用 exact-path staging，并在提交前核对 `git diff --cached --name-only`。禁止 `git add -A`、`git add .`、stash、clean 或 sibling commit。

## 9. 明确不做

P2 不做：

- shared executable Runtime；
- project-local runner replacement；
- generic Agent orchestration；
- Role Pack extraction；
- model/provider API；
- database、network、scheduler、trading、deployment；
- P3 pilot selection or execution；
- P4 package/repository decision。

## 10. Stop gate

Task 0 完成后停止。只有用户明确批准本计划，才能开始 Task 1；“继续”“下一步”不得解释为对 sibling writes、Runtime、P3 或 P4 的授权。
