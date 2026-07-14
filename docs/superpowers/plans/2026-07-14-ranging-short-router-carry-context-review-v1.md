# Ranging-Short Router Carry Context Review v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 由 Research Director 生成只包含 `ranging_state_without_current_range_signal` 的 medium-risk Proposal，由 Campaign Compiler dry-run 编译完整但不可执行的 Campaign，并输出中文 Markdown/HTML 人工决策包。

**Architecture:** 新增纯数据 `router context contract`，以机器可执行 AST 固定现有 `RegimeDetector` 投票语义和来源哈希。Director 仅在前序 routing preparation 明确返回 `insufficient_router_context_evidence` 后生成新 Proposal；Compiler 验证人工 compilation-only approval、context contract、四个冻结切片和受保护输入，再把当前执行预算强制为零。独立 builder 追加 Registry/State 和中文报告，不调用 Candidate creator、Backtest runner 或任何 sealed-data evaluator。

**Tech Stack:** Python 3.12、JSON/YAML、SQLite、静态 HTML/CSS、`unittest`、Node.js guard、PowerShell readiness。

## Global Constraints

- 唯一 context ID：`ranging_state_without_current_range_signal`。
- context 公式必须严格等于设计文档中的 `regime_4h == ranging AND NOT current_raw_ranging_signal`。
- `current_raw_ranging_signal` 只能复用 `adx_4h < 20` 与 `bb_width_4h <= bb_width_mean_4h OR atr_4h <= atr_mean_4h`，不得新增或搜索阈值。
- 当前预算固定为 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`，`execution_authorized: false`。
- 未来独立审批 envelope 上限为 `1 Candidate / 16 Development-only Backtests / 0 Validation / 0 Holdout`，不得增加时间切片。
- 正式 `RegimeAwareV6`、`regime_aware_base.py`、`regime_detector.py`、正式 router、现有 Candidate、Policy、Runtime、Dataset/Snapshot 均不得修改。
- 不访问 Validation/Holdout，不运行 Backtest、Hyperopt、temporal slice 或 Forward Dry-run。
- 旧 Proposal、旧 Campaign、旧报告和历史 Registry 记录只能引用，不得覆盖。
- 人工报告默认简体中文并同时生成 Markdown 与离线 HTML；机器字段保持英文。
- 不 push、不 merge、不自动执行下一 Campaign。

---

### Task 1: 冻结机器可执行 Router Context Contract

**Files:**
- Create: `scripts/ranging_short_router_context.py`
- Create: `tests/test_ranging_short_router_carry_context_preparation.py`

**Interfaces:**
- Consumes: `strategies/regime_detector.py`、`strategies/regime_aware_base.py`。
- Produces: `build_context_contract(repo: Path) -> dict[str, Any]`、`context_contract_fingerprint(contract: dict[str, Any]) -> str`。

- [ ] **Step 1: 写 contract 失败测试**

在新测试文件中加入：

```python
class RouterCarryContextContractTest(unittest.TestCase):
    def test_contract_freezes_one_runtime_observable_context(self):
        contract = router_context.build_context_contract(ROOT)
        self.assertEqual(contract["context_id"], "ranging_state_without_current_range_signal")
        self.assertEqual(contract["context_count"], 1)
        self.assertEqual(contract["output_regime"], {"column": "regime_4h", "operator": "eq", "value": "ranging"})
        self.assertEqual(
            contract["current_raw_ranging_signal"],
            {
                "all": [
                    {"column": "adx_4h", "operator": "lt", "value": 20},
                    {"any": [
                        {"left": "bb_width_4h", "operator": "lte", "right": "bb_width_mean_4h"},
                        {"left": "atr_4h", "operator": "lte", "right": "atr_mean_4h"},
                    ]},
                ]
            },
        )
        self.assertEqual(contract["context_expression"], {"all": [contract["output_regime"], {"not": contract["current_raw_ranging_signal"]}]})
        self.assertFalse(contract["threshold_search_authorized"])
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation.RouterCarryContextContractTest -v
```

Expected: FAIL，原因是 `ranging_short_router_context` 尚不存在。

- [ ] **Step 3: 创建最小 contract 模块**

模块必须包含以下稳定数据结构和来源验证：

```python
CONTEXT_ID = "ranging_state_without_current_range_signal"

