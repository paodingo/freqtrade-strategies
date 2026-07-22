#!/usr/bin/env python3
"""Build and query the governed open-source quantitative knowledge layer."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

import jsonschema

from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path("research/knowledge/open-source-v1")
SCHEMA_ROOT = Path("research/knowledge/schemas")
SNAPSHOT_AT = "2026-07-19T00:00:00+08:00"

SCHEMAS = {
    "source": "open-source-source-snapshot.schema.json",
    "pattern": "strategy-pattern-card.schema.json",
    "lesson": "research-lesson-card.schema.json",
}
BROKER_SCHEMA = "knowledge-broker-selection.schema.json"
BROKER_MAX_PATTERNS = 4
BROKER_MAX_LESSONS = 4
PROMOTION_PACKET = Path("research/knowledge/curation/open-source-learning-v1-review-batch-20260719/promotion-review-packet.json")
PROMOTION_APPROVAL = Path("research/governance/approvals/open-source-learning-v1-lesson-promotion-20260720.json")
PROMOTION_APPROVAL_SCHEMA = Path("research/knowledge/schemas/research-lesson-promotion-approval.schema.json")

SOURCE_SPECS = (
    {
        "project_id": "freqtrade-strategies",
        "canonical_url": "https://github.com/freqtrade/freqtrade-strategies",
        "commit_sha": "dbd5b0b21cfbf5ee80588d37458ace2467b7f8a4",
        "default_branch": "main",
        "license_spdx": "GPL-3.0-only",
        "licensing_constraints": "Reference mechanisms only; no source or parameter copying into this repository.",
        "scope": ["crypto", "freqtrade", "strategy_examples"],
        "claims": ["Provides educational Freqtrade strategy examples and warns that results depend on pair, timeframe, and timerange."],
        "status": "active_reference_only",
    },
    {
        "project_id": "jesse",
        "canonical_url": "https://github.com/jesse-ai/jesse",
        "commit_sha": "fa63531cae6c09b978711dc1892285067304e2df",
        "default_branch": "master",
        "license_spdx": "MIT",
        "licensing_constraints": "MIT license verified at the pinned commit; preserve copyright and license notice; clean-room mechanism summaries only.",
        "scope": ["crypto", "multi_timeframe", "order_lifecycle"],
        "claims": ["Documents multi-symbol and multi-timeframe strategy research with explicit order intent."],
        "status": "active_reference_only",
    },
    {
        "project_id": "qlib",
        "canonical_url": "https://github.com/microsoft/qlib",
        "commit_sha": "d5379c520f66a39953bad76234a7019a72796fd0",
        "default_branch": "main",
        "license_spdx": "MIT",
        "licensing_constraints": "Learn workflow and factor evaluation patterns; do not import model code in v1.",
        "scope": ["factor_research", "machine_learning", "portfolio_workflow"],
        "claims": ["Covers data processing, forecasting, backtesting, portfolio construction, and execution workflows."],
        "status": "active_reference_only",
    },
    {
        "project_id": "lean",
        "canonical_url": "https://github.com/QuantConnect/Lean",
        "commit_sha": "0269115d3cfbf691c7a0b7cfcc9ed412cafb91f6",
        "default_branch": "master",
        "license_spdx": "Apache-2.0",
        "licensing_constraints": "Reference portfolio and execution abstractions; no engine integration in v1.",
        "scope": ["multi_asset", "portfolio_construction", "execution_model"],
        "claims": ["Provides a modular event-driven research, backtesting, portfolio, risk, and execution engine."],
        "status": "active_reference_only",
    },
    {
        "project_id": "nautilus-trader",
        "canonical_url": "https://github.com/nautechsystems/nautilus_trader",
        "commit_sha": "3ffa0ca4bea7876a7f78f8799fd73426059a097a",
        "default_branch": "develop",
        "license_spdx": "LGPL-3.0-only",
        "licensing_constraints": "Reference deterministic execution semantics only; no engine or adapter code copying.",
        "scope": ["event_driven", "execution_simulation", "research_live_parity"],
        "claims": ["Uses deterministic event-driven semantics across research simulation and live execution."],
        "status": "active_reference_only",
    },
    {
        "project_id": "hummingbot",
        "canonical_url": "https://github.com/hummingbot/hummingbot",
        "commit_sha": "816b8ab539360557cee7d9248c2f24473b10b16f",
        "default_branch": "master",
        "license_spdx": "Apache-2.0",
        "licensing_constraints": "Reference market-making and connector risk concepts; current 1h data cannot validate microstructure alpha.",
        "scope": ["crypto", "market_making", "cross_venue_execution"],
        "claims": ["Provides modular crypto exchange connectors and market-making oriented strategy infrastructure."],
        "status": "active_reference_only",
    },
)


PATTERN_SPECS = (
    ("causal-indicator-validation", "因果指标验证", "research_method", "research_integrity", "freqtrade-strategies", ["lookahead-analysis", "recursive-analysis", "causal-signals"], "在评价收益前先证明指标不会使用未来数据，且启动长度变化不会重写历史信号。", ["ohlcv"], "ready", "对完整数据和多个前缀重算信号；任何历史信号变化都使实验无效。", ["工具只能发现已覆盖的偏差", "递归稳定不等于经济有效"], ["出现未来信号重写", "前缀重算不一致"]),
    ("multi-timeframe-regime-gating", "多周期状态过滤", "alpha_mechanism", "regime_filtering", "freqtrade-strategies", ["multi-timeframe", "regime-filter", "signal-gating"], "低周期负责入场，高周期只提供已经确认的市场状态过滤。", ["1h_ohlcv", "4h_ohlcv"], "ready", "先计算已收盘的4小时状态，再允许1小时候选信号；禁止回填状态。", ["高周期确认造成滞后", "过滤器可能减少有效覆盖"], ["相对基线没有信息增益", "过滤后覆盖退化"]),
    ("explicit-order-intent", "显式订单意图", "execution_pattern", "execution_semantics", "jesse", ["order-intent", "entry-exit-separation", "position-state"], "把信号、订单意图和持仓状态分开，使交易变化可以归因。", ["ohlcv", "position_state"], "ready", "信号先生成意图；订单层根据当前持仓与执行约束决定是否提交。", ["状态机复杂度增加", "回测执行语义可能与交易所不同"], ["同一输入产生非确定订单", "无法解释信号到成交的阻断点"]),
    ("multi-symbol-timeframe-composition", "多标的多周期组合", "research_method", "cross_pair_research", "jesse", ["multi-symbol", "multi-timeframe", "cross-pair"], "在统一时钟上组合多个标的和周期，避免分别回测后再主观拼接。", ["btc_1h_4h", "eth_1h_4h"], "ready", "只用同一时刻已完成的BTC和ETH信息产生路由或相对强弱特征。", ["时钟对齐错误", "跨币种关系可能发生结构变化"], ["前缀因果检查失败", "ETH描述性结果材料性退化"]),
    ("cross-sectional-factor-ranking", "横截面因子排序", "alpha_mechanism", "relative_strength", "qlib", ["cross-sectional", "factor-ranking", "relative-strength"], "比较同一时点多个资产的标准化特征，而不是只看单资产绝对阈值。", ["synchronized_multi_asset_ohlcv"], "data_readiness_required", "在每个已完成时点计算跨资产排名，只交易领先或落后的明确一端。", ["当前资产数太少", "排名暴露可能等同市场Beta"], ["排名对资产池不稳定", "成本后相对收益消失"]),
    ("walk-forward-concept-drift", "滚动概念漂移评估", "research_method", "temporal_robustness", "qlib", ["walk-forward", "concept-drift", "temporal-slices"], "把市场关系视为会变化的对象，用冻结的滚动窗口评价稳定性。", ["long_history", "sealed_temporal_slices"], "data_readiness_required", "按预先冻结的时间切片依次训练或校准，并只评价下一段Development数据。", ["窗口选择形成隐性搜索", "样本不足导致结论不稳定"], ["多数切片方向不一致", "结果依赖单一窗口"]),
    ("portfolio-risk-model-separation", "组合与风险模型分离", "risk_pattern", "portfolio_risk", "lean", ["portfolio-construction", "risk-model", "alpha-separation"], "Alpha只表达方向和强度，独立组合与风险层决定资本分配。", ["multi_asset_signals", "portfolio_state"], "data_readiness_required", "将信号评分映射为目标暴露，再由风险预算限制总仓位和集中度。", ["可能掩盖弱Alpha", "与当前固定仓位契约不兼容"], ["风险层成为收益主要来源", "移除Alpha后表现不变"]),
    ("scheduled-universe-rebalance", "定时资产池再平衡", "research_method", "portfolio_rebalance", "lean", ["scheduled-rebalance", "universe-selection", "turnover-control"], "资产选择与交易触发采用不同频率，减少噪声换手。", ["multi_asset_history", "tradability_metadata"], "out_of_v1_scope", "按固定日程更新资产池，在资产池内才允许低周期信号。", ["当前只批准BTC和ETH", "资产池变化引入幸存者偏差"], ["换手成本抵消收益", "资产池定义依赖未来信息"]),
    ("deterministic-research-live-parity", "确定性研究—执行一致性", "execution_pattern", "execution_semantics", "nautilus-trader", ["deterministic-clock", "event-driven", "research-live-parity"], "研究和执行共享时间、订单与状态转换语义，减少部署漂移。", ["event_stream", "order_state"], "data_readiness_required", "固定事件顺序、时钟和订单状态机；相同输入必须产生相同状态轨迹。", ["实现成本高", "仅有K线不能验证订单级细节"], ["重复运行状态轨迹不同", "研究订单语义无法映射到运行时"]),
    ("realistic-fill-order-state", "真实成交与订单状态模拟", "execution_pattern", "fill_simulation", "nautilus-trader", ["fill-model", "partial-fill", "order-state"], "成交、撤单、部分成交和队列状态必须显式建模，不能默认理想成交。", ["quotes_or_orderbook", "trades", "order_state"], "out_of_v1_scope", "使用可审计成交模型推进订单状态，并对滑点和未成交进行压力测试。", ["缺少L1/L2历史数据", "错误成交模型会制造虚假Alpha"], ["保守成交假设下收益消失", "订单状态无法重放"]),
    ("inventory-aware-market-making", "库存约束做市", "alpha_mechanism", "market_making", "hummingbot", ["market-making", "inventory-risk", "spread"], "报价宽度和偏斜随库存、波动率及交易成本变化。", ["l2_orderbook", "trade_ticks", "latency", "fees"], "out_of_v1_scope", "围绕中间价双边报价；库存偏离时减少同方向报价并扩大风险侧价差。", ["1小时K线无法验证成交", "延迟和队列位置主导结果"], ["保守队列模型下无正收益", "库存尾部风险不可控"]),
    ("funding-basis-arbitrage", "资金费率与基差套利", "alpha_mechanism", "relative_value", "hummingbot", ["funding-rate", "basis", "cross-venue"], "比较资金费率、基差和执行成本，在对冲后捕捉相对价值。", ["funding_history", "spot_perp_basis", "multi_venue_quotes", "borrow_cost"], "data_readiness_required", "仅在预期资金收益覆盖双边费用、滑点和基差风险时建立对冲头寸。", ["资金费率会快速反转", "跨场所执行和借贷风险"], ["成本压力后收益为负", "对冲误差材料性扩大"]),
)


def semantic_fingerprint(payload: dict[str, Any], field: str) -> str:
    return fingerprint({key: value for key, value in payload.items() if key != field})


def source_snapshots() -> list[dict[str, Any]]:
    snapshots = []
    for spec in SOURCE_SPECS:
        payload = {
            "schema_version": "open-source-source-snapshot-v1",
            "snapshot_id": f"{spec['project_id']}@{spec['commit_sha']}",
            **spec,
            "retrieved_at": SNAPSHOT_AT,
            "source_class": "C",
            "publisher_type": "public_strategy_repository",
            "fingerprint_basis": "canonical repository identity, fixed commit, license, scope, and claims; full source is not stored",
            "full_source_stored": False,
            "code_reuse_authorized": False,
        }
        payload["content_fingerprint"] = semantic_fingerprint(payload, "content_fingerprint")
        snapshots.append(payload)
    return snapshots


def pattern_cards(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_ids = {item["project_id"]: item["snapshot_id"] for item in sources}
    cards = []
    for pattern_id, title, kind, family, project, keys, summary, data, readiness, pseudocode, risks, falsification in PATTERN_SPECS:
        payload = {
            "schema_version": "strategy-pattern-card-v1",
            "pattern_id": pattern_id,
            "title_zh": title,
            "pattern_kind": kind,
            "strategy_family": family,
            "mechanism_summary_zh": summary,
            "mechanism_keys": sorted(keys),
            "source_snapshot_ids": [source_ids[project]],
            "source_class": "C",
            "required_data": sorted(data),
            "local_data_readiness": readiness,
            "clean_room_pseudocode_zh": pseudocode,
            "risks": sorted(risks),
            "falsification_conditions": sorted(falsification),
            "evidence_requirements": ["至少一项A类内部证据或B类学术/教材证据", "Development-only最小变量实验", "因果性和成本检查"],
            "proposal_eligibility": "inspiration_only_requires_A_or_B",
            "parameters_copied": False,
            "implementation_copied": False,
            "alpha_claim": False,
            "status": "blocked_by_data" if readiness == "out_of_v1_scope" else "catalogued",
        }
        payload["pattern_fingerprint"] = semantic_fingerprint(payload, "pattern_fingerprint")
        cards.append(payload)
    return cards


def _legacy_lesson_cards(repo: Path) -> list[dict[str, Any]]:
    chan_path = Path("reports/audits/chan-structure-reversal-v1/final-report.json")
    ablation_path = Path("research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json")
    invalidation_path = Path("research/recertification/stage3d3b/stage3d2b-invalidation-event.json")
    closure_path = Path("research/closures/regime-aware-ranging-thresholds-v1.yaml")
    chan = load_document(repo / chan_path)
    ablation = load_document(repo / ablation_path)
    invalidation = load_document(repo / invalidation_path)
    closure = load_document(repo / closure_path)
    if chan.get("classification") != "development_rejected_material_degradation":
        raise ValueError("chan lesson evidence classification drift")
    if ablation.get("classification") != "branch_negative_contributor":
        raise ValueError("ablation lesson evidence classification drift")
    if closure.get("status") != "closed_evidence_exhausted":
        raise ValueError("threshold closure evidence drift")

    specs = [
        {
            "lesson_id": "chan-confirmed-higher-low-direct-entry-v1",
            "title_zh": "确认次低点直接做多产生材料性退化",
            "outcome": "rejected_degradation",
            "mechanism_keys": ["confirmed-higher-low", "direct-long-entry", "structure-retest"],
            "scope": {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "timeframe": "1h", "data": "Development-only"},
            "summary_zh": "结构信号在两币种均真实成交，但收益、Profit Factor和回撤相对基线恶化；相同直接入场语义应阻止重复研究。",
            "metrics": {
                pair: {
                    "return_delta_pp": chan["pair_results"][pair]["candidate_minus_baseline"]["total_return_percentage_points"],
                    "profit_factor_delta": chan["pair_results"][pair]["candidate_minus_baseline"]["profit_factor"],
                    "drawdown_delta_pp": chan["pair_results"][pair]["candidate_minus_baseline"]["max_drawdown_percentage_points"],
                    "structure_trades": chan["pair_results"][pair]["candidate"]["structure_trade_count"],
                }
                for pair in ("btc", "eth")
            },
            "evidence_paths": [chan_path.as_posix()],
            "reuse_policy": "block_semantic_duplicate",
        },
        {
            "lesson_id": "ranging-short-branch-negative-contributor-v1",
            "title_zh": "震荡做空分支在BTC和ETH均为负贡献",
            "outcome": "negative_contributor",
            "mechanism_keys": ["ranging-short", "branch-contribution", "regime-entry"],
            "scope": {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "data": "Development-only"},
            "summary_zh": "移除震荡做空分支后两币种Development结果均改善；未来保留或重做必须说明与原分支的材料性差异。",
            "metrics": {pair: ablation["pair_results"][pair]["candidate_minus_baseline"] for pair in ("btc", "eth")},
            "evidence_paths": [ablation_path.as_posix()],
            "reuse_policy": "warn_and_require_material_difference",
        },
        {
            "lesson_id": "candidate-module-cache-shadowing-v1",
            "title_zh": "候选模块缓存污染会使研究结果失效",
            "outcome": "invalidated_engineering",
            "mechanism_keys": ["candidate-isolation", "module-cache", "fresh-process"],
            "scope": {"affected_experiments": invalidation["affected_experiment_ids"], "failure_class": "implementation_error"},
            "summary_zh": "候选依赖模块被Python缓存遮蔽时，表面可复现的实验仍可能运行错误实现；候选必须使用独立模块身份和新进程。",
            "metrics": {"invalidated_experiment_count": len(invalidation["affected_experiment_ids"])},
            "evidence_paths": [invalidation_path.as_posix()],
            "reuse_policy": "require_recertification",
        },
        {
            "lesson_id": "single-threshold-ranging-search-exhausted-v1",
            "title_zh": "震荡单阈值邻域研究证据耗尽",
            "outcome": "closed_evidence_exhausted",
            "mechanism_keys": ["single-threshold", "ranging-regime", "adjacent-search"],
            "scope": {"strategy_family": closure["strategy_family"], "variables": sorted(closure["variables"])},
            "summary_zh": "相邻阈值搜索没有产生Development合格候选；仅扩大阈值范围、增加回测或LLM直觉都不是重开理由。",
            "metrics": {"development_eligible_experiment_ids": closure["conclusions"]["development_eligible_experiment_ids"]},
            "evidence_paths": [closure_path.as_posix()],
            "reuse_policy": "block_semantic_duplicate",
        },
    ]
    lessons = []
    for spec in specs:
        payload = {
            "schema_version": "research-lesson-card-v1",
            **spec,
            "mechanism_keys": sorted(spec["mechanism_keys"]),
            "source_class": "A",
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        payload["lesson_fingerprint"] = semantic_fingerprint(payload, "lesson_fingerprint")
        lessons.append(payload)
    return lessons


def promoted_lesson_cards(repo: Path) -> list[dict[str, Any]]:
    approval = load_document(repo / PROMOTION_APPROVAL)
    packet = load_document(repo / PROMOTION_PACKET)
    jsonschema.Draft202012Validator(load_document(repo / PROMOTION_APPROVAL_SCHEMA)).validate(approval)
    if semantic_fingerprint(approval, "approval_fingerprint") != approval["approval_fingerprint"]:
        raise ValueError("lesson promotion approval fingerprint mismatch")
    if semantic_fingerprint(packet, "packet_fingerprint") != packet["packet_fingerprint"]:
        raise ValueError("lesson promotion packet fingerprint mismatch")
    if approval["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise ValueError("lesson promotion approval is not bound to the current packet")
    packet_candidates = {item["candidate_id"]: item for item in packet["candidates"]}
    decisions = {item["candidate_id"]: item for item in approval["decisions"]}
    if len(decisions) != len(approval["decisions"]) or set(decisions) != set(packet_candidates):
        raise ValueError("lesson promotion decisions must cover the packet exactly once")
    if approval["approved_count"] != sum(item["decision"] == "approved" for item in decisions.values()):
        raise ValueError("lesson promotion approved count mismatch")
    if approval["rejected_count"] != sum(item["decision"] == "rejected" for item in decisions.values()):
        raise ValueError("lesson promotion rejected count mismatch")
    cards = []
    for candidate_id in sorted(packet_candidates):
        packet_item = packet_candidates[candidate_id]
        decision = decisions[candidate_id]
        if decision["candidate_fingerprint"] != packet_item["candidate_fingerprint"]:
            raise ValueError("lesson promotion candidate fingerprint mismatch")
        candidate = load_document(repo / packet_item["path"])
        if candidate["candidate_id"] != candidate_id:
            raise ValueError("lesson promotion candidate identity mismatch")
        if semantic_fingerprint(candidate, "candidate_fingerprint") != candidate["candidate_fingerprint"]:
            raise ValueError("lesson promotion candidate payload fingerprint mismatch")
        if candidate["candidate_fingerprint"] != decision["candidate_fingerprint"]:
            raise ValueError("lesson promotion decision candidate mismatch")
        if decision["decision"] != "approved":
            continue
        card = candidate["proposed_card"]
        if semantic_fingerprint(card, "lesson_fingerprint") != card["lesson_fingerprint"]:
            raise ValueError("promoted lesson fingerprint mismatch")
        for evidence_path in card["evidence_paths"]:
            if not (repo / evidence_path).is_file():
                raise ValueError(f"promoted lesson evidence is missing: {evidence_path}")
        cards.append(card)
    return cards


def lesson_cards(repo: Path) -> list[dict[str, Any]]:
    legacy = [
        item
        for item in _legacy_lesson_cards(repo)
        if item["lesson_id"] != "ranging-short-branch-negative-contributor-v1"
    ]
    return sorted([*legacy, *promoted_lesson_cards(repo)], key=lambda item: item["lesson_id"])


def validate_assets(repo: Path, sources: list[dict[str, Any]], patterns: list[dict[str, Any]], lessons: list[dict[str, Any]]) -> None:
    if len(sources) != 6 or len(patterns) > 12 or len(patterns) != 12 or not lessons:
        raise ValueError("open-source knowledge v1 fixed scope mismatch")
    validators = {
        key: jsonschema.Draft202012Validator(load_document(repo / SCHEMA_ROOT / name), format_checker=jsonschema.FormatChecker())
        for key, name in SCHEMAS.items()
    }
    for kind, items, fingerprint_field in (
        ("source", sources, "content_fingerprint"),
        ("pattern", patterns, "pattern_fingerprint"),
        ("lesson", lessons, "lesson_fingerprint"),
    ):
        seen = set()
        for item in items:
            validators[kind].validate(item)
            if item[fingerprint_field] != semantic_fingerprint(item, fingerprint_field):
                raise ValueError(f"{kind} fingerprint mismatch: {item}")
            if item[fingerprint_field] in seen:
                raise ValueError(f"duplicate {kind} fingerprint")
            seen.add(item[fingerprint_field])


def build_knowledge(repo: Path, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    sources = source_snapshots()
    patterns = pattern_cards(sources)
    lessons = lesson_cards(repo)
    validate_assets(repo, sources, patterns, lessons)
    root = repo / output_root
    assets: list[dict[str, str]] = []
    for kind, items, id_field, folder in (
        ("source", sources, "project_id", "sources"),
        ("pattern", patterns, "pattern_id", "patterns"),
        ("lesson", lessons, "lesson_id", "lessons"),
    ):
        for item in items:
            path = root / folder / f"{item[id_field]}.json"
            write_json(path, item)
            assets.append({"kind": kind, "path": path.relative_to(repo).as_posix(), "sha256": sha256_file(path)})
    knowledge_fingerprint = fingerprint({"assets": sorted(assets, key=lambda item: item["path"])})
    context = {
        "schema_version": "open-source-knowledge-context-v1",
        "knowledge_snapshot_fingerprint": knowledge_fingerprint,
        "source_policy": {"public_repository_class": "C", "class_c_only_result": "reject", "proposal_requirement": "at_least_one_A_or_B"},
        "sources": sources,
        "patterns": patterns,
        "lessons": lessons,
        "candidate_creation_authorized": False,
        "backtest_authorized": False,
        "strategy_mutation_authorized": False,
    }
    context["context_fingerprint"] = semantic_fingerprint(context, "context_fingerprint")
    context_path = root / "current-context.json"
    write_json(context_path, context)
    manifest = {
        "schema_version": "open-source-knowledge-manifest-v1",
        "knowledge_id": "open-source-learning-v1",
        "generated_at": SNAPSHOT_AT,
        "knowledge_snapshot_fingerprint": knowledge_fingerprint,
        "counts": {"sources": len(sources), "patterns": len(patterns), "lessons": len(lessons)},
        "assets": sorted(assets, key=lambda item: item["path"]),
        "context_path": context_path.relative_to(repo).as_posix(),
        "context_sha256": sha256_file(context_path),
        "candidate_created": False,
        "backtests_run": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
    }
    manifest["manifest_fingerprint"] = semantic_fingerprint(manifest, "manifest_fingerprint")
    write_json(root / "manifest.json", manifest)
    return manifest


def register_knowledge(repo: Path, registry_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    context = load_document(repo / manifest["context_path"])
    connection = open_director_registry(registry_path)
    protected_before = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in ("director_proposals", "compiled_campaigns", "research_campaign_runs")
    }
    for source in context["sources"]:
        connection.execute(
            "INSERT OR REPLACE INTO open_source_knowledge_sources(snapshot_id,project_id,commit_sha,content_fingerprint,license_spdx,status,payload_json,retrieved_at) VALUES(?,?,?,?,?,?,?,?)",
            (source["snapshot_id"], source["project_id"], source["commit_sha"], source["content_fingerprint"], source["license_spdx"], source["status"], json.dumps(source, sort_keys=True), source["retrieved_at"]),
        )
    for pattern in context["patterns"]:
        connection.execute(
            "INSERT OR REPLACE INTO open_source_strategy_patterns(pattern_id,pattern_fingerprint,strategy_family,status,source_snapshot_ids_json,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (pattern["pattern_id"], pattern["pattern_fingerprint"], pattern["strategy_family"], pattern["status"], json.dumps(pattern["source_snapshot_ids"], sort_keys=True), json.dumps(pattern, sort_keys=True), SNAPSHOT_AT),
        )
        for snapshot_id in pattern["source_snapshot_ids"]:
            lineage_id = fingerprint({"source": snapshot_id, "pattern": pattern["pattern_id"]})
            connection.execute(
                "INSERT OR REPLACE INTO open_source_knowledge_lineage(lineage_id,source_type,source_id,relation,target_type,target_id,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (lineage_id, "source_snapshot", snapshot_id, "abstracted_as", "strategy_pattern", pattern["pattern_id"], "{}", SNAPSHOT_AT),
            )
    for lesson in context["lessons"]:
        connection.execute(
            "INSERT OR REPLACE INTO open_source_research_lessons(lesson_id,lesson_fingerprint,outcome,mechanism_keys_json,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (lesson["lesson_id"], lesson["lesson_fingerprint"], lesson["outcome"], json.dumps(lesson["mechanism_keys"], sort_keys=True), json.dumps(lesson, sort_keys=True), SNAPSHOT_AT),
        )
        for evidence_path in lesson["evidence_paths"]:
            lineage_id = fingerprint({"evidence": evidence_path, "lesson": lesson["lesson_id"]})
            connection.execute(
                "INSERT OR REPLACE INTO open_source_knowledge_lineage(lineage_id,source_type,source_id,relation,target_type,target_id,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (lineage_id, "internal_evidence", evidence_path, "supports", "research_lesson", lesson["lesson_id"], "{}", SNAPSHOT_AT),
            )
    connection.commit()
    protected_after = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in protected_before
    }
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in ("open_source_knowledge_sources", "open_source_strategy_patterns", "open_source_research_lessons", "open_source_knowledge_lineage")
    }
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if protected_before != protected_after:
        raise ValueError("knowledge registration changed proposal or campaign counts")
    return {"integrity": integrity, "counts": counts, "protected_counts_unchanged": True}


def _latest_generic_promotion(repo: Path, snapshot_fingerprint: str) -> dict[str, Any] | None:
    root = repo / "reports/audits/open-source-learning-v1/review-batches/aggregated"
    completed = []
    if root.is_dir():
        for batch_root in root.glob("knowledge-review-batch-*"):
            approval_path = batch_root / "promotion-approval.json"
            published_manifest_path = batch_root / "promotion-published-manifest.json"
            packet_path = batch_root / "promotion-review-packet.json"
            if not (approval_path.is_file() and published_manifest_path.is_file() and packet_path.is_file()):
                continue
            approval = load_document(approval_path)
            published_manifest = load_document(published_manifest_path)
            packet = load_document(packet_path)
            if semantic_fingerprint(approval, "approval_fingerprint") != approval.get("approval_fingerprint"):
                raise ValueError("generic lesson promotion approval fingerprint mismatch")
            if semantic_fingerprint(published_manifest, "manifest_fingerprint") != published_manifest.get("manifest_fingerprint"):
                raise ValueError("generic lesson promotion published manifest fingerprint mismatch")
            if semantic_fingerprint(packet, "packet_fingerprint") != packet.get("packet_fingerprint"):
                raise ValueError("generic lesson promotion packet fingerprint mismatch")
            if approval.get("packet_fingerprint") != packet.get("packet_fingerprint"):
                raise ValueError("generic lesson promotion approval packet mismatch")
            if packet.get("source_review_batch") != batch_root.name:
                raise ValueError("generic lesson promotion batch identity mismatch")
            if published_manifest.get("knowledge_snapshot_fingerprint") != snapshot_fingerprint:
                continue
            completed.append((str(approval["decided_at"]), batch_root, approval, packet_path))
    if not completed:
        return None
    _, batch_root, approval, packet_path = max(
        completed, key=lambda item: (item[0], item[1].name)
    )
    return {
        "lesson_curation": (
            f"promotion_completed_{approval['approved_count']}_approved_"
            f"{approval['rejected_count']}_rejected"
        ),
        "promotion_review_packet": packet_path.relative_to(repo).as_posix(),
        "last_promotion_batch": {
            "status": "completed",
            "approved": approval["approved_count"],
            "rejected": approval["rejected_count"],
            "archive": batch_root.relative_to(repo).as_posix(),
            "automatic_application_authorized": False,
        },
    }


def knowledge_state_summary(repo: Path) -> dict[str, Any]:
    manifest_path = repo / OUTPUT_ROOT / "manifest.json"
    if not manifest_path.is_file():
        return {"available": False, "evidence": []}
    manifest = load_document(manifest_path)
    context_path = repo / manifest["context_path"]
    if sha256_file(context_path) != manifest["context_sha256"]:
        raise ValueError("open-source knowledge context hash mismatch")
    summary = {
        "available": True,
        "knowledge_id": manifest["knowledge_id"],
        "knowledge_snapshot_fingerprint": manifest["knowledge_snapshot_fingerprint"],
        "counts": manifest["counts"],
        "class_c_only_result": "reject",
        "candidate_creation_authorized": False,
        "automatic_broker": {
            "enabled": True,
            "consumer": "research_discovery_researcher",
            "max_patterns": BROKER_MAX_PATTERNS,
            "max_lessons": BROKER_MAX_LESSONS,
            "ranking": "deterministic_weighted_lexical_v2",
            "usage_lineage_relation": "retrieved_for",
        },
        "learning_loop": {
            "idea_knowledge_binding_required": True,
            "critic_verification_required": True,
            "director_verified_binding_required": True,
            "worker_dispatch": "provider_neutral_lease_queue",
            "campaign_feedback": "automatic_pending_human_review_draft",
            "automatic_lesson_promotion_authorized": False,
        },
        "maintenance": {
            "source_refresh": "human_approval_only",
            "lifecycle": "registry_managed",
            "source_refresh_report": "reports/audits/open-source-learning-v1/source-refresh-report.json",
            "retrieval_evaluation": "reports/audits/open-source-learning-v1/retrieval-evaluation.json",
            "learning_loop_health": "reports/audits/open-source-learning-v1/learning-loop-health.json",
            "pending_review_packet": "reports/audits/open-source-learning-v1/pending-review-packet.json",
            "review_recommendations": "reports/audits/open-source-learning-v1/review-recommendations.json",
            "lesson_curation": "promotion_completed_6_approved_0_rejected",
            "promotion_review_packet": "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/promotion-review-packet.json",
            "last_promotion_batch": {
                "status": "completed",
                "approved": 6,
                "rejected": 0,
                "archive": "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720",
                "automatic_application_authorized": False,
            },
            "last_review_batch": {
                "status": "completed",
                "approved": 8,
                "rejected": 3,
                "archive": "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719",
                "automatic_application_authorized": False,
            },
            "automatic_source_update_authorized": False,
            "automatic_lesson_promotion_authorized": False,
        },
        "evidence": [manifest["context_path"]],
    }
    latest = _latest_generic_promotion(repo, manifest["knowledge_snapshot_fingerprint"])
    if latest is not None:
        summary["maintenance"].update(latest)
    return summary


def retrieve_context(repo: Path, mechanism_keys: Iterable[str] = (), strategy_family: str | None = None) -> dict[str, Any]:
    context = load_document(repo / OUTPUT_ROOT / "current-context.json")
    keys = {str(key) for key in mechanism_keys}
    patterns = [
        item for item in context["patterns"]
        if (not strategy_family or item["strategy_family"] == strategy_family)
        and (not keys or keys.intersection(item["mechanism_keys"]))
    ]
    lessons = [item for item in context["lessons"] if not keys or keys.intersection(item["mechanism_keys"])]
    return {
        "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
        "patterns": sorted(patterns, key=lambda item: item["pattern_id"]),
        "lessons": sorted(lessons, key=lambda item: item["lesson_id"]),
        "proposal_eligibility": "requires_A_or_B_and_human_governance",
    }


def _normalized_query(value: object) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z\u3400-\u9fff]+", " ", str(value).lower())
    return " ".join(normalized.split())[:256]


def _broker_query_terms(event_type: str, event_ref: str, state: dict[str, Any]) -> list[tuple[str, int]]:
    weighted: list[tuple[str, int]] = [(event_ref, 100), (event_type, 2)]
    for item in state.get("unresolved_research_questions", []):
        if isinstance(item, dict):
            weighted.extend((item.get(field, ""), 2) for field in ("question_id", "question", "current_answer"))
    for item in state.get("possible_next_directions", []):
        if isinstance(item, dict):
            weighted.append((item.get("direction", ""), 2))
    for item in state.get("invalidated_research", []):
        if isinstance(item, dict):
            weighted.extend((item.get(field, ""), 1) for field in ("event_id", "reason", "repair_status"))
    for item in state.get("closed_branches", []):
        if isinstance(item, dict):
            weighted.extend((item.get(field, ""), 1) for field in ("closure_id", "branch", "status", "decision", "variables"))

    deduplicated: dict[str, int] = {}
    for raw, weight in weighted:
        if isinstance(raw, list):
            values = raw
        else:
            values = [raw]
        for value in values:
            term = _normalized_query(value)
            if term:
                deduplicated[term] = max(weight, deduplicated.get(term, 0))
    return list(deduplicated.items())[:32]


def _score_card(card: dict[str, Any], weighted_terms: list[tuple[str, int]]) -> tuple[int, list[str]]:
    score = 0
    matched_keys: set[str] = set()
    for key in card["mechanism_keys"]:
        normalized_key = _normalized_query(key)
        key_tokens = {token for token in normalized_key.split() if len(token) >= 4}
        for term, weight in weighted_terms:
            if normalized_key and normalized_key in term:
                score += 100 * weight
                matched_keys.add(key)
                continue
            overlap = key_tokens.intersection(term.split())
            if overlap:
                score += 10 * weight * len(overlap)
                matched_keys.add(key)
    return score, sorted(matched_keys)


def broker_selection(
    repo: Path,
    event_type: str,
    event_ref: str,
    trigger_fingerprint: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Select bounded knowledge for one Discovery trigger without granting execution authority."""
    context = load_document(repo / OUTPUT_ROOT / "current-context.json")
    knowledge_state = state.get("open_source_knowledge")
    if not isinstance(knowledge_state, dict) or knowledge_state.get("available") is not True:
        raise ValueError("open-source knowledge is not available in current research state")
    if knowledge_state.get("knowledge_snapshot_fingerprint") != context.get("knowledge_snapshot_fingerprint"):
        raise ValueError("open-source knowledge snapshot does not match current research state")

    weighted_terms = _broker_query_terms(event_type, event_ref, state)
    ranked_patterns = []
    for card in context["patterns"]:
        score, matched = _score_card(card, weighted_terms)
        if score:
            ranked_patterns.append((score, card["pattern_id"], matched, card))
    ranked_lessons = []
    for card in context["lessons"]:
        score, matched = _score_card(card, weighted_terms)
        if score:
            ranked_lessons.append((score, card["lesson_id"], matched, card))
    ranked_patterns.sort(key=lambda item: (-item[0], item[1]))
    ranked_lessons.sort(key=lambda item: (-item[0], item[1]))

    selected_patterns = [
        {
            "pattern_id": card["pattern_id"],
            "title_zh": card["title_zh"],
            "strategy_family": card["strategy_family"],
            "mechanism_summary_zh": card["mechanism_summary_zh"],
            "local_data_readiness": card["local_data_readiness"],
            "proposal_eligibility": card["proposal_eligibility"],
            "score": score,
            "matched_mechanism_keys": matched,
        }
        for score, _, matched, card in ranked_patterns[:BROKER_MAX_PATTERNS]
    ]
    selected_lessons = [
        {
            "lesson_id": card["lesson_id"],
            "title_zh": card["title_zh"],
            "outcome": card["outcome"],
            "summary_zh": card["summary_zh"],
            "reuse_policy": card["reuse_policy"],
            "evidence_paths": card["evidence_paths"],
            "score": score,
            "matched_mechanism_keys": matched,
        }
        for score, _, matched, card in ranked_lessons[:BROKER_MAX_LESSONS]
    ]
    identity = {
        "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
        "trigger_fingerprint": trigger_fingerprint,
        "query_terms": [term for term, _ in weighted_terms],
    }
    selection = {
        "schema_version": "knowledge-broker-selection-v1",
        "selection_id": f"knowledge-selection-{fingerprint(identity)[:16]}",
        "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
        "trigger_fingerprint": trigger_fingerprint,
        "query_terms": identity["query_terms"],
        "selected_patterns": selected_patterns,
        "selected_lessons": selected_lessons,
        "limits": {
            "max_patterns": BROKER_MAX_PATTERNS,
            "max_lessons": BROKER_MAX_LESSONS,
            "ranking": "deterministic_weighted_lexical_v2",
        },
        "governance": {
            "class_c_only_result": "reject",
            "proposal_requirement": "at_least_one_A_or_B",
            "candidate_creation_authorized": False,
            "backtest_authorized": False,
            "strategy_mutation_authorized": False,
        },
    }
    selection["selection_fingerprint"] = semantic_fingerprint(selection, "selection_fingerprint")
    validator = jsonschema.Draft202012Validator(load_document(repo / SCHEMA_ROOT / BROKER_SCHEMA))
    validator.validate(selection)
    return selection


