# Cross-project Harness Protocol P4C ChinaSectorRadar Consumer Rollout Plan

- 日期：`2026-07-15`
- 计划状态：`awaiting_explicit_implementation_approval`
- 第二个 consumer：`ChinaSectorRadar`
- rollout 模式：`vendored_static_release`
- 本轮 consumer writes：`0`
- 本轮 publish / Campaign / shared Runtime：`0`

## 1. 审计结论

P4B 已证明 v0.1 静态分发可以进入第一个 consumer 的主分支，同时保留项目本地 authority 与 runner。下一步应当是 P4C：把同一份静态 Protocol distribution 安装到第二个非 source-project consumer `ChinaSectorRadar`，而不是抽取 shared executable Runtime。

`ChinaSectorRadar` 当前适合进入静态安装计划，但其治理边界比 `rehab-intervention` 更严格：项目仍处于 `H1 Reliability Harness`，当前 readiness 合法地保持 `blocked/1`，并保留四个已登记 H2 业务语义 blocker。P4C 只能验证静态合同的文件身份和映射兼容性，不得改变 H1/H2 状态，不得把 Protocol verifier 的 `passed/0` 解释为项目 readiness、business readiness 或 H2 approval。

本计划只写入 Protocol source 中的本 Markdown 和中文 HTML 阅读副本。未修改 `D:/code/ChinaSectorRadar`，未运行 readiness、daily job、Campaign、数据库、网络、build、部署或市场数据命令。

## 2. 冻结身份

| 身份 | 冻结值 |
| --- | --- |
| Protocol source branch | `codex/btc-mvp-system-p1-integrated` |
| Protocol planning base | `e280c5f1dc60d2f22855aebefdf1e15a8b381eea` |
| P4A candidate commit | `62b38952d482fe079341114e67653be38a7389e2` |
| Canonical 15-file source commit | `6363b7f8352a53cbcd709a4d3d6b5c0bc7ba3b93` |
| Distribution version | `0.1` |
| Fingerprint profile | `sha256-text-lf-v1` |
| Release manifest fingerprint | `sha256:ed033e8bcf3b468baf08cb3d245029517b45931a5ee6359207216dc3456a8dd9` |
| ChinaSectorRadar branch | `main` |
| ChinaSectorRadar base commit | `a8b99c74f43aeb1e34db600bdbd5608a888d2d7f` |
| ChinaSectorRadar status at audit | `clean` |
| rehab-intervention P4B main | `34ff3b8a30e13f06f748cc0673b732f909513b0b` |

P2 的 `china-sector-radar.json` 已绑定相同 consumer base `a8b99c74...`，并保持 `mapped=5`、`derived=3`、`gap=3` 的真实差异：`RoleContract`、`Budget` 和 `RunState` 仍是 gap。任一冻结 commit、release manifest、文件集合、authority 或 consumer base 漂移，都会使未来的 P4C-A implementation approval 失效，必须重新审计。

## 3. Consumer authority 与 H1 边界

P4C 必须保留以下优先级，不创建新的项目 authority：

1. 用户的明确批准和 `AGENTS.md`；
2. `docs/harness/h1_scope.md`；
3. `docs/agent_operating_contract.md`；
4. H1 candidate 与 independent review lifecycle evidence；
5. 项目本地 readiness result。

静态分发不得改写以下事实：

- H1 independent review 在 `main@a8b99c74...` 已通过；
- candidate-time evidence 中 `review.status=pending` 与后来单独提交的 independent review `pass` 是有意保留的生命周期，不得折叠或回填；
- readiness 继续是 `blocked/1`；
- 四个 blocker 继续是 `H1-BLOCKER-FUTURE-VISIBILITY`、`H1-BLOCKER-PREVIOUS-CLOSE`、`H1-BLOCKER-REQUIRED-DATA-NORMAL`、`H1-BLOCKER-STATUS-MISMATCH`；
- `next_allowed_action=request_h2_plan_approval` 不授权执行 H2；
- Phase 9B 继续 parked；
- Protocol mapping 的 gap 不因 vendoring 自动补齐。

因此 P4C implementation 不修改 `AGENTS.md`、现有 H1 scope、task manifest、schemas、readiness scripts、canonical evidence 或 independent review。

## 4. 选定的 consumer model

继续使用 `vendored_static_release`：

- 从 P4A candidate `62b38952...` 的本地 exact checkout 复制 19 个 JSON；
- 完整安装 4 个 distribution metadata 和 15 个 canonical artifacts；
- 创建 ChinaSectorRadar 专用 closed `consumer-lock.json`；
- 使用 project-local、Python standard-library-only verifier；
- 不修改现有 Python package、依赖锁、H1 runner 或 PowerShell readiness 入口；
- 不自动更新，不访问网络，不运行或导入项目业务 Runtime；
- 不复制 P3/P4B approval、Campaign、state、result 或 consumer lock 作为新 authority；
- rollback 只恢复前一 approved consumer commit/lock，不清理项目本地 Runtime 或运行数据。