def build_context_contract(repo: Path) -> dict[str, Any]:
    detector = repo / "strategies/regime_detector.py"
    base = repo / "strategies/regime_aware_base.py"
    detector_text = detector.read_text(encoding="utf-8")
    base_text = base.read_text(encoding="utf-8")
    required = (
        "adx < self.adx_range_threshold",
        "(bb_width / bb_width_mean) > 1.0",
        "atr_val > atr_mean",
        'dataframe["regime_4h"] == RegimeDetector.RANGING',
    )
    combined = detector_text + "\n" + base_text
    missing = [snippet for snippet in required if snippet not in combined]
    if missing:
        raise ValueError(f"router_context_source_contract_drift: {missing}")
    raw = {
        "all": [
            {"column": "adx_4h", "operator": "lt", "value": 20},
            {"any": [
                {"left": "bb_width_4h", "operator": "lte", "right": "bb_width_mean_4h"},
                {"left": "atr_4h", "operator": "lte", "right": "atr_mean_4h"},
            ]},
        ]
    }
    output = {"column": "regime_4h", "operator": "eq", "value": "ranging"}
    return {
        "schema_version": "ranging-short-router-context-contract-v1",
        "context_id": CONTEXT_ID,
        "context_count": 1,
        "output_regime": output,
        "current_raw_ranging_signal": raw,
        "context_expression": {"all": [output, {"not": raw}]},
        "source_files": ["strategies/regime_detector.py", "strategies/regime_aware_base.py"],
        "source_sha256": {
            "strategies/regime_detector.py": canonical_text_sha256(detector),
            "strategies/regime_aware_base.py": canonical_text_sha256(base),
        },
        "evaluation_preconditions": ["bb_width_mean_4h > 0", "atr_mean_4h > 0"],
        "threshold_search_authorized": False,
        "time_slice_used_as_regime_label": False,
    }

def context_contract_fingerprint(contract: dict[str, Any]) -> str:
    return fingerprint(contract)
```

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: 与 Step 2 相同。

Expected: contract 测试通过。

- [ ] **Step 5: 精确提交 contract 与测试**

```powershell
git add -- scripts/ranging_short_router_context.py tests/test_ranging_short_router_carry_context_preparation.py
git diff --cached --name-only
git commit -m "research: freeze ranging-short router context contract"
```

---

### Task 2: Research Director 生成新的单 Context Proposal

**Files:**
- Modify: `scripts/research_director.py`
- Modify: `tests/test_ranging_short_router_carry_context_preparation.py`

**Interfaces:**
- Consumes: `regime_conditioned_ranging_short_routing_preparation.recommendation`、retention closure、Task 1 contract。
- Produces: `proposal_id=ranging-short-router-carry-context-review-v1` 与稳定 `semantic_fingerprint`。

- [ ] **Step 1: 写 Director 失败测试**

```python
def test_director_emits_exactly_one_medium_risk_router_context(self):
    run = research_director.generate(
        self.state,
        self.constitution,
        "compile approved ranging-short router carry context",
        {"max_campaigns": 1, "max_wall_clock_minutes": 30, "max_validation_accesses": 0},
        "medium",
        10,
    )
    proposal = next(item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID)
    self.assertEqual(proposal["risk_class"], "medium")
    self.assertEqual(proposal["proposed_method"]["router_context"]["context_id"], CONTEXT_ID)
    self.assertEqual(proposal_fingerprint(proposal), proposal["semantic_fingerprint"])
    self.assertEqual(proposal["estimated_experiments"], 3)
    self.assertNotIn("threshold", proposal["allowed_changes"])
    self.assertIn("validation", proposal["forbidden_changes"])
```

- [ ] **Step 2: 运行并确认 RED**

Run:

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation.RouterCarryProposalTest -v
```

Expected: FAIL，Director 尚未生成新 Proposal。

- [ ] **Step 3: 增加最小 Proposal 分支**

在 `research_director.generate()` 中仅当以下条件全部满足时追加 Proposal：

