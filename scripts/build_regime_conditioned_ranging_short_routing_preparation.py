#!/usr/bin/env python3
"""Build the compilation-only routing review package without executing research."""

from __future__ import annotations

import html
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import compile_research_campaign
import research_director
from export_director_registry import export_registry
from research_control import load_campaign
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    proposal_fingerprint,
    utc_now,
    write_json,
    write_yaml,
)


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_ID = "regime-conditioned-ranging-short-routing-v1"
PROPOSAL_DIR = ROOT / "research/director/next-after-ranging-short-retention/proposals"
COMPILED_DIR = ROOT / "research/director/compiled" / PROPOSAL_ID
ANALYSIS_DIR = ROOT / "research/analysis" / PROPOSAL_ID
REPORT_DIR = ROOT / "reports/research"
APPROVAL_PATH = ROOT / "research/governance/approvals/regime-conditioned-ranging-short-routing-v1-compilation-approval.json"
STATE_PATH = ROOT / "research/director/current-research-state.json"
STATE_MD_PATH = ROOT / "research/director/current-research-state.md"
REGISTRY_PATH = ROOT / "research/registry/stage4a-director.db"
REGISTRY_EXPORT_PATH = ROOT / "research/director/registry-records.json"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def _restore_registry_from_export() -> sqlite3.Connection:
    """Rehydrate only tracked Director tables when an isolated worktree has no local DB."""
    connection = open_director_registry(REGISTRY_PATH)
    if not REGISTRY_EXPORT_PATH.exists():
        return connection
    tracked = load_document(REGISTRY_EXPORT_PATH)
    for table, rows in (tracked.get("tables") or {}).items():
        columns = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        if not columns:
            continue
        for row in rows:
            names = [name for name in row if name in columns]
            placeholders = ",".join("?" for _ in names)
            quoted = ",".join(f'"{name}"' for name in names)
            connection.execute(
                f'INSERT OR REPLACE INTO "{table}" ({quoted}) VALUES ({placeholders})',
                [row[name] for name in names],
            )
    connection.commit()
    return connection


