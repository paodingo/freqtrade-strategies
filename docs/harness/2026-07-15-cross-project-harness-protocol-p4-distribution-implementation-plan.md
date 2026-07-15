# Cross-project Harness Protocol P4A Distribution Implementation Plan

- 日期：`2026-07-15`
- 计划状态：`awaiting_explicit_implementation_approval`
- 决策：`static_distribution_only`
- Shared executable Runtime：`out_of_scope`
- Sibling project writes：`0`
- Network/data/business execution：`0`

## 1. 目标

在 Protocol source 中实现一个 language-neutral、可复现、可独立验证的 v0.1 static distribution contract。它只发布 contracts、mapping descriptors、synthetic fixtures 和 release metadata，不替换任何项目 runner，也不安装或发布 package。

## 2. Approval Gate A

P4 Task 0 的“继续执行”只授权本审计和本计划，不授权下列 P4A implementation paths。开始 P4A 前，用户必须明确批准：

- `static_distribution_only` 决策；
- canonical v0.x incubation owner；
- exact 12-path write surface；
- Python 只作为 source-side build/verify tooling；
- no sibling writes、no publish、no consumer rollout、no shared Runtime。

## 3. Exact implementation write surface

仅允许：

1. `harness/distribution/v0.1/distribution-manifest.schema.json`
2. `harness/distribution/v0.1/fingerprint-profiles.json`
3. `harness/distribution/v0.1/fingerprint-test-vectors.json`
4. `harness/distribution/v0.1/release-manifest.json`
5. `scripts/build_harness_protocol_distribution.py`
6. `scripts/verify_harness_protocol_distribution.py`
7. `tests/test_harness_protocol_distribution_contracts.py`
8. `tests/test_harness_protocol_distribution_reproducibility.py`
9. `scripts/guard_harness_diff.js`
10. `docs/harness/change_surface_matrix.md`
11. `docs/harness/harness-protocol-distribution-policy.md`
12. `docs/harness/harness-protocol-distribution-policy.zh-CN.html`

禁止使用 `harness/**`、`docs/**`、`scripts/build_*` 等宽泛授权；staging 必须逐路径核对。

## 4. Frozen canonical input surface

Builder 只允许读取现有 15 个 source artifacts：

### Protocol Core component（7）

- `harness/protocol/v0.1/harness-protocol.schema.json`
- `harness/protocol/v0.1/protocol-manifest.json`
- `harness/protocol/v0.1/fixtures/normal.json`
- `harness/protocol/v0.1/fixtures/governed-block.json`
- `harness/protocol/v0.1/fixtures/tool-error.json`
- `harness/protocol/v0.1/fixtures/authority-mismatch.json`
- `harness/protocol/v0.1/fixtures/known-baseline-debt.json`

### Mapping component（8）

- `harness/mappings/v0.1/project-mapping.schema.json`
- `harness/mappings/v0.1/mapping-manifest.json`
- `harness/mappings/v0.1/projects/freqtrade-strategies.json`
- `harness/mappings/v0.1/projects/china-sector-radar.json`
- `harness/mappings/v0.1/projects/rehab-intervention.json`
- `harness/mappings/v0.1/fixtures/source-stale.json`
- `harness/mappings/v0.1/fixtures/authority-weakening.json`
- `harness/mappings/v0.1/fixtures/unmapped-gap.json`

任何新增输入、路径重命名或 Core content change 都必须停止并请求新计划。

## 5. Task 1 — Distribution contracts

创建：

- closed JSON Schema for release manifest；
- `sha256-text-lf-v1` profile descriptor；
- LF/CRLF、lone CR、BOM、invalid UTF-8、duplicate JSON key、content drift test vectors；
- source component、artifact identity、release identity、consumer lock 和 invalidation rules。

Manifest 必须包含：

- `distribution_version`
- `protocol_version`
- `mapping_version`
- `source_repository`
- `source_commit`
- `fingerprint_profile`
- ordered `components`
- ordered `artifacts`
- `scope`
- `upgrade_policy`
- `rollback_policy`

Unknown field、duplicate path、absolute path、backslash path、missing component、unknown profile 和 fingerprint mismatch 必须 fail closed。

## 6. Task 2 — Source-side builder and verifier

### Builder

`build_harness_protocol_distribution.py`：

- 只读取 frozen 15-file input surface；
- 明确 UTF-8/no-BOM 和 EOL normalization；
- 拒绝 symlink、directory、duplicate JSON keys 和 source set drift；
- 输出 deterministic `release-manifest.json`；
- 不修改 source artifacts；
- 不写 sibling repo；
- 不创建 archive、tag、release 或 network request。

### Verifier

`verify_harness_protocol_distribution.py`：

- 验证 manifest schema、ordered file set、bytes/profile/fingerprints；
- 验证 Protocol P1 与 Mapping P2 manifest relationship；
- 验证无 project Runtime import、绝对路径、secret material 或 domain Core drift；
- portable exit：`0=passed`、`1=blocked`、`2=error`；
- 不执行 consumer command 或 Campaign。