```python
routing = state.get("regime_conditioned_ranging_short_routing_preparation") or {}
if (
    routing.get("status") == "compiled_pending_human_review"
    and routing.get("recommendation") == "insufficient_router_context_evidence"
    and routing.get("candidate_created") is False
    and routing.get("backtest_calls") == 0
    and routing.get("validation_accesses") == 0
    and routing.get("holdout_accesses") == 0
):
    context = build_context_contract(ROOT)
    proposal = proposal_base(
        "ranging-short-router-carry-context-review-v1",
        "Ranging-short router carry context review",
        "Does ranging_short_entry contribution differ specifically when the router remains ranging without a current raw ranging signal?",
        "Mixed temporal contribution is established, while router-context attribution remains unresolved.",
        supporting_evidence,
        {
            "type": "single_router_context_compilation_only",
            "router_context": context,
            "steps": [
                "freeze the approved router context and source identity",
                "freeze a Development-only context coverage gate",
                "compile a future single-Candidate approval envelope without execution",
            ],
            "execution": "no_candidate_no_backtest_no_validation_no_holdout",
        },
        (0.88, "high", "This isolates the unresolved router-state attribution without reopening threshold or whole-branch deletion research."),
        "medium",
        3,
        30,
        required_datasets,
        runtime,
        policy,
        exact_allowed_paths,
        required_artifacts,
        required_tests,
        ["regime_router", "ranging_short_entry", CONTEXT_ID],
    )
    proposals.append(proposal)
```

`allowed_changes` 只能包含新 Proposal、compiled package、analysis、State/Registry、中文报告、builder、测试和精确 guard 路径。`forbidden_changes` 必须包含 strategy/base/router/Candidate、threshold、Backtest、Validation、Holdout 和 Hyperopt。

- [ ] **Step 4: 运行 Director 与现有 Stage 4A 测试**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation.RouterCarryProposalTest tests.test_stage4a_research_director -v
```

Expected: 新 Proposal 测试和既有 Director 测试全部通过。

- [ ] **Step 5: 精确提交 Director 变更**

```powershell
git add -- scripts/research_director.py tests/test_ranging_short_router_carry_context_preparation.py
git diff --cached --name-only
git commit -m "research: propose ranging-short router carry review"
```

---

### Task 3: Campaign Compiler 冻结不可执行 Spec

**Files:**
- Modify: `scripts/compile_research_campaign.py`
- Modify: `tests/test_ranging_short_router_carry_context_preparation.py`

**Interfaces:**
- Consumes: Task 2 Proposal、Task 1 contract、compilation-only approval、四 Slice temporal evidence。
- Produces: `router_carry_context_plan`、`campaign_fingerprint`、零执行预算。

- [ ] **Step 1: 写 Compiler 失败测试**

```python
def test_compiler_freezes_context_and_zero_execution_budget(self):
    campaign, metadata, brief = compile_research_campaign.compile_campaign(
        ROOT, self.proposal, self.state, self.constitution
    )
    plan = campaign["router_carry_context_plan"]
    self.assertEqual(plan["context_contract"], router_context.build_context_contract(ROOT))
    self.assertEqual(plan["current_execution_budget"], {
        "max_candidates": 0,
        "max_backtest_calls": 0,
        "max_validation_accesses": 0,
        "max_holdout_accesses": 0,
    })
    self.assertEqual(plan["future_separate_approval_envelope"]["max_candidates"], 1)
    self.assertEqual(plan["future_separate_approval_envelope"]["max_backtest_calls"], 16)
    self.assertEqual(plan["future_separate_approval_envelope"]["additional_temporal_slices"], 0)
    self.assertFalse(metadata["execution_authorized"])
    self.assertEqual(fingerprint({k: v for k, v in campaign.items() if k not in {"compiled_at", "campaign_fingerprint"}}), campaign["campaign_fingerprint"])
```

- [ ] **Step 2: 运行并确认 RED**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation.RouterCarryCompilerTest -v
```

Expected: FAIL，Campaign 尚无 `router_carry_context_plan`。

- [ ] **Step 3: 实现专用 Compiler plan**

新增常量和函数：