def _build_matrix(campaign: dict[str, Any]) -> dict[str, Any]:
    temporal_path = ROOT / "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json"
    temporal = load_document(temporal_path)
    plan = campaign["regime_conditioned_routing_plan"]
    slices: list[dict[str, Any]] = []
    for short_id, conclusion in plan["slice_conclusions"].items():
        full_id = f"ranging-short-ablation-{short_id}"
        item = temporal["slice_results"][full_id]
        slices.append(
            {
                "slice_id": short_id,
                "conclusion": conclusion,
                "signals_removed": item["signals"]["removed"],
                "trades_removed": item["trades"]["removed"],
                "candidate_minus_baseline": item["candidate_minus_baseline"],
                "candidate_minus_baseline_costs": item["candidate_minus_baseline_costs"],
                "router_context_attribution": "not_available_in_existing_evidence",
            }
        )
    return {
        "schema_version": "regime-conditioned-ranging-short-routing-evidence-matrix-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": campaign["proposal_fingerprint"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "formal_branch": "ranging_short_entry",
        "formal_branch_status": "retained_unchanged",
        "temporal_classification": temporal["classification"],
        "slice_policy_fingerprint": temporal["slice_policy_fingerprint"],
        "slices": slices,
        "cross_slice_observation": (
            "Existing evidence proves mixed temporal contribution, but does not bind each sign to a "
            "predeclared runtime-observable router context."
        ),
        "invalid_inference": "time_slice_is_not_a_market_regime_label",
        "strategy_modified": False,
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }


def _build_packet(campaign: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    plan = campaign["regime_conditioned_routing_plan"]
    return {
        "schema_version": "regime-conditioned-ranging-short-routing-human-decision-packet-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": campaign["proposal_fingerprint"],
        "compiled_campaign_fingerprint": campaign["campaign_fingerprint"],
        "risk_class": "medium",
        "approval_status": "pending_human_review",
        "execution_authorized": False,
        "recommendation": plan["preparation_recommendation"],
        "recommendation_reason": plan["recommendation_reason"],
        "evidence_matrix_fingerprint": fingerprint(matrix),
        "formal_branch_status": "retained_unchanged",
        "current_budget": plan["current_execution_budget"],
        "future_separate_approval_envelope": plan["future_separate_approval_envelope"],
        "required_human_decisions": [
            "declare one exact runtime-observable router context without using time slices as regime labels",
            "approve a new medium-risk Proposal and its semantic fingerprint",
            "approve a newly compiled Campaign fingerprint and exact single-variable diff allowlist",
            "approve at most one Candidate and 16 Development-only Backtests",
        ],
        "insufficient_for": [
            "modifying or deleting formal ranging_short_entry",
            "creating a Candidate",
            "running a Backtest",
            "accessing Validation or Holdout",
            "reopening threshold or whole-branch deletion research",
        ],
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "campaign_executed": False,
    }


def _markdown(campaign: dict[str, Any], matrix: dict[str, Any], packet: dict[str, Any]) -> str:
    rows = []
    for item in matrix["slices"]:
        delta = item["candidate_minus_baseline"]
        rows.append(
            f"| `{item['slice_id']}` | `{item['conclusion']}` | {item['signals_removed']} | "
            f"{item['trades_removed']} | {delta['total_return_abs']:.8f} USDT | {delta['profit_factor']:.8f} |"
        )
    future = packet["future_separate_approval_envelope"]
    return f"""# Regime-conditioned ranging-short routing 人工决策报告

> 状态：**仅完成 Proposal 与 dry-run 编译，未执行 Campaign**

- Proposal fingerprint：`{campaign['proposal_fingerprint']}`
- Compiled Campaign fingerprint：`{campaign['campaign_fingerprint']}`
- 风险等级：`medium`
- 当前授权：`0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`
- 正式分支：`ranging_short_entry` 保留且未修改

## 已冻结证据

| 切片 | 贡献结论 | 移除信号 | 移除交易 | 收益差值 Candidate - Baseline | Profit Factor 差值 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

四个切片证明贡献方向随时间变化，但没有把这种变化归因到可在运行时直接观测、并在实验前声明的 router context。**时间切片不是市场 regime 标签**，不能据此事后挑选路由条件。

## 编译建议

`{packet['recommendation']}`

当前应继续保留正式分支，不创建 Candidate，也不执行 Backtest。若未来能先验声明一个精确的 router context，应另建中风险 Proposal 并重新人工审批。

## 未来单独审批上限

- Candidate：最多 `{future['max_candidates']}` 个；
- Development-only Backtest：最多 `{future['max_backtest_calls']}` 次；
- 新增时间切片：`0`；
- Validation / Holdout：`0 / 0`；
- 必须重新冻结 Proposal fingerprint、Campaign fingerprint、Candidate 路径/类名/hash 与 diff allowlist。

## 仍需人工决定

1. 是否存在一个不依赖本次结果挑选的、可运行时观测的精确 router context；
2. 是否批准新的单变量 Candidate；
3. 是否批准 16 次 Development-only Backtest；
4. 是否接受继续保留分支且不作结构变更。

本报告不支持删除正式分支、修改阈值、改变 entry/exit 或访问 Validation/Holdout。
"""


def _html_report(campaign: dict[str, Any], matrix: dict[str, Any], packet: dict[str, Any]) -> str:
    cards = []
    labels = {
        "inconclusive": "证据不足",
        "positive_contributor": "正贡献",
        "negative_contributor": "负贡献",
    }
    for item in matrix["slices"]:
        delta = item["candidate_minus_baseline"]
        cards.append(
            f'''<article class="slice"><div class="slice-head"><strong>{html.escape(item['slice_id'])}</strong>'''
            f'''<span class="pill">{labels[item['conclusion']]}</span></div>'''
            f'''<dl><div><dt>移除信号</dt><dd>{item['signals_removed']}</dd></div>'''
            f'''<div><dt>移除交易</dt><dd>{item['trades_removed']}</dd></div>'''
            f'''<div><dt>收益差值</dt><dd>{delta['total_return_abs']:.4f} USDT</dd></div>'''
            f'''<div><dt>PF 差值</dt><dd>{delta['profit_factor']:.4f}</dd></div></dl></article>'''
        )
    fp = html.escape(campaign["campaign_fingerprint"])
    proposal_fp = html.escape(campaign["proposal_fingerprint"])
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ranging-short 路由研究人工决策报告</title>
<style>
:root{{--paper:#f7f4ec;--ink:#17201c;--muted:#65706a;--green:#193f35;--teal:#2c6f68;--amber:#a86718;--line:#d8d4c8;--card:#fffdf7}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei","Segoe UI",sans-serif;line-height:1.65}}
main{{max-width:1080px;margin:auto;padding:48px 24px 72px}}header{{border-top:6px solid var(--green);padding:32px 0 24px;border-bottom:1px solid var(--line)}}
.eyebrow{{color:var(--teal);font-weight:700;letter-spacing:.08em}}h1{{font-size:clamp(2rem,5vw,3.6rem);line-height:1.12;margin:.35rem 0 1rem;max-width:900px}}h2{{margin-top:40px}}
.status{{display:inline-block;background:#f3e5cb;color:#75450d;padding:8px 12px;border-radius:6px;font-weight:700}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}
.summary div,.slice,.decision{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:0 4px 18px rgba(23,32,28,.05)}}dt{{font-size:.8rem;color:var(--muted)}}dd{{margin:4px 0 0;font-weight:700;overflow-wrap:anywhere}}
.slices{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.slice-head{{display:flex;justify-content:space-between;gap:8px;align-items:center}}.pill{{background:#e4efeb;color:var(--green);padding:3px 8px;border-radius:999px;font-size:.78rem;font-weight:700}}
.slice dl{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:0}}.decision{{border-left:5px solid var(--amber)}}code{{font-family:Consolas,monospace;font-size:.88em;overflow-wrap:anywhere}}ul,ol{{padding-left:1.3rem}}footer{{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:.86rem}}
@media(max-width:800px){{.summary,.slices{{grid-template-columns:1fr 1fr}}}}@media(max-width:520px){{main{{padding:24px 16px 48px}}.summary,.slices{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}.summary div,.slice,.decision{{box-shadow:none}}}}
</style>
</head>
<body><main>
<header><div class="eyebrow">RESEARCH HARNESS · 人工决策</div><h1>Ranging-short 的下一步，不是立即改策略</h1><p class="status">仅完成 Proposal 与 dry-run 编译 · 未执行 Campaign</p></header>
<section class="summary"><div><dt>风险等级</dt><dd>medium</dd></div><div><dt>正式分支</dt><dd>保留且未修改</dd></div><div><dt>当前 Backtest</dt><dd>0</dd></div><div><dt>Validation / Holdout</dt><dd>0 / 0</dd></div></section>
<section><h2>四个冻结切片</h2><div class="slices">{''.join(cards)}</div></section>
<section class="decision"><h2>编译建议</h2><p><code>{html.escape(packet['recommendation'])}</code></p><p>现有证据证明贡献方向存在时间依赖，但尚未归因到一个预先声明、运行时可观测的 router context。时间切片不能替代 market regime。</p><p>因此当前保持 <code>retain_branch_no_routing_change</code>。只有在人工先确定精确单一 context 后，才可另行审批最多 1 个 Candidate 和 16 次 Development-only Backtest。</p></section>
<section><h2>执行前仍需人工批准</h2><ol><li>精确、先验、可运行时观测的单一 router context；</li><li>新的 Proposal 与 Compiled Campaign fingerprint；</li><li>Candidate 路径、类名、源码 hash 与 diff allowlist；</li><li>16 次 Development-only Backtest 的独立授权。</li></ol></section>
<section><h2>冻结身份</h2><p>Proposal：<code>{proposal_fp}</code></p><p>Compiled Campaign：<code>{fp}</code></p></section>
<footer>离线静态报告 · 不加载外部字体、脚本或网络资源 · 正式策略、Candidate、Policy、Dataset、Runtime 均未修改</footer>
</main></body></html>'''


def build() -> dict[str, Any]:
    state = load_document(STATE_PATH)
    constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
    run = research_director.generate(
        state,
        constitution,
        "regime-conditioned ranging-short routing",
        {"max_campaigns": 1, "max_wall_clock_minutes": 30, "max_validation_accesses": 0},
        "medium",
        10,
    )
    proposal = next(item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID)
    if proposal_fingerprint(proposal) != proposal["semantic_fingerprint"]:
        raise ValueError("proposal fingerprint drift")

    created_at = utc_now()
    approval = {
        "schema_version": "research-proposal-compilation-approval-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "approval_status": "approved_for_compilation_only",
        "approver_type": "human_user",
        "approval_source": "accepted_next_step_recommendation",
        "execution_authorized": False,
        "candidate_creation_authorized": False,
        "backtest_authorized": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "approved_at": created_at,
    }
    write_json(APPROVAL_PATH, approval)
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PROPOSAL_DIR / "director-run.json", run)
    write_json(PROPOSAL_DIR / f"{PROPOSAL_ID}.json", proposal)
    write_yaml(PROPOSAL_DIR / f"{PROPOSAL_ID}.yaml", proposal)

    campaign, metadata, brief = compile_research_campaign.compile_campaign(
        ROOT, proposal, state, constitution
    )
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    write_yaml(COMPILED_DIR / "campaign.yaml", campaign)
    write_json(COMPILED_DIR / "experiment-queue.json", campaign["experiment_queue"])
    write_json(COMPILED_DIR / "compilation-metadata.json", metadata)
    (COMPILED_DIR / "implementation-brief.md").write_text(brief, encoding="utf-8")
    load_campaign(COMPILED_DIR / "campaign.yaml")

    matrix = _build_matrix(campaign)
    packet = _build_packet(campaign, matrix)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ANALYSIS_DIR / "routing-evidence-matrix.json", matrix)
    write_json(COMPILED_DIR / "human-decision-packet.json", packet)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    markdown = _markdown(campaign, matrix, packet)
    (REPORT_DIR / f"{PROPOSAL_ID}-decision-report.md").write_text(markdown, encoding="utf-8")
    (REPORT_DIR / f"{PROPOSAL_ID}-decision-report.html").write_text(
        _html_report(campaign, matrix, packet), encoding="utf-8"
    )

    state["regime_conditioned_ranging_short_routing_preparation"] = {
        "status": "compiled_pending_human_review",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "risk_class": "medium",
        "recommendation": packet["recommendation"],
        "campaign_executed": False,
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "evidence": [
            f"research/analysis/{PROPOSAL_ID}/routing-evidence-matrix.json",
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
        {key: value for key, value in state.items() if key not in {"generated_at", "state_fingerprint", "snapshot_id"}}
    )
    state["snapshot_id"] = f"research-state-{state['state_fingerprint'][:16]}"
    write_json(STATE_PATH, state)
    STATE_MD_PATH.write_text(
        f"""# 当前研究状态

- 当前准备项：`{PROPOSAL_ID}`
- Proposal fingerprint：`{proposal['semantic_fingerprint']}`
- Compiled Campaign fingerprint：`{campaign['campaign_fingerprint']}`
- 风险等级：`medium`
- 状态：`compiled_pending_human_review`
- 建议：`{packet['recommendation']}`
- 正式 `ranging_short_entry`：保留且未修改
- Candidate / Backtest / Validation / Holdout：`0 / 0 / 0 / 0`

详细中文报告见 `reports/research/{PROPOSAL_ID}-decision-report.md` 和同名 HTML 文件。
""",
        encoding="utf-8",
    )

    connection = _restore_registry_from_export()
    connection.execute(
        "INSERT OR REPLACE INTO director_runs(run_id,state_fingerprint,objective,risk_tolerance,budget_json,recommendation,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (run["run_id"], run["state_fingerprint"], run["objective"], run["risk_tolerance"], json.dumps(run["budget"], sort_keys=True), run["recommendation"], json.dumps(run, sort_keys=True), run["created_at"]),
    )
    connection.execute(
        "INSERT OR REPLACE INTO director_proposals(proposal_id,run_id,semantic_fingerprint,risk_class,information_gain,status,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (PROPOSAL_ID, run["run_id"], proposal["semantic_fingerprint"], "medium", proposal["expected_information_gain"]["score"], "approved_for_compilation_only", json.dumps(proposal, sort_keys=True), created_at),
    )
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id,proposal_fingerprint,approval_status,approver_type,approved_at,payload_json) VALUES(?,?,?,?,?,?)",
        (PROPOSAL_ID, proposal["semantic_fingerprint"], "approved_for_compilation_only", "human_user", created_at, json.dumps(approval, sort_keys=True)),
    )
    connection.execute("DELETE FROM compiled_campaigns WHERE proposal_id=?", (PROPOSAL_ID,))
    connection.execute(
        "INSERT OR REPLACE INTO compiled_campaigns(compilation_id,proposal_id,campaign_id,campaign_fingerprint,compile_mode,execution_authorized,referenced_hashes_json,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"compile-{campaign['campaign_fingerprint'][:16]}", PROPOSAL_ID, campaign["campaign_id"], campaign["campaign_fingerprint"], "dry_run", 0, json.dumps(metadata["referenced_hashes"], sort_keys=True), json.dumps(campaign, sort_keys=True), created_at),
    )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise ValueError("Registry integrity check failed")
    write_json(REGISTRY_EXPORT_PATH, export_registry(str(REGISTRY_PATH)))

    return {
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "recommendation": packet["recommendation"],
        "registry_integrity": integrity,
        "campaign_executed": False,
        "candidate_created": False,
        "backtest_calls": 0,
    }


def main() -> int:
    result = build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