P4B 的 remediation 必须从一开始进入 P4C 合同：verifier 递归枚举 vendor root，实际集合必须精确等于 lock 加 19 个 target；任何额外文件都返回 `blocked/1 vendor_file_set_mismatch`，任何 symlink、Junction、reparse point 或其他非普通文件都返回 `blocked/1 vendor_entry_not_regular`。

## 5. Exact 24-path implementation surface

只有用户另行明确批准 P4C-A 后，才允许在新的 consumer worktree 修改以下 24 条精确路径：

1. `docs/harness/harness_protocol_distribution.md`
2. `docs/harness/harness_protocol_distribution.zh-CN.html`
3. `scripts/verify_harness_protocol_distribution.py`
4. `tests/test_harness_protocol_distribution.py`
5. `harness/protocol/vendor/v0.1/consumer-lock.json`
6. `harness/protocol/vendor/v0.1/distribution/distribution-manifest.schema.json`
7. `harness/protocol/vendor/v0.1/distribution/fingerprint-profiles.json`
8. `harness/protocol/vendor/v0.1/distribution/fingerprint-test-vectors.json`
9. `harness/protocol/vendor/v0.1/distribution/release-manifest.json`
10. `harness/protocol/vendor/v0.1/protocol/harness-protocol.schema.json`
11. `harness/protocol/vendor/v0.1/protocol/protocol-manifest.json`
12. `harness/protocol/vendor/v0.1/protocol/fixtures/normal.json`
13. `harness/protocol/vendor/v0.1/protocol/fixtures/governed-block.json`
14. `harness/protocol/vendor/v0.1/protocol/fixtures/tool-error.json`
15. `harness/protocol/vendor/v0.1/protocol/fixtures/authority-mismatch.json`
16. `harness/protocol/vendor/v0.1/protocol/fixtures/known-baseline-debt.json`
17. `harness/protocol/vendor/v0.1/mappings/project-mapping.schema.json`
18. `harness/protocol/vendor/v0.1/mappings/mapping-manifest.json`
19. `harness/protocol/vendor/v0.1/mappings/projects/freqtrade-strategies.json`
20. `harness/protocol/vendor/v0.1/mappings/projects/china-sector-radar.json`
21. `harness/protocol/vendor/v0.1/mappings/projects/rehab-intervention.json`
22. `harness/protocol/vendor/v0.1/mappings/fixtures/source-stale.json`
23. `harness/protocol/vendor/v0.1/mappings/fixtures/authority-weakening.json`
24. `harness/protocol/vendor/v0.1/mappings/fixtures/unmapped-gap.json`

禁止用 `harness/**`、`docs/**`、`scripts/**` 或 `tests/**` 代替 exact paths。禁止修改 `AGENTS.md`、`pyproject.toml`、`uv.lock`、`.gitattributes`、现有 H1 harness/evidence、`src/**`、`configs/**`、`db/**`、`data/**`、`logs/**`、`.env*`、Docker、deployment 或 daily-job 文件。禁止 `git add .`、`git add -A`、stash、clean、reset、merge、push 或 PR。

## 6. Consumer lock contract

ChinaSectorRadar 的 `consumer-lock.json` 必须是 closed shape，并至少绑定：

- `lock_version`、`distribution_version`、`distribution_mode` 和 `fingerprint_profile`；
- consumer repository、`main`、base commit `a8b99c74...` 和 clean status；
- Protocol repository、candidate commit `62b38952...` 和 canonical source commit `6363b7f...`；
- release manifest fingerprint；
- ordered 19-file `source_path -> target_path`、fingerprint 和 normalized bytes；
- authority mode `preserve_or_tighten`；
- project-local H1 runner/readiness preserved；
- `auto_update=false` 和完整 invalidation triggers；
- rollback policy；
- `publish_authority=false`、`campaign_authority=false`、`runtime_replacement=false`、`network_access=false`、`data_mutation=false`、`h2_authority=false`。

Unknown、duplicate、missing field，source identity drift、artifact drift、额外文件、非普通文件或 authority weakening 必须是 `blocked/1`；encoding、parser 或 verifier 自身无法可信完成时必须是 `error/2`。

## 7. Implementation tasks

### Task 0 — fresh consumer worktree gate

- 从 `D:/code/ChinaSectorRadar main@a8b99c74...` 创建 `D:/code/ChinaSectorRadar-p4c-static-rollout`；
- 使用 branch `codex/harness-protocol-p4c-static-rollout`；
- 确认 source、China consumer、rehab consumer 全部 exact HEAD/status；
- 确认 24 条 target path 在 base 上均不存在；
- consumer 非 clean、branch/base 漂移、target 预存在或 sibling 漂移时立即停止；
- 不从 operational worktree 读取 `.env`、cache、daily reports 或 secrets。