```python
ROUTER_CARRY_CONTEXT_PROPOSAL_ID = "ranging-short-router-carry-context-review-v1"
ROUTER_CARRY_CONTEXT_APPROVAL = "research/governance/approvals/ranging-short-router-carry-context-review-v1-compilation-approval.json"

def router_carry_context_plan(repo: Path, proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal["proposal_id"] != ROUTER_CARRY_CONTEXT_PROPOSAL_ID:
        return None
    approval = load_document(repo / ROUTER_CARRY_CONTEXT_APPROVAL)
    contract = build_context_contract(repo)
    if proposal["proposed_method"]["router_context"] != contract:
        raise ValueError("router context contract drift")
    if approval.get("proposal_fingerprint") != proposal["semantic_fingerprint"]:
        raise ValueError("router context compilation approval fingerprint mismatch")
    if approval.get("approval_status") != "approved_for_compilation_only" or approval.get("execution_authorized") is not False:
        raise ValueError("router context compilation approval scope mismatch")
    return {
        "context_contract": contract,
        "context_contract_fingerprint": context_contract_fingerprint(contract),
        "slice_policy_fingerprint": temporal["slice_policy_fingerprint"],
        "slice_order": ["s01", "s02", "s03", "s04"],
        "coverage_gate": {
            "required_before_backtest": True,
            "context_pre_gate_intersection_min": 1,
            "both_context_states_required": True,
            "result_independent_selection": True,
        },
        "current_execution_budget": {"max_candidates": 0, "max_backtest_calls": 0, "max_validation_accesses": 0, "max_holdout_accesses": 0},
        "future_separate_approval_envelope": {
            "max_candidates": 1,
            "max_backtest_calls": 16,
            "backtest_formula": "4 frozen Development slices x Baseline/Candidate x RUN-A/RUN-B",
            "additional_temporal_slices": 0,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
            "requires_new_human_execution_approval": True,
        },
    }
```

在 `compile_campaign()` 中调用该函数；命中时把 `campaign["router_carry_context_plan"]` 写入 fingerprint 输入，将 budget 强制更新为零，并生成三条不可执行 queue：冻结 contract、冻结 coverage gate、准备未来人工审批 envelope。

- [ ] **Step 4: 运行 Compiler、旧 routing 和 Stage 4A 回归测试**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation.RouterCarryCompilerTest tests.test_regime_conditioned_ranging_short_routing_preparation tests.test_stage4a_research_director -v
```

Expected: 全部通过；旧 Campaign fingerprint 仍可由其已提交 artifact 重算。

- [ ] **Step 5: 精确提交 Compiler 变更**

```powershell
git add -- scripts/compile_research_campaign.py tests/test_ranging_short_router_carry_context_preparation.py
git diff --cached --name-only
git commit -m "research: compile router carry context review"
```

---

### Task 4: Builder、Registry、中文 Markdown/HTML 与 Guard

**Files:**
- Create: `scripts/build_ranging_short_router_carry_context_preparation.py`
- Modify: `scripts/guard_harness_diff.js`
- Modify: `tests/test_ranging_short_router_carry_context_preparation.py`
- Create: `research/governance/approvals/ranging-short-router-carry-context-review-v1-compilation-approval.json`
- Create: `research/director/next-after-regime-conditioned-ranging-short-routing/proposals/ranging-short-router-carry-context-review-v1.json`
- Create: `research/director/next-after-regime-conditioned-ranging-short-routing/proposals/ranging-short-router-carry-context-review-v1.yaml`
- Create: `research/director/next-after-regime-conditioned-ranging-short-routing/proposals/director-run.json`
- Create: `research/director/compiled/ranging-short-router-carry-context-review-v1/campaign.yaml`
- Create: `research/director/compiled/ranging-short-router-carry-context-review-v1/compilation-metadata.json`
- Create: `research/director/compiled/ranging-short-router-carry-context-review-v1/experiment-queue.json`
- Create: `research/director/compiled/ranging-short-router-carry-context-review-v1/implementation-brief.md`
- Create: `research/director/compiled/ranging-short-router-carry-context-review-v1/human-decision-packet.json`
- Create: `research/analysis/ranging-short-router-carry-context-review-v1/router-context-evidence-matrix.json`
- Create: `reports/research/ranging-short-router-carry-context-review-v1-decision-report.md`
- Create: `reports/research/ranging-short-router-carry-context-review-v1-decision-report.html`
- Modify: `research/director/current-research-state.json`
- Modify: `research/director/current-research-state.md`
- Modify: `research/director/registry-records.json`

**Interfaces:**
- Consumes: Task 2 Proposal、Task 3 Campaign、tracked Registry export。
- Produces: 追加式 dry-run governance package；不得产生 execution record、Candidate 或 results path。

- [ ] **Step 1: 写 artifacts 与中文报告失败测试**

```python
def test_builder_writes_chinese_offline_package_without_execution(self):
    result = builder.build()
    self.assertEqual(result["proposal_id"], PROPOSAL_ID)
    self.assertEqual(result["candidate_count"], 0)
    self.assertEqual(result["backtest_calls"], 0)
    packet = load_document(COMPILED / "human-decision-packet.json")
    self.assertEqual(packet["context_id"], CONTEXT_ID)
    self.assertFalse(packet["execution_authorized"])
    html = REPORT_HTML.read_text(encoding="utf-8")
    self.assertIn('lang="zh-CN"', html)
    self.assertNotRegex(html, r"https?://|<script")
    self.assertIn("当前不执行", html)
    rows = load_document(ROOT / "research/director/registry-records.json")["compiled_campaigns"]
    matching = [row for row in rows if row["proposal_id"] == PROPOSAL_ID]
    self.assertEqual(len(matching), 1)
    self.assertEqual(matching[0]["execution_authorized"], 0)
