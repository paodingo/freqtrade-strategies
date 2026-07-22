#!/usr/bin/env python3
"""Curate approved feedback into deduplicated lesson candidates without promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import load_document, open_director_registry, write_json


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path("research/knowledge/curation/open-source-learning-v1-review-batch-20260719")
CANDIDATE_SCHEMA = Path("research/knowledge/schemas/research-lesson-curation-candidate.schema.json")
LESSON_SCHEMA = Path("research/knowledge/schemas/research-lesson-card.schema.json")
PACKET_SCHEMA = Path("research/knowledge/schemas/research-lesson-promotion-packet.schema.json")
CREATED_AT = "2026-07-19T19:00:00+08:00"
SOURCE_REVIEW_BATCH = "open-source-learning-v1-review-batch-20260719"


def _card(
    lesson_id: str,
    title_zh: str,
    outcome: str,
    mechanism_keys: list[str],
    scope: dict[str, Any],
    summary_zh: str,
    evidence_paths: list[str],
    reuse_policy: str,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = {
        "schema_version": "research-lesson-card-v1",
        "lesson_id": lesson_id,
        "title_zh": title_zh,
        "outcome": outcome,
        "mechanism_keys": sorted(mechanism_keys),
        "scope": scope,
        "summary_zh": summary_zh,
        "metrics": metrics or {},
        "evidence_paths": sorted(evidence_paths),
        "source_class": "A",
        "reuse_policy": reuse_policy,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    card["lesson_fingerprint"] = knowledge.semantic_fingerprint(card, "lesson_fingerprint")
    return card


def candidate_specs() -> list[dict[str, Any]]:
    return [
        {
            "source_feedback_ids": [
                "branch-contribution-ablation-v1-ablation-execution-attempt-2",
                "ranging-short-branch-retention-review-v1-closure",
            ],
            "merge_disposition": "replace_existing_lesson",
            "supersedes_lesson_ids": ["ranging-short-branch-negative-contributor-v1"],
            "material_difference_zh": "把 BTC/ETH 全开发区间的负贡献证据与四个冻结时间切片的混合依赖结论合并，纠正原卡可能被误读为普遍删除依据的问题。",
            "card": _card(
                "ranging-short-temporal-retention-v1",
                "震荡做空分支具有时间依赖，应保留而非整体删除",
                "retained",
                ["branch-contribution", "ranging-short", "temporal-slices", "retention-governance"],
                {"data": "Development-only", "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "temporal_slices": ["s01", "s02", "s03", "s04"]},
                "全开发区间消融显示该分支在 BTC 与 ETH 上为负贡献，但四个冻结切片分别呈现无贡献、一段正贡献和两段负贡献；证据支持保留现有分支并关闭整体删除研究，未来重开必须提供新的时间稳定证据。",
                [
                    "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json",
                    "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json",
                    "research/closures/ranging-short-branch-retention-review-v1.json",
                ],
                "block_semantic_duplicate",
                {"slice_conclusions": {"s01": "inconclusive", "s02": "positive_contributor", "s03": "negative_contributor", "s04": "negative_contributor"}},
            ),
        },
        {
            "source_feedback_ids": ["eth-cross-pair-generalization-v1-run"],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "现有经验卡没有区分行为复现与跨币种经济泛化，本候选明确建立该边界。",
            "card": _card(
                "cross-pair-reproducibility-not-generalization-v1",
                "跨币种行为可复现不等于经济泛化成立",
                "descriptive_not_generalized",
                ["cross-pair", "development-only", "reproducibility"],
                {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "data": "Development-only"},
                "ETH 在独立进程中稳定复现交易行为，但描述性收益与 Profit Factor 明显弱于 BTC；可复现性只能证明实现稳定，不能证明盈利性或跨币种泛化。",
                [
                    "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json",
                    "reports/audits/eth-cross-pair-generalization/eth-cross-pair-generalization-final-report.json",
                ],
                "warn_and_require_material_difference",
            ),
        },
        {
            "source_feedback_ids": ["exit-logic-structure-audit-v1-run-001"],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "现有经验卡未覆盖退出归因的因果证据门槛。",
            "card": _card(
                "exit-frequency-insufficient-causal-evidence-v1",
                "退出频率归因不足以支持退出逻辑重写",
                "insufficient_causal_evidence",
                ["causal-attribution", "exit-logic", "no-mutation"],
                {"data": "Development-only", "audited_exits": 82, "negative_slices": ["stage3e1-s02"]},
                "退出原因计数和分片损益能够描述现象，但未隔离退出机制的增量因果贡献；不得仅凭 ROI、止损等频率占比重写退出或风险语义。",
                [
                    "research/analysis/exit-logic-audit/exit-attribution.json",
                    "reports/audits/exit-logic-audit/exit-logic-structure-final-report.json",
                ],
                "block_semantic_duplicate",
            ),
        },
        {
            "source_feedback_ids": ["regime-conditioned-branch-factorization-v1-recertification-attempt-3"],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "与模块缓存污染经验不同，本候选约束比较结果必须绑定当前原始输出和比较契约。",
            "card": _card(
                "semantic-equivalence-current-artifact-binding-v1",
                "语义等价结论必须绑定当前原始结果与比较契约",
                "verified_engineering",
                ["artifact-lineage", "fresh-process", "semantic-equivalence", "signal-mask"],
                {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "recertification_attempt": 3},
                "旧成功结论因标准化交易未绑定当前原始结果而失效；有效复认证必须使用当前输出、固定比较契约、独立新进程和完整失效血缘。该经验只证明实现等价，不证明 Alpha 改善。",
                [
                    "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-2-invalidation.json",
                    "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-semantic-equivalence-result.json",
                    "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-lineage.json",
                ],
                "require_recertification",
            ),
        },
        {
            "source_feedback_ids": ["stage4c1-cycle-1-regime-branch-structure-audit-v1"],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "现有阈值耗尽卡约束局部搜索，本候选新增跨切片方向轮动不能转化为阈值或结构修改的证据规则。",
            "card": _card(
                "regime-directionality-rotation-no-threshold-search-v1",
                "状态方向轮动不构成阈值搜索或立即修改依据",
                "structural_no_mutation",
                ["directionality-rotation", "regime-branch", "threshold-closure"],
                {"data": "Development-only", "stable_one_sided_defect": False},
                "单个切片可能高度偏多或偏空，但跨切片方向显著轮动且没有稳定单侧缺陷；结构性分布现象不能作为相邻阈值搜索、删除单侧分支或立即修改策略的依据。",
                [
                    "research/analysis/regime-branch-audit/regime-branch-structure.json",
                    "reports/audits/stage4c1/cycle-1-regime-branch-final-report.json",
                ],
                "warn_and_require_material_difference",
            ),
        },
        {
            "source_feedback_ids": ["strategy-family-reassessment-v1-run"],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "现有经验卡聚焦单次机制失败，本候选记录策略家族研究资源配置与单一高信息结构假设约束。",
            "card": _card(
                "strategy-family-baseline-single-structure-hypothesis-v1",
                "策略家族可保留为基线，但活跃研究应限于单一结构假设",
                "research_direction_retained",
                ["research-allocation", "strategy-family", "structural-hypothesis"],
                {"strategy_family": "RegimeAwareV6", "decision_scope": "historical_development_evidence"},
                "BTC 时间证据不足以支持退休，ETH 弱势和未隔离的路由—分支贡献也不支持原样继续主动研究；应仅保留为执行基线，并一次只评估一个明确批准的结构假设。",
                [
                    "research/analysis/strategy-family-reassessment/family-evidence-matrix.json",
                    "research/analysis/strategy-family-reassessment/human-review-packet.json",
                ],
                "warn_and_require_material_difference",
            ),
        },
    ]


def build_candidates(repo: Path, registry_export: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tables = registry_export["tables"]
    approved = sorted(
        row["feedback_id"]
        for row in tables["research_lesson_feedback_drafts"]
        if row["review_status"] == "approved_for_manual_curation"
    )
    candidate_validator = jsonschema.Draft202012Validator(load_document(repo / CANDIDATE_SCHEMA))
    lesson_validator = jsonschema.Draft202012Validator(load_document(repo / LESSON_SCHEMA))
    candidates = []
    covered: list[str] = []
    for spec in candidate_specs():
        card = spec["card"]
        lesson_validator.validate(card)
        candidate = {
            "schema_version": "research-lesson-curation-candidate-v1",
            "candidate_id": f"lesson-candidate-{card['lesson_id']}",
            "status": "pending_human_promotion_review",
            "source_feedback_ids": sorted(spec["source_feedback_ids"]),
            "merge_disposition": spec["merge_disposition"],
            "supersedes_lesson_ids": sorted(spec["supersedes_lesson_ids"]),
            "material_difference_zh": spec["material_difference_zh"],
            "proposed_card": card,
            "automatic_promotion_authorized": False,
        }
        candidate["candidate_fingerprint"] = knowledge.semantic_fingerprint(candidate, "candidate_fingerprint")
        candidate_validator.validate(candidate)
        candidates.append(candidate)
        covered.extend(candidate["source_feedback_ids"])
    if sorted(covered) != approved or len(covered) != len(set(covered)):
        raise ValueError("curation candidates do not cover approved feedback exactly once")
    packet_candidates = []
    for candidate in candidates:
        path = OUTPUT_ROOT / "candidates" / f"{candidate['candidate_id']}.json"
        write_json(repo / path, candidate)
        packet_candidates.append({
            "candidate_id": candidate["candidate_id"],
            "proposed_lesson_id": candidate["proposed_card"]["lesson_id"],
            "path": path.as_posix(),
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "source_feedback_ids": candidate["source_feedback_ids"],
            "supersedes_lesson_ids": candidate["supersedes_lesson_ids"],
        })
    context = load_document(repo / knowledge.OUTPUT_ROOT / "current-context.json")
    packet = {
        "schema_version": "research-lesson-promotion-packet-v1",
        "packet_id": "open-source-learning-v1-lesson-promotion-review-20260719",
        "generated_at": CREATED_AT,
        "source_review_batch": SOURCE_REVIEW_BATCH,
        "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
        "approved_feedback_count": len(approved),
        "candidate_count": len(candidates),
        "formal_lesson_count_before": len(context["lessons"]),
        "candidates": packet_candidates,
        "coverage": {
            "approved_feedback_ids": approved,
            "covered_feedback_ids": sorted(covered),
            "uncovered_feedback_ids": [],
            "duplicate_feedback_merged": len(approved) - len(candidates),
        },
        "human_approval_required": True,
        "automatic_promotion_authorized": False,
        "execution_authorized": False,
    }
    packet["packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "packet_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / PACKET_SCHEMA)).validate(packet)
    write_json(repo / OUTPUT_ROOT / "promotion-review-packet.json", packet)
    return candidates, packet


def register_candidates(registry_path: str | Path, candidates: list[dict[str, Any]]) -> int:
    connection = open_director_registry(registry_path)
    try:
        for candidate in candidates:
            payload_json = json.dumps(candidate, sort_keys=True)
            connection.execute(
                "INSERT OR IGNORE INTO research_lesson_curation_candidates("
                "candidate_id,proposed_lesson_id,candidate_fingerprint,status,source_feedback_ids_json,payload_json,created_at"
                ") VALUES(?,?,?,?,?,?,?)",
                (candidate["candidate_id"], candidate["proposed_card"]["lesson_id"], candidate["candidate_fingerprint"], candidate["status"], json.dumps(candidate["source_feedback_ids"], sort_keys=True), payload_json, CREATED_AT),
            )
            row = connection.execute(
                "SELECT * FROM research_lesson_curation_candidates WHERE candidate_id=?", (candidate["candidate_id"],)
            ).fetchone()
            if row is None or row["candidate_fingerprint"] != candidate["candidate_fingerprint"] or row["payload_json"] != payload_json:
                raise ValueError("lesson curation candidate identity conflict")
        connection.commit()
        return connection.execute("SELECT COUNT(*) FROM research_lesson_curation_candidates").fetchone()[0]
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--registry-export", default="research/director/registry-records.json")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    if (repo / knowledge.PROMOTION_APPROVAL).is_file():
        raise ValueError("curation batch is closed by the governed lesson promotion approval")
    candidates, packet = build_candidates(repo, load_document(repo / args.registry_export))
    registered = register_candidates(args.registry, candidates)
    print(json.dumps({"candidates": len(candidates), "registered": registered, "packet": packet["packet_id"], "automatic_promotion_authorized": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
