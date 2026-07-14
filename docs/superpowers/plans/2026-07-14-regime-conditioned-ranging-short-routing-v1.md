# Regime-conditioned Ranging-short Routing v1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不执行 Campaign、不创建 Candidate、不运行 Backtest 的前提下，由 Research Director 生成 `regime-conditioned-ranging-short-routing-v1` 中风险 Proposal，dry-run 编译完整 Campaign，并输出中文 Markdown/HTML 人工决策包。

**Architecture:** Research Director 只在 `ranging-short-branch-retention-review-v1` 已关闭且状态为 `closed_mixed_temporal_dependency` 时生成新 Proposal。Campaign Compiler 冻结四个已有 Slice、当前 router 结构、正式策略和治理输入，并把当前执行预算固定为零；独立 preparation builder 生成证据矩阵、审批包和离线 HTML，但不调用任何 Backtest runner。

**Tech Stack:** Python 3.12、JSON/YAML、SQLite Registry、静态 HTML/CSS、`unittest`、PowerShell readiness。

## Global Constraints

- 正式 `ranging_short_entry` 必须保留，不修改正式策略、基类、Candidate、router、阈值或执行配置。
- 当前阶段 Candidate、Backtest、Hyperopt、Validation、Holdout 和 temporal slice 执行预算全部为 0。
- 不得重新开启 `whole_branch_deletion` 或已关闭 threshold 研究。
- 新 Proposal 风险等级为 `medium`，Campaign 状态保持 `pending_human_review`，执行授权为 `false`。
- 人工阅读报告使用简体中文，并同时提供 Markdown 与离线 HTML；机器字段继续使用英文。
- 不 push、不 merge 新研究分支。

---

### Task 1: Director Proposal 与关闭分支约束

**Files:**
- Modify: `scripts/research_director.py`
- Test: `tests/test_regime_conditioned_ranging_short_routing_preparation.py`

**Interfaces:**
- Consumes: `current-research-state.json` 中的 `ranging_short_branch_retention_review` 与 `closed_branches`。
- Produces: `proposal_id=regime-conditioned-ranging-short-routing-v1`、`risk_class=medium`、稳定 `semantic_fingerprint`。

- [x] **Step 1: 写失败测试**

测试调用 `research_director.generate()`，断言 Proposal 只在 retention closure 完成后出现，且不请求整体删除、阈值调整、Validation/Holdout、Candidate 或 Backtest。

- [x] **Step 2: 验证测试失败**

Run: `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe -m unittest tests.test_regime_conditioned_ranging_short_routing_preparation -v`

Expected: Proposal 不存在或 preparation artifacts 不存在。

- [x] **Step 3: 实现最小 Proposal 生成逻辑**

在 `generate()` 中基于 retention closure 添加证据驱动 Proposal，引用 temporal result、closure、router equivalence 和 structure map；方法限定为 read-only routing evidence matrix。

- [x] **Step 4: 验证 Proposal 测试通过**

Run: 同 Step 2。

Expected: Proposal 指纹可复算，关闭分支未重新开启。

### Task 2: Specialized dry-run Campaign Plan

**Files:**
- Modify: `scripts/compile_research_campaign.py`
- Test: `tests/test_regime_conditioned_ranging_short_routing_preparation.py`

**Interfaces:**
- Consumes: Director Proposal、四 Slice temporal result、retention closure、router structure map。
- Produces: `regime_conditioned_routing_plan`，当前预算 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`。

- [x] **Step 1: 写 Campaign 失败测试**

断言 Campaign fingerprint 可复算、`compile_mode=dry_run`、`execution_authorized=false`，并检查 deterministic decision taxonomy、blocked paths、stop conditions 与未来独立审批上限。

- [x] **Step 2: 运行并确认失败**

Run: `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe -m unittest tests.test_regime_conditioned_ranging_short_routing_preparation -v`

- [x] **Step 3: 实现 specialized plan**

增加 `regime_conditioned_ranging_short_routing_plan()`，冻结 s01–s04 结论、single-variable rule、当前零执行预算和未来单独审批 envelope：最多 1 Candidate、16 Development-only Backtests、不得增加 Slice。

- [x] **Step 4: 运行测试确认通过**

Run: 同 Step 2。

### Task 3: 中文 Markdown/HTML 决策包与 Registry

**Files:**
- Create: `scripts/build_regime_conditioned_ranging_short_routing_preparation.py`
- Create: `research/governance/approvals/regime-conditioned-ranging-short-routing-v1-compilation-approval.json`
- Create: `research/analysis/regime-conditioned-ranging-short-routing-v1/routing-evidence-matrix.json`
- Create: `research/director/compiled/regime-conditioned-ranging-short-routing-v1/human-decision-packet.json`
- Create: `reports/research/regime-conditioned-ranging-short-routing-v1-decision-report.md`
- Create: `reports/research/regime-conditioned-ranging-short-routing-v1-decision-report.html`
- Modify: `research/director/current-research-state.json`
- Modify: `research/director/registry-records.json`
- Test: `tests/test_regime_conditioned_ranging_short_routing_preparation.py`

**Interfaces:**
- Consumes: compiled Campaign、Proposal、existing temporal evidence。
- Produces: 中文人工报告、机器 evidence matrix、Registry compilation record；无 execution record。

- [x] **Step 1: 写 artifacts 与中文 HTML 失败测试**

断言 HTML 为 UTF-8、`lang=zh-CN`、无外部 URL、包含 Proposal/Campaign fingerprint、四 Slice、当前零预算、未来人工审批范围；断言 Registry `execution_authorized=0`。

- [x] **Step 2: 验证失败**

Run: `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe -m unittest tests.test_regime_conditioned_ranging_short_routing_preparation -v`

- [x] **Step 3: 实现 builder 并生成 v0**

Builder 调用 Director 与 Compiler 的纯函数，写入 Proposal、Campaign、metadata、queue、evidence matrix、approval、中文 Markdown/HTML，并更新 State/Registry。HTML 使用本地 CSS tokens、响应式 grid、打印样式且无 JavaScript/CDN。

- [x] **Step 4: 运行 builder 与测试**

Run: `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe scripts/build_regime_conditioned_ranging_short_routing_preparation.py`

Run: `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Scripts\python.exe -m unittest tests.test_regime_conditioned_ranging_short_routing_preparation -v`

Expected: 所有 artifacts 生成，Candidate/Backtest/Validation/Holdout 仍为 0。

### Task 4: Guard、完整验证与提交

**Files:**
- Modify: `scripts/guard_harness_diff.js`
- Modify: `docs/superpowers/plans/2026-07-14-regime-conditioned-ranging-short-routing-v1.md`

**Interfaces:**
- Consumes: 本计划全部变更。
- Produces: 逻辑 commit 与干净 worktree。

- [x] **Step 1: 添加精确 Guard allowlist**

仅允许本 Proposal、compiled output、analysis、报告、builder、测试与计划路径。

- [x] **Step 2: 运行全部验证**

Run targeted、`test_research*.py`、Portable baseline、`scripts/run_agent_readiness_checks.ps1`、Registry integrity、protected manifests 与正式策略 hash。

- [x] **Step 3: 精确暂存与审查**

禁止 `git add -A`；逐路径暂存，检查 `git diff --cached --name-only` 和 staged diff。

- [x] **Step 4: 提交并验证 clean status**

Commit: `research: compile regime-conditioned ranging-short routing review`

Expected: `git status --porcelain=v2 --branch` 只有 branch header；不 push、不 merge。