def register_broker_usage(
    connection: Any,
    run_id: str,
    selection: dict[str, Any],
    created_at: str,
) -> int:
    """Record the exact knowledge recalled for a Discovery run, idempotently."""
    bindings = [
        ("strategy_pattern", item["pattern_id"], item)
        for item in selection["selected_patterns"]
    ] + [
        ("research_lesson", item["lesson_id"], item)
        for item in selection["selected_lessons"]
    ]
    inserted = 0
    for source_type, source_id, item in bindings:
        lineage_id = fingerprint(
            {
                "selection_fingerprint": selection["selection_fingerprint"],
                "source_type": source_type,
                "source_id": source_id,
                "run_id": run_id,
            }
        )
        payload = {
            "selection_id": selection["selection_id"],
            "selection_fingerprint": selection["selection_fingerprint"],
            "knowledge_snapshot_fingerprint": selection["knowledge_snapshot_fingerprint"],
            "score": item["score"],
            "matched_mechanism_keys": item["matched_mechanism_keys"],
        }
        cursor = connection.execute(
            "INSERT OR IGNORE INTO open_source_knowledge_lineage("
            "lineage_id,source_type,source_id,relation,target_type,target_id,payload_json,created_at"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (
                lineage_id,
                source_type,
                source_id,
                "retrieved_for",
                "discovery_run",
                run_id,
                json.dumps(payload, sort_keys=True),
                created_at,
            ),
        )
        inserted += cursor.rowcount
        stored = connection.execute(
            "SELECT source_type,source_id,relation,target_type,target_id,payload_json,created_at "
            "FROM open_source_knowledge_lineage WHERE lineage_id=?",
            (lineage_id,),
        ).fetchone()
        expected = (source_type, source_id, "retrieved_for", "discovery_run", run_id, json.dumps(payload, sort_keys=True), created_at)
        if stored is None or tuple(stored) != expected:
            raise ValueError("knowledge broker lineage conflict")
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--registry")
    parser.add_argument("--query-key", action="append", default=[])
    parser.add_argument("--strategy-family")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    if args.query_key or args.strategy_family:
        print(json.dumps(retrieve_context(repo, args.query_key, args.strategy_family), indent=2, ensure_ascii=False))
        return 0
    manifest = build_knowledge(repo)
    result: dict[str, Any] = {"manifest": manifest}
    if args.registry:
        result["registry"] = register_knowledge(repo, Path(args.registry), manifest)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