```

- [ ] **Step 2: 运行并确认 RED**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation.RouterCarryBuilderTest -v
```

Expected: FAIL，builder 与 artifacts 尚不存在。

- [ ] **Step 3: 实现 builder**

Builder 的 `build()` 必须按以下固定顺序执行：

```python
def build() -> dict[str, Any]:
    assert_clean_branch_preflight()
    state = load_document(STATE_PATH)
    constitution = load_document(CONSTITUTION_PATH)
    run = research_director.generate(state, constitution, OBJECTIVE, ZERO_BUDGET, "medium", 10)
    proposal = next(item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID)
    if proposal_fingerprint(proposal) != proposal["semantic_fingerprint"]:
        raise ValueError("proposal fingerprint drift")
    approval = compilation_only_approval(proposal)
    write_json(APPROVAL_PATH, approval)
    campaign, metadata, brief = compile_research_campaign.compile_campaign(ROOT, proposal, state, constitution)
    if metadata["execution_authorized"] or campaign["budget"]["max_backtest_calls"] != 0:
        raise ValueError("dry-run execution boundary violated")
    write_proposal_and_campaign(run, proposal, campaign, metadata, brief)
    matrix = build_context_evidence_matrix(campaign)
    packet = build_human_decision_packet(campaign, matrix)
    write_json(MATRIX_PATH, matrix)
    write_json(PACKET_PATH, packet)
    write_chinese_markdown_and_offline_html(campaign, matrix, packet)
    update_state_append_only(state, campaign, packet)
    update_registry_append_only(run, proposal, campaign, metadata, approval)
    assert_registry_integrity()
    assert_no_execution_candidate_or_results_record()
    return {"proposal_id": PROPOSAL_ID, "proposal_fingerprint": proposal["semantic_fingerprint"], "campaign_fingerprint": campaign["campaign_fingerprint"], "candidate_count": 0, "backtest_calls": 0}
```

State 新字段固定为 `ranging_short_router_carry_context_preparation`。报告必须包含 context 公式、来源哈希、四个旧 Slice 结论、coverage gate、当前零预算、未来独立审批预算和“正式分支保持不变”。HTML 仅使用内联 CSS，不使用 JavaScript、CDN、远程字体或外链。

- [ ] **Step 4: 添加精确 Guard allowlist**

在 `LOW_RISK_SURFACES` 中只增加以下逐文件规则：

```javascript
{ path: "scripts/ranging_short_router_context.py" },
{ path: "scripts/build_ranging_short_router_carry_context_preparation.py" },
{ path: "tests/test_ranging_short_router_carry_context_preparation.py" },
{ path: "research/director/next-after-regime-conditioned-ranging-short-routing/proposals/director-run.json" },
{ path: "research/director/next-after-regime-conditioned-ranging-short-routing/proposals/ranging-short-router-carry-context-review-v1.json" },
{ path: "research/director/next-after-regime-conditioned-ranging-short-routing/proposals/ranging-short-router-carry-context-review-v1.yaml" },
{ path: "research/director/compiled/ranging-short-router-carry-context-review-v1/campaign.yaml" },
{ path: "research/director/compiled/ranging-short-router-carry-context-review-v1/compilation-metadata.json" },
{ path: "research/director/compiled/ranging-short-router-carry-context-review-v1/experiment-queue.json" },
{ path: "research/director/compiled/ranging-short-router-carry-context-review-v1/implementation-brief.md" },
{ path: "research/director/compiled/ranging-short-router-carry-context-review-v1/human-decision-packet.json" },
{ path: "research/analysis/ranging-short-router-carry-context-review-v1/router-context-evidence-matrix.json" },
{ path: "research/governance/approvals/ranging-short-router-carry-context-review-v1-compilation-approval.json" },
{ path: "reports/research/ranging-short-router-carry-context-review-v1-decision-report.md" },
{ path: "reports/research/ranging-short-router-carry-context-review-v1-decision-report.html" },
{ path: "docs/superpowers/specs/2026-07-14-ranging-short-router-carry-context-review-v1-design.md" },
{ path: "docs/superpowers/plans/2026-07-14-ranging-short-router-carry-context-review-v1.md" },
```