### Task 1 — vendor static release

- 从 P4A exact candidate checkout 复制 19 个 JSON；
- 不进行项目化内容改写；
- 创建 closed ChinaSectorRadar consumer lock；
- 只暂存 exact Task 1 paths并核对 staged allowlist。

### Task 2 — Python local verifier and tests

- verifier 只允许 Python standard library；
- 不 import `china_sector_radar`、subprocess、socket、HTTP client、database client 或 shell executor；
- 支持 `passed/0`、`blocked/1`、`error/2`；
- 递归验证 exact file set 与 regular-file identity；
- 覆盖 fingerprint、UTF-8、BOM、duplicate keys、CRLF/lone CR、manifest/lock closed shape、authority、drift、extra file 和 symlink/Junction/reparse point；
- 不修改 `pyproject.toml` 或 `uv.lock`。

### Task 3 — project documentation

- 文档明确静态 distribution 与 H1 readiness 是两条不同状态轴；
- 记录 upgrade、rollback、known gaps 和禁止操作；
- 明确 verifier pass 不解除四个 H2 blockers；
- 生成自包含中文 HTML 阅读副本。

### Task 4 — verification and review

- 使用不生成 bytecode/cache 的只读验证方式；
- 运行 focused distribution tests 和现有 full pytest suite；
- 不运行 `scripts/run_agent_readiness_checks.*`，避免把 P4C 误注册为 H1 candidate evidence；
- 不运行 daily job、provider、PostgreSQL、health-check、scheduler、market data、Web、Campaign、network、Docker 或 deployment；
- fresh checkout 复核 exact 24 paths、19 fingerprints、CRLF/LF、recursive file set、reparse-point rejection、H1 evidence zero-diff、protected diff 和 sibling zero-write；
- remediation 只能落在 exact 24 paths 内，之后必须重新复核。

## 8. Verification commands

只有 P4C-A 获批后，才允许在 dedicated worktree 执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
D:\code\ChinaSectorRadar\.venv\Scripts\python.exe scripts\verify_harness_protocol_distribution.py
D:\code\ChinaSectorRadar\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_harness_protocol_distribution.py -q
D:\code\ChinaSectorRadar\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
git diff --check
git status --short --untracked-files=all
```

明确禁止：

```text
scripts/run_agent_readiness_checks.*
scripts/run_daily_job.*
python -m china_sector_radar.cli health-check
database/provider/market-data commands
Campaign / network / browser / Docker / build / deploy
```

## 9. Budgets and protected surfaces

| Budget | Limit |
| --- | ---: |
| Consumer implementation paths | 24 exact paths |
| Vendored JSON files | 19 |
| Canonical artifacts | 15 |
| Consumer worktrees written | 1 dedicated worktree only |
| Original ChinaSectorRadar main writes | 0 |
| Protocol source implementation writes | 0 |
| rehab-intervention writes | 0 |
| H1 evidence/readiness writes | 0 |
| Campaign executions | 0 |
| Network/database/daily-job/build/deploy executions | 0 |
| Business/protected path changes | 0 |

## 10. Rollback

- implementation 未验收：删除 dedicated worktree/branch；`main` 保持不变；
- implementation 已 commit 但未 merge：放弃该 branch，不改 `main`；
- 未来另行批准 merge 后回滚：revert 精确 P4C commits，使上一 approved consumer lock 再次成为 authority；
- 不自动删除 project-local runner、H1 artifacts、operational data、cache、reports 或 secrets；
- 不把 readiness `blocked/1` 当作 P4C rollback 原因，因为这是预期保留的独立状态轴。

## 11. Gate P4C-A

本计划完成后停止。进入 consumer implementation 需要用户明确批准：

> 批准 P4C ChinaSectorRadar static vendoring implementation，绑定 Protocol candidate `62b38952d482fe079341114e67653be38a7389e2`、release manifest fingerprint `sha256:ed033e8bcf3b468baf08cb3d245029517b45931a5ee6359207216dc3456a8dd9`、consumer base `a8b99c74f43aeb1e34db600bdbd5608a888d2d7f`，允许仅修改计划中的 exact 24 paths；不允许修改 H1 authority/readiness/evidence，不允许 publish、Campaign、shared Runtime、H2、business/data/network/build/deployment 或 merge 到 `main`。

“继续”“执行下一步”或对方向的认可不等于 P4C-A implementation approval。

## 12. Gate P4C-B

即使 implementation、verification 和 fresh review 全部通过，也必须再次停止并报告：candidate commit、consumer lock fingerprint、19-file fingerprints、focused/full tests、recursive file-set/reparse tests、H1 evidence zero-diff、protected diff、sibling status 和 rollback。没有新的明确批准，不得 merge 到 `main`、publish、运行 Campaign、执行 H2 或启动 shared Runtime extraction。
