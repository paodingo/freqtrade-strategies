#!/usr/bin/env python3
"""Build the approved router-carry compilation package without execution."""

from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path
from typing import Any

import compile_research_campaign
import research_director
from build_regime_conditioned_ranging_short_routing_preparation import (
    _restore_registry_from_export,
)
from export_director_registry import export_registry
from ranging_short_router_context import context_contract_fingerprint
from research_control import load_campaign
from research_director_common import (
    fingerprint,
    load_document,
    proposal_fingerprint,
    utc_now,
    write_json,
    write_yaml,
)


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_ID = "ranging-short-router-carry-context-review-v1"
PROPOSAL_DIR = (
    ROOT
    / "research/director/next-after-regime-conditioned-ranging-short-routing/proposals"
)
COMPILED_DIR = ROOT / "research/director/compiled" / PROPOSAL_ID
ANALYSIS_DIR = ROOT / "research/analysis" / PROPOSAL_ID
REPORT_DIR = ROOT / "reports/research"
APPROVAL_PATH = (
    ROOT
    / "research/governance/approvals/"
    "ranging-short-router-carry-context-review-v1-compilation-approval.json"
)
STATE_PATH = ROOT / "research/director/current-research-state.json"
STATE_MD_PATH = ROOT / "research/director/current-research-state.md"
REGISTRY_PATH = ROOT / "research/registry/stage4a-director.db"
REGISTRY_EXPORT_PATH = ROOT / "research/director/registry-records.json"
CONSTITUTION_PATH = ROOT / "research/governance/research-constitution.yaml"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def assert_clean_branch_preflight() -> None:
    branch = _git("branch", "--show-current")
    if branch != "research/regime-conditioned-ranging-short-routing-v1":
        raise ValueError(f"unexpected preparation branch: {branch}")
    status = _git("status", "--porcelain=v2", "--untracked-files=all")
    changed = [line for line in status.splitlines() if not line.startswith("#")]
    if changed:
        raise ValueError("preparation_worktree_not_clean")


def _approval(proposal: dict[str, Any], created_at: str) -> dict[str, Any]:
    return {
        "schema_version": "research-proposal-compilation-approval-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "approval_status": "approved_for_compilation_only",
        "approver_type": "human_user",
        "approval_source": "approved_router_carry_context_design_and_spec",
        "execution_authorized": False,
        "candidate_creation_authorized": False,
        "backtest_authorized": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "approved_at": created_at,
    }