不得增加 `reports/research/**`、`research/director/compiled/**` 或 `scripts/build_*` 等宽泛规则。

- [ ] **Step 5: 先提交 builder、测试与精确 Guard**

```powershell
git add -- scripts/build_ranging_short_router_carry_context_preparation.py scripts/guard_harness_diff.js tests/test_ranging_short_router_carry_context_preparation.py
git diff --cached --name-only
git diff --cached --check
git commit -m "research: add router carry preparation builder"
```

Expected: 提交后版本控制工作树干净，随后 builder 的 clean-worktree preflight 才可通过。

- [ ] **Step 6: 运行 builder 与 targeted tests**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' scripts/build_ranging_short_router_carry_context_preparation.py
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation tests.test_regime_conditioned_ranging_short_routing_preparation tests.test_stage4a_research_director -v
```

Expected: Proposal/Campaign fingerprint 可重算；HTML 离线；Registry integrity 为 `ok`；Candidate/Backtest/Validation/Holdout 均为零。

- [ ] **Step 7: 精确提交生成包**

逐路径 `git add -- <exact paths>`，然后：

```powershell
git diff --cached --name-only
git diff --cached --check
git commit -m "research: prepare ranging-short router carry review"
```

暂存列表不得包含 `strategies/**`、`research/candidates/**`、`research/results/**`、数据库、Runtime、Dataset 或 Snapshot 文件。

---

### Task 5: 全量验证与 Clean-Worktree 闭环

**Files:**
- Verify only: all committed paths from Tasks 1–4

**Interfaces:**
- Consumes: 已提交 Proposal/Compiler/report package。
- Produces: 可复核测试证据、最终 commit SHA、干净 worktree；不产生新研究执行。

- [ ] **Step 1: 运行 targeted、Research 与 Stage tests**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_ranging_short_router_carry_context_preparation tests.test_regime_conditioned_ranging_short_routing_preparation tests.test_stage4a_research_director -v
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest discover -s tests -p 'test_research*.py' -v
```

Expected: 所有本次和既有 Research/Stage 测试通过。

- [ ] **Step 2: 运行 Portable full baseline**

```powershell
& '.\.venv-freqtrade\Scripts\python.exe' scripts/verify_test_baseline.py --run --profile clean_worktree_portable
```

Expected: JSON 中 `errors: []` 且 `versioned_worktree_unchanged: true`。

- [ ] **Step 3: 运行 readiness、protected manifest 与 Registry integrity**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_agent_readiness_checks.ps1
& '.\.venv-freqtrade\Scripts\python.exe' -m unittest tests.test_protected_manifest_hash_contract -v
& '.\.venv-freqtrade\Scripts\python.exe' -c "import sqlite3; c=sqlite3.connect('research/registry/stage4a-director.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0])"
```

Expected: 三个 readiness guards 通过；protected hash tests 通过；Registry 输出 `ok`。

- [ ] **Step 4: 验证冻结输入和零执行边界**

```powershell
git diff a4dd06821c98bfe2c44505d1d6ed388a76f4d25f -- strategies/ research/candidates/ research/data/ research/evaluation/ research/runtime/
rg -n 'execution_authorized|max_candidates|max_backtest_calls|max_validation_accesses|max_holdout_accesses' research/director/compiled/ranging-short-router-carry-context-review-v1
git status --short --untracked-files=all
```

Expected: 受保护目录 diff 为空；当前预算全部为零；没有 Candidate、results 或 execution record；工作树干净。

- [ ] **Step 5: 最终报告**

报告以下内容：

- Proposal fingerprint；
- Compiled Campaign fingerprint；
- Context contract fingerprint；
- 唯一 context 公式；
- 当前与未来预算；
- 中文 HTML 报告绝对路径；
- 测试、readiness、Portable baseline、Registry 和冻结哈希结果；
- commit 列表与 clean status；
- 明确“未创建 Candidate、未运行 Backtest、未访问 Validation/Holdout、未 push、未 merge”。