构建和验证可使用 source repository 已锁定的 Python 3.12/jsonschema 环境；consumer release artifacts 仍为静态 JSON/Markdown。

## 7. Task 3 — Tests

保持两个测试文件、精确 16 个 P4A tests：

### Contract tests（8）

1. manifest schema is valid Draft 2020-12；
2. exact closed manifest shape；
3. exact ordered 15-file source set；
4. exact component membership；
5. repo-relative POSIX paths only；
6. version/source commit are bound；
7. scope excludes Runtime/package/plugin/skill/publish；
8. unknown/duplicate/missing fields fail closed。

### Reproducibility tests（8）

1. LF and CRLF produce same profile fingerprint；
2. lone CR normalizes to LF；
3. BOM is rejected；
4. invalid UTF-8 is error；
5. duplicate JSON keys are rejected；
6. content drift changes fingerprint；
7. independent builds produce byte-identical manifest；
8. builder/verifier import no project Runtime and perform no network/sibling writes。

P1+P2+P4A focused total must be `50/50`。

## 8. Task 4 — Documentation and independent review

Distribution policy 必须说明：

- v0.x canonical owner 与 release-by-commit；
- Protocol content、mapping descriptors 与 project authority 的优先级；
- consumer vendoring/lock/upgrade/rollback；
- historical fingerprint profiles 不被追溯改写；
- local runner/state/roles 保持 project-owned；
- neutral repo、Runtime、package/CLI、plugin/skill、Role Pack 仍未批准。

Independent reviewer 必须使用 fresh detached worktree 验证：

- exact 12 implementation paths；
- exact 15 input files；
- P4A 16/16；focused 50/50；
- readiness 三项通过；
- full baseline 无新增 failure；
- Linux/LF 与 Windows/CRLF test vectors；
- protected/trading/business diff `0`；
- sibling repo HEAD/status 未变化；
- worktree clean。

## 9. Verification commands

```powershell
& .\.venv-freqtrade\Scripts\python.exe -B -m unittest `
  tests.test_harness_protocol_guard_contract `
  tests.test_harness_protocol_contracts `
  tests.test_harness_protocol_conformance `
  tests.test_harness_project_mapping_guard `
  tests.test_harness_project_mapping_contracts `
  tests.test_harness_project_mapping_conformance `
  tests.test_harness_protocol_distribution_contracts `
  tests.test_harness_protocol_distribution_reproducibility -v
& .\scripts\run_agent_readiness_checks.ps1
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv-freqtrade\Scripts\python.exe -B scripts/verify_test_baseline.py --run --profile clean_worktree_portable
Remove-Item Env:PYTHONDONTWRITEBYTECODE
git diff --check
git status --short --untracked-files=all
```

如果 dedicated worktree 使用外部已验证 Python，报告必须记录 exact executable identity；不得搜索 PATH、安装或更新依赖。

## 10. Budget and forbidden operations

| Budget | Limit |
| --- | ---: |
| implementation changed paths | 12 |
| canonical input files | 15 |
| P4A tests | 16 |
| external/network calls | 0 |
| sibling writes | 0 |
| data/database access | 0 |
| Campaign/runtime executions | 0 |
| automatic retries after governed failure | 0 |

禁止：

- 创建/发布 Git tag、GitHub release、package、CLI、plugin、skill 或新 repository；
- 修改三个 consumer repository；
- 导入或运行 consumer Runtime；
- 运行 backtest、daily job、rehab Campaign、E2E、database、scheduler、deployment；
- 修改 Protocol Core、P2 mapping descriptor 或 P3 evidence；
- 自动决定 P4B consumer rollout。

## 11. Commits and staging

建议精确 commits：

1. `feat: define harness protocol distribution contracts`
2. `feat: add deterministic protocol distribution verifier`
3. `docs: record harness protocol distribution policy`

每次只 stage 当前 task exact paths，并核对：

```powershell
git diff --cached --name-only
git diff --cached --check
```

禁止 `git add .`、`git add -A`、stash、clean、reset、blind deletion、merge、push 或 PR。

## 12. Approval Gate B — Publish or consumer rollout

P4A candidate 完成、独立复核通过后必须再次停止。用户必须看到并批准：

- exact candidate commit；
- release manifest fingerprint；
- source commit/source set；
- test/readiness/baseline results；
- rollback policy；
- target consumer 与 exact write paths。

Gate B 之前不得发布 tag/release、复制到 sibling repo、更新 consumer lock 或执行任何 consumer Campaign。

## 13. Stop gate

本 P4 Task 0 完成并提交后停止在 Approval Gate A。只有用户明确批准本 P4A implementation plan，才进入 12-path implementation；“继续”“下一步”或对 P4 概念的认可不等于 implementation approval。