def _matrix(campaign: dict[str, Any]) -> dict[str, Any]:
    plan = campaign["router_carry_context_plan"]
    return {
        "schema_version": "ranging-short-router-context-evidence-matrix-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": campaign["proposal_fingerprint"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "context_id": plan["context_contract"]["context_id"],
        "context_contract": plan["context_contract"],
        "context_contract_fingerprint": plan["context_contract_fingerprint"],
        "slice_policy_fingerprint": plan["slice_policy_fingerprint"],
        "slice_order": plan["slice_order"],
        "slice_conclusions": plan["slice_conclusions"],
        "coverage_gate": plan["coverage_gate"],
        "current_budget": plan["current_execution_budget"],
        "future_separate_approval_envelope": plan[
            "future_separate_approval_envelope"
        ],
        "formal_branch_status": "retained_unchanged",
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "time_slice_used_as_regime_label": False,
    }


def _packet(campaign: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    plan = campaign["router_carry_context_plan"]
    return {
        "schema_version": "ranging-short-router-context-human-decision-packet-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": campaign["proposal_fingerprint"],
        "compiled_campaign_fingerprint": campaign["campaign_fingerprint"],
        "risk_class": "medium",
        "approval_status": "pending_human_execution_review",
        "execution_authorized": False,
        "context_id": plan["context_contract"]["context_id"],
        "context_contract_fingerprint": plan["context_contract_fingerprint"],
        "evidence_matrix_fingerprint": fingerprint(matrix),
        "coverage_gate": plan["coverage_gate"],
        "current_budget": plan["current_execution_budget"],
        "future_separate_approval_envelope": plan[
            "future_separate_approval_envelope"
        ],
        "formal_branch_status": "retained_unchanged",
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "next_human_decisions": [
            "review the frozen Proposal and Campaign fingerprints",
            "review the exact single-variable Candidate identity and diff allowlist",
            "separately authorize at most one Candidate and 16 Development-only Backtests",
        ],
        "insufficient_for": [
            "creating a Candidate",
            "running a Backtest",
            "accessing Validation or Holdout",
            "modifying or deleting formal ranging_short_entry",
        ],
    }


def _markdown(campaign: dict[str, Any], packet: dict[str, Any]) -> str:
    plan = campaign["router_carry_context_plan"]
    context = plan["context_contract"]
    future = packet["future_separate_approval_envelope"]
    return f"""# Ranging-short Router Carry Context 人工决策报告

## 当前结论

已冻结唯一运行时 context：`{context['context_id']}`。

该 context 表示正式 router 输出 `ranging`，但当前 4h candle 的 ADX、BB width 与 ATR 原始投票并未直接形成 ranging signal。它可能来自 hysteresis 状态保持或初始化状态；本报告不把所有命中样本武断归类为 hysteresis。

## 精确公式

```text
regime_4h == "ranging"
AND NOT (
  adx_4h < 20
  AND (
    bb_width_4h <= bb_width_mean_4h
    OR atr_4h <= atr_mean_4h
  )
)
```

评价前置条件为 `bb_width_mean_4h > 0` 和 `atr_mean_4h > 0`。阈值全部来自现有 `RegimeDetector`，没有进行 threshold search。

## 冻结身份

- Proposal fingerprint：`{campaign['proposal_fingerprint']}`
- Compiled Campaign fingerprint：`{campaign['campaign_fingerprint']}`
- Context contract fingerprint：`{packet['context_contract_fingerprint']}`
- Slice Policy fingerprint：`{plan['slice_policy_fingerprint']}`

## 四个既有切片

- `s01`：`inconclusive`
- `s02`：`positive_contributor`
- `s03`：`negative_contributor`
- `s04`：`negative_contributor`

时间切片只用于未来稳定性比较，不作为 market regime 标签。

## 当前不执行

当前预算为 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`。正式 `ranging_short_entry`、`RegimeDetector`、router、阈值和执行配置均保持不变。

未来如另获明确人工执行批准，上限为 `1 Candidate / {future['max_backtest_calls']} Development-only Backtests / 0 Validation / 0 Holdout`，复用四个冻结切片且不得增加第五个切片。Backtest 前必须通过 context coverage gate。
"""


def _html(campaign: dict[str, Any], packet: dict[str, Any]) -> str:
    plan = campaign["router_carry_context_plan"]
    context_id = html.escape(packet["context_id"])
    proposal_fp = html.escape(campaign["proposal_fingerprint"])
    campaign_fp = html.escape(campaign["campaign_fingerprint"])
    context_fp = html.escape(packet["context_contract_fingerprint"])
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ranging-short Router Context 人工决策</title>
<style>
:root{{--paper:#f5f2e8;--ink:#18211d;--muted:#647069;--green:#173f35;--teal:#2e7169;--amber:#a86718;--line:#d7d1c2;--card:#fffdf7}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei","Segoe UI",sans-serif;line-height:1.65}}
main{{max-width:1040px;margin:auto;padding:48px 24px 72px}}header{{border-top:6px solid var(--green);border-bottom:1px solid var(--line);padding:30px 0}}
h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.12;margin:.4rem 0}}h2{{margin-top:36px}}.eyebrow{{color:var(--teal);font-weight:700;letter-spacing:.08em}}
.status,.card{{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:18px}}.status{{border-left:5px solid var(--amber);margin:22px 0}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}code{{font-family:Consolas,monospace;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;background:#e9eee9;padding:18px;border-radius:8px}}
dt{{color:var(--muted);font-size:.82rem}}dd{{margin:4px 0 0;font-weight:700;overflow-wrap:anywhere}}footer{{margin-top:44px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted)}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}}main{{padding:28px 16px 48px}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}}}
</style></head><body><main>
<header><div class="eyebrow">RESEARCH HARNESS · 人工决策</div><h1>Router 保持 ranging，但当前投票不再支持 ranging</h1><p>单一 context 的 compilation-only 冻结包</p></header>
<section class="status"><h2>当前不执行</h2><p>Candidate、Backtest、Validation、Holdout 均为 0；正式策略和 router 保持不变。</p></section>
<section><h2>唯一 Context</h2><p><code>{context_id}</code></p><pre>regime_4h == "ranging"
AND NOT (adx_4h &lt; 20 AND (bb_width_4h &lt;= bb_width_mean_4h OR atr_4h &lt;= atr_mean_4h))</pre></section>
<section><h2>冻结身份</h2><div class="grid"><div class="card"><dt>Proposal</dt><dd>{proposal_fp}</dd></div><div class="card"><dt>Campaign</dt><dd>{campaign_fp}</dd></div><div class="card"><dt>Context Contract</dt><dd>{context_fp}</dd></div></div></section>
<section><h2>证据边界</h2><p>四个既有切片为 s01 inconclusive、s02 positive、s03/s04 negative。时间切片不作为 market regime 标签；未来执行仍需新的明确人工授权和 coverage gate。</p></section>
<footer>离线静态中文报告 · 不加载外部字体、脚本或网络资源</footer>
</main></body></html>'''


def _update_registry(
    run: dict[str, Any],
    proposal: dict[str, Any],
    campaign: dict[str, Any],
    metadata: dict[str, Any],
    approval: dict[str, Any],
    created_at: str,
) -> str:
    connection = _restore_registry_from_export()
    connection.execute(
        "INSERT OR REPLACE INTO director_runs(run_id,state_fingerprint,objective,risk_tolerance,budget_json,recommendation,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            run["run_id"],
            run["state_fingerprint"],
            run["objective"],
            run["risk_tolerance"],
            json.dumps(run["budget"], sort_keys=True),
            run["recommendation"],
            json.dumps(run, sort_keys=True),
            run["created_at"],
        ),
    )
    connection.execute(
        "INSERT OR REPLACE INTO director_proposals(proposal_id,run_id,semantic_fingerprint,risk_class,information_gain,status,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            PROPOSAL_ID,
            run["run_id"],
            proposal["semantic_fingerprint"],
            "medium",
            proposal["expected_information_gain"]["score"],
            "approved_for_compilation_only",
            json.dumps(proposal, sort_keys=True),
            created_at,
        ),
    )
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id,proposal_fingerprint,approval_status,approver_type,approved_at,payload_json) VALUES(?,?,?,?,?,?)",
        (
            PROPOSAL_ID,
            proposal["semantic_fingerprint"],
            "approved_for_compilation_only",
            "human_user",
            created_at,
            json.dumps(approval, sort_keys=True),
        ),
    )
    connection.execute("DELETE FROM compiled_campaigns WHERE proposal_id=?", (PROPOSAL_ID,))
    connection.execute(
        "INSERT OR REPLACE INTO compiled_campaigns(compilation_id,proposal_id,campaign_id,campaign_fingerprint,compile_mode,execution_authorized,referenced_hashes_json,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            f"compile-{campaign['campaign_fingerprint'][:16]}",
            PROPOSAL_ID,
            campaign["campaign_id"],
            campaign["campaign_fingerprint"],
            "dry_run",
            0,
            json.dumps(metadata["referenced_hashes"], sort_keys=True),
            json.dumps(campaign, sort_keys=True),
            created_at,
        ),
    )
    connection.commit()
    executions = connection.execute(
        "SELECT COUNT(*) FROM research_campaign_runs WHERE proposal_id=?",
        (PROPOSAL_ID,),
    ).fetchone()[0]
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if executions != 0:
        raise ValueError("unexpected router context execution record")
    if integrity != "ok":
        raise ValueError("Registry integrity check failed")
    write_json(REGISTRY_EXPORT_PATH, export_registry(str(REGISTRY_PATH)))
    return integrity


def build() -> dict[str, Any]:
    assert_clean_branch_preflight()
    state = load_document(STATE_PATH)
    constitution = load_document(CONSTITUTION_PATH)
    run = research_director.generate(
        state,
        constitution,
        "compile approved ranging-short router carry context",
        {
            "max_campaigns": 1,
            "max_wall_clock_minutes": 30,
            "max_validation_accesses": 0,
        },
        "medium",
        10,
    )
    proposal = next(item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID)
    if proposal_fingerprint(proposal) != proposal["semantic_fingerprint"]:
        raise ValueError("proposal fingerprint drift")

    created_at = utc_now()
    approval = _approval(proposal, created_at)
    write_json(APPROVAL_PATH, approval)
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PROPOSAL_DIR / "director-run.json", run)
    write_json(PROPOSAL_DIR / f"{PROPOSAL_ID}.json", proposal)
    write_yaml(PROPOSAL_DIR / f"{PROPOSAL_ID}.yaml", proposal)

    campaign, metadata, brief = compile_research_campaign.compile_campaign(
        ROOT, proposal, state, constitution
    )
    budget = campaign["budget"]
    if metadata["execution_authorized"] or any(
        budget.get(key) != 0
        for key in (
            "max_candidates",
            "max_backtest_calls",
            "max_validation_accesses",
            "max_holdout_accesses",
        )
    ):
        raise ValueError("dry-run execution boundary violated")
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    write_yaml(COMPILED_DIR / "campaign.yaml", campaign)
    write_json(COMPILED_DIR / "experiment-queue.json", campaign["experiment_queue"])
    write_json(COMPILED_DIR / "compilation-metadata.json", metadata)
    (COMPILED_DIR / "implementation-brief.md").write_text(brief, encoding="utf-8")
    load_campaign(COMPILED_DIR / "campaign.yaml")

    matrix = _matrix(campaign)
    packet = _packet(campaign, matrix)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ANALYSIS_DIR / "router-context-evidence-matrix.json", matrix)
    write_json(COMPILED_DIR / "human-decision-packet.json", packet)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"{PROPOSAL_ID}-decision-report.md").write_text(
        _markdown(campaign, packet), encoding="utf-8"
    )
    (REPORT_DIR / f"{PROPOSAL_ID}-decision-report.html").write_text(
        _html(campaign, packet), encoding="utf-8"
    )

    state["ranging_short_router_carry_context_preparation"] = {
        "status": "compiled_pending_human_execution_review",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "context_id": packet["context_id"],
        "context_contract_fingerprint": packet["context_contract_fingerprint"],
        "risk_class": "medium",
        "campaign_executed": False,
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "evidence": [
            f"research/analysis/{PROPOSAL_ID}/router-context-evidence-matrix.json",
            f"research/director/compiled/{PROPOSAL_ID}/human-decision-packet.json",
        ],
    }
    state["generated_at"] = created_at
    state["git"] = {
        "branch": _git("branch", "--show-current"),
        "head": _git("rev-parse", "HEAD"),
        "versioned_worktree_clean": True,
        "versioned_worktree_clean_at_preparation_preflight": True,
    }
    state["state_fingerprint"] = fingerprint(
        {
            key: value
            for key, value in state.items()
            if key not in {"generated_at", "state_fingerprint", "snapshot_id"}
        }
    )
    state["snapshot_id"] = f"research-state-{state['state_fingerprint'][:16]}"
    write_json(STATE_PATH, state)
    STATE_MD_PATH.write_text(
        f"""# 当前研究状态

- 当前准备项：`{PROPOSAL_ID}`
- Proposal fingerprint：`{proposal['semantic_fingerprint']}`
- Compiled Campaign fingerprint：`{campaign['campaign_fingerprint']}`
- Context contract fingerprint：`{context_contract_fingerprint(campaign['router_carry_context_plan']['context_contract'])}`
- 风险等级：`medium`
- 状态：`compiled_pending_human_execution_review`
- 正式 `ranging_short_entry`：保留且未修改
- Candidate / Backtest / Validation / Holdout：`0 / 0 / 0 / 0`

详细中文报告见 `reports/research/{PROPOSAL_ID}-decision-report.md` 和同名 HTML 文件。
""",
        encoding="utf-8",
    )

    integrity = _update_registry(
        run, proposal, campaign, metadata, approval, created_at
    )
    return {
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "context_contract_fingerprint": packet["context_contract_fingerprint"],
        "registry_integrity": integrity,
        "campaign_executed": False,
        "candidate_count": 0,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }


def main() -> int:
    print(json.dumps(build(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
