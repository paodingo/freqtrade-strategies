#!/usr/bin/env python3
"""Render the approved BNB/XRP descriptive Discovery worker outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from research_director_common import load_document, write_json


ROOT = Path(__file__).resolve().parents[1]
STATE_FP = "67c3311d8d84d1ef745c3b0c89357a40271197814903f53a570d8cc8fc260dc0"
SELECTION_ID = ""
SELECTION_FP = ""
LESSONS = [
    "cross-pair-reproducibility-not-generalization-v1",
    "regime-directionality-rotation-no-threshold-search-v1",
    "ranging-short-temporal-retention-v1",
    "exit-frequency-insufficient-causal-evidence-v1",
]
DATASETS = [
    "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
    "futures-dev-eth-usdt-usdt-20240101-20240830-v1",
    "futures-dev-bnb-usdt-usdt-20240101-20240830-v1",
    "futures-dev-xrp-usdt-usdt-20240101-20240830-v1",
]


def _knowledge_use(title: str, patterns: list[str]) -> dict[str, Any]:
    explanations = {
        LESSONS[0]: f"{title}只检验描述性结构，不把可复现性解释为盈利或经济泛化。",
        LESSONS[1]: f"{title}不搜索相邻阈值，也不据方向轮动修改策略。",
        LESSONS[2]: f"{title}不重开震荡做空整体删除，仅比较新增币种的描述性结构。",
        LESSONS[3]: f"{title}不依据退出频率改写退出或风险语义。",
    }
    return {
        "selection_id": SELECTION_ID,
        "selection_fingerprint": SELECTION_FP,
        "used_pattern_ids": patterns,
        "considered_lesson_ids": LESSONS,
        "material_difference_from_lessons": [
            {"lesson_id": lesson, "explanation": explanations[lesson]}
            for lesson in LESSONS
        ],
        "rationale": "Knowledge Broker 仅约束重复研究；提案资格来自已封存 Development 数据和内部 A 类证据。",
    }


def _idea(spec: dict[str, Any]) -> dict[str, Any]:
    title = spec["title"]
    return {
        "schema_version": "research-idea-v1",
        "idea_id": spec["idea_id"],
        "idea_version": 1,
        "strategy_family": spec["strategy_family"],
        "title": title,
        "plain_language_summary_zh": spec["summary"],
        "falsifiable_hypothesis": spec["hypothesis"],
        "proposed_market_mechanism": spec["mechanism"],
        "supporting_evidence": spec["supporting"],
        "contradictory_evidence": spec["contradictory"],
        "source_refs": [
            {
                "source_class": "A",
                "path": "research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml",
                "claim": "BNB Development 数据已封存且必需数据流零缺口。",
            },
            {
                "source_class": "A",
                "path": "research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml",
                "claim": "XRP Development 数据已封存且必需数据流零缺口。",
            },
            {
                "source_class": "A",
                "path": "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json",
                "claim": "ETH 行为可复现但不证明跨币种经济泛化。",
            },
            {
                "source_class": "A",
                "path": "research/director/current-research-state.json",
                "claim": "BNB/XRP 已获 Development-only 描述性研究授权。",
            },
        ],
        "novelty_vs_existing_research": spec["novelty"],
        "required_datasets": DATASETS,
        "data_readiness": "ready",
        "fixed_scope_confirmation": {
            "exchange": "binance",
            "market": "USD-M Futures",
            "margin_mode": "isolated",
            "primary_timeframe": "1h",
            "informative_timeframes": ["4h"],
            "development_only": True,
            "risk_parameters_unchanged": True,
            "new_dataset": False,
            "validation_access": False,
            "holdout_access": False,
        },
        "minimal_test_method": spec["method"],
        "comparison_baseline": spec["baseline"],
        "expected_information_gain": spec["information_gain"],
        "estimated_cost": {
            "experiments": 0,
            "wall_clock_minutes": spec["minutes"],
            "compute_class": "low",
        },
        "risk_class": spec["risk"],
        "contamination_risk": spec["contamination"],
        "falsification_conditions": spec["falsification"],
        "stop_conditions": [
            "任何步骤需要回测、Candidate、策略修改或参数搜索",
            "任何步骤需要 Validation、Holdout、私有 API 或网络下载",
            "任何必需 Development 数据流完整性校验失败",
        ],
        "known_limitations": spec["limitations"],
        "knowledge_use": _knowledge_use(title, spec["patterns"]),
        "research_state_fingerprint": STATE_FP,
    }


def ideas() -> list[dict[str, Any]]:
    specs = [
        {
            "idea_id": "bnb-xrp-distribution-shift-profile-v1",
            "strategy_family": "cross_pair_descriptive",
            "title": "BNB/XRP 收益与波动分布迁移画像",
            "summary": "只计算四个 Development 币种的收益、实现波动、尾部幅度和成交量分位数，形成同窗描述矩阵。",
            "hypothesis": "若 BNB/XRP 在多数冻结分段的波动与尾部幅度相对 BTC/ETH 保持稳定排序，则后续跨币种研究可采用分层而非单一尺度；若排序频繁翻转则否定。",
            "mechanism": "资产波动尺度和尾部厚度差异可能改变固定信号条件的可达性，但描述差异本身不授权策略调整。",
            "supporting": ["四个数据集共享同一 Development 时间边界。", "BNB/XRP 1h 与 4h 流均零缺口。"],
            "contradictory": ["ETH 的可复现行为没有带来经济泛化。", "单一 2024 窗口可能混入阶段特异性。"],
            "novelty": "现有证据比较 BTC/ETH 策略行为，本方向先比较 BNB/XRP 的无策略市场分布。",
            "method": "读取 1h/4h Development 数据，按预先固定的全窗和四个时间分段输出分位数与稳健尺度；不生成信号或交易。",
            "baseline": "BTC/ETH 同窗同分段的无策略收益与波动统计。",
            "information_gain": 0.94,
            "minutes": 35,
            "risk": "low",
            "contamination": "none",
            "falsification": ["相对排序在多数分段翻转。", "差异主要由缺口、重复或边界不一致解释。"],
            "limitations": ["描述统计不能证明策略泛化。", "不包含订单簿和成交成本。"],
            "patterns": ["multi-symbol-timeframe-composition"],
        },
        {
            "idea_id": "bnb-xrp-timeframe-coherence-v1",
            "strategy_family": "cross_pair_descriptive",
            "title": "BNB/XRP 1h—4h 多周期一致性审计",
            "summary": "比较各币种 1h 聚合结果与已封存 4h 数据在方向、波动和极端区间上的一致性。",
            "hypothesis": "若 BNB/XRP 的 1h—4h 一致性显著低于 BTC/ETH 且跨分段持续，则多周期条件的跨币种可比性不足；否则该前置风险被否定。",
            "mechanism": "多周期一致性决定高周期状态信息能否与低周期观察形成可比较的时间结构。",
            "supporting": ["四个币种均有同窗 1h 与 4h 数据。", "多周期组合是 Broker 召回的相关机制。"],
            "contradictory": ["时间聚合一致不代表状态条件一致。", "交易所归档数据本身可能机械地高度一致。"],
            "novelty": "区别于清单完整性审计，本方向检验已封存数值在跨周期上的结构一致性。",
            "method": "用固定 UTC 桶将 1h 数据聚合为 4h，与封存 4h 数据做无策略一致性比较并列出异常。",
            "baseline": "BTC/ETH 的同类 1h—4h 一致性统计。",
            "information_gain": 0.86,
            "minutes": 30,
            "risk": "low",
            "contamination": "none",
            "falsification": ["BNB/XRP 与 BTC/ETH 的一致性差异不稳定。", "观察差异全部来自数值精度而非时间结构。"],
            "limitations": ["不检验策略 informative merge。", "不涉及信号或收益。"],
            "patterns": ["multi-symbol-timeframe-composition"],
        },
        {
            "idea_id": "bnb-xrp-regime-occupancy-transfer-v1",
            "strategy_family": "regime_structure",
            "title": "BNB/XRP 状态占用与可达性迁移",
            "summary": "依据现有只读条件图定义，设计各市场状态代理的占用率、持续时间和方向不平衡描述。",
            "hypothesis": "若 BNB/XRP 在多数时间分段持续缺失 BTC/ETH 可达的状态区域，则共享状态路由的跨币种描述基础不足；若占用结构相近则否定。",
            "mechanism": "市场状态的可达性差异可能先于任何交易结果暴露跨币种结构偏移。",
            "supporting": ["现有条件图记录了状态结构。", "既有研究观察到方向轮动但未授权阈值搜索。"],
            "contradictory": ["代理占用不等于真实交易触发。", "禁止读取策略实现可能限制精确复刻。"],
            "novelty": "只做状态占用描述，不重复阈值搜索、分支删除或策略回测。",
            "method": "先冻结条件图中可由允许来源重建的无交易状态代理，再计算四币种分段占用、持续时间和不可达项；无法重建则停止。",
            "baseline": "BTC/ETH 已有状态结构与方向分布证据。",
            "information_gain": 0.90,
            "minutes": 45,
            "risk": "medium",
            "contamination": "low",
            "falsification": ["允许来源不足以无歧义重建状态代理。", "状态占用差异没有跨分段持续性。"],
            "limitations": ["不能读取策略代码或生成交易信号。", "状态代理可能遗漏执行语义。"],
            "patterns": ["multi-timeframe-regime-gating"],
        },
        {
            "idea_id": "bnb-xrp-funding-mark-stress-v1",
            "strategy_family": "derivatives_microstructure",
            "title": "BNB/XRP 资金费率与标记价格压力画像",
            "summary": "利用封存 8h funding_rate 与 mark 流描述极端资金费率、标记收益和波动压力的共现。",
            "hypothesis": "若 BNB/XRP 的极端资金费率与标记价格压力共现率持续高于 BTC/ETH，则衍生品持仓环境存在可描述的币种层差异；否则否定。",
            "mechanism": "永续合约资金压力可能与标记价格波动共同刻画拥挤状态，但不等同于可交易基差。",
            "supporting": ["BNB/XRP 均有零缺口 8h mark 与 funding_rate。", "四币种同窗便于分段比较。"],
            "contradictory": ["没有现货基差和订单簿。", "资金费率共现不证明因果或套利收益。"],
            "novelty": "不同于 Broker 的 funding-basis 套利灵感，本方向明确排除现货腿和交易设计，仅做永续数据描述。",
            "method": "固定分位数定义后计算 8h funding_rate 与 mark 变化的共现表、持续时长和分段稳定性。",
            "baseline": "BTC/ETH 同窗 8h funding_rate 与 mark 描述统计。",
            "information_gain": 0.88,
            "minutes": 30,
            "risk": "low",
            "contamination": "none",
            "falsification": ["共现差异不跨分段持续。", "资金费率时间戳无法与 mark 8h 桶严格对齐。"],
            "limitations": ["不包含现货价格、订单簿或真实资金成本。", "不得推导套利或持仓建议。"],
            "patterns": ["multi-symbol-timeframe-composition"],
        },
        {
            "idea_id": "bnb-xrp-cross-pair-dependence-v1",
            "strategy_family": "portfolio_structure",
            "title": "四币种相关性与压力同步性描述",
            "summary": "比较 BTC、ETH、BNB、XRP 在普通期与尾部压力期的同步性和相关性稳定度。",
            "hypothesis": "若 BNB/XRP 仅在压力期与 BTC/ETH 高度同步、普通期明显分化，则跨币种证据不能被当作独立样本；若两类时期均低同步则否定。",
            "mechanism": "共同市场冲击会降低多币种证据的有效独立性，并夸大表面泛化。",
            "supporting": ["四币种具有同窗 1h 数据。", "现有泛化结论仍未成立。"],
            "contradictory": ["只有四个资产，横截面很小。", "相关性对时间切片敏感。"],
            "novelty": "从证据独立性而非策略收益角度审计跨币种样本价值。",
            "method": "预先固定普通期与尾部压力定义，输出滚动相关、尾部共现和分段区间；不做组合构建。",
            "baseline": "BTC/ETH 双币种同窗相关结构。",
            "information_gain": 0.82,
            "minutes": 35,
            "risk": "low",
            "contamination": "low",
            "falsification": ["压力期与普通期同步差异不稳定。", "结果对单一窗口长度高度敏感。"],
            "limitations": ["四币种不能代表完整市场。", "不构成分散化或配置结论。"],
            "patterns": ["cross-sectional-factor-ranking"],
        },
        {
            "idea_id": "bnb-xrp-volume-price-coupling-v1",
            "strategy_family": "market_activity",
            "title": "BNB/XRP 量价耦合稳定性审计",
            "summary": "比较四币种成交量异常与绝对收益、波动扩张之间的同窗关系。",
            "hypothesis": "若 BNB/XRP 的量价耦合方向或强度在多数分段与 BTC/ETH 相反，则基于相同活动代理的跨币种解释不稳健；否则否定。",
            "mechanism": "成交活动与价格变化的耦合差异可能反映市场参与结构差异。",
            "supporting": ["1h OHLCV 数据完整且同窗。", "无需策略信号即可计算活动代理。"],
            "contradictory": ["交易所成交量不代表全市场活动。", "量价关系可能由波动机械驱动。"],
            "novelty": "补充收益分布画像，专门检验成交活动代理的跨币种稳定性。",
            "method": "以各币种自身历史分位数定义成交量异常，比较其与绝对收益和后续无条件波动的描述关系。",
            "baseline": "BTC/ETH 同窗量价耦合统计。",
            "information_gain": 0.74,
            "minutes": 30,
            "risk": "low",
            "contamination": "low",
            "falsification": ["量价耦合差异不跨分段持续。", "关系在控制波动尺度后消失。"],
            "limitations": ["成交量口径仅限 Binance USD-M。", "不推断因果或交易优势。"],
            "patterns": [],
        },
    ]
    return [_idea(spec) for spec in specs]


def critiques(run_path: Path) -> list[dict[str, Any]]:
    ideas_by_id = {
        payload["idea_id"]: payload
        for payload in (
            load_document(path) for path in sorted((run_path / "ideas").glob("*.json"))
        )
    }
    specs = {
        "bnb-xrp-distribution-shift-profile-v1": ("reject", [0.94, 0.94, 0.96, 0.10, 0.95], ["该方向已完成同窗、四分段的描述分析，属于语义重复。"]),
        "bnb-xrp-timeframe-coherence-v1": ("pass", [0.92, 0.94, 0.97, 0.93, 0.94], []),
        "bnb-xrp-regime-occupancy-transfer-v1": ("pass", [0.90, 0.88, 0.78, 0.91, 0.94], []),
        "bnb-xrp-funding-mark-stress-v1": ("pass", [0.88, 0.90, 0.94, 0.92, 0.88], []),
        "bnb-xrp-cross-pair-dependence-v1": ("reject", [0.82, 0.84, 0.93, 0.62, 0.82], ["四币种样本不足以稳定区分独立性与共同冲击。"]),
        "bnb-xrp-volume-price-coupling-v1": ("reject", [0.74, 0.82, 0.92, 0.65, 0.78], ["与分布迁移画像信息重叠，优先级不足。"]),
    }
    keys = [
        "expected_information_gain",
        "falsifiability_and_mechanism_clarity",
        "feasibility_with_existing_data",
        "novelty_and_non_duplication",
        "robustness_relevance",
    ]
    results = []
    for idea_id, (verdict, values, fatal) in specs.items():
        idea = ideas_by_id[idea_id]
        results.append({
            "schema_version": "research-critique-v1",
            "critique_id": f"critique-{idea_id}-{run_path.name.removeprefix('discovery-run-')}",
            "idea_id": idea_id,
            "idea_semantic_fingerprint": idea["semantic_fingerprint"],
            "verdict": verdict,
            "source_verification": {"highest_class": "A"},
            "duplicate_research_check": "已核对四张 Broker 经验卡与既有 BTC/ETH 研究；未重复阈值搜索、退出改写或分支删除。",
            "falsifiability_assessment": "假设、反证条件、最小描述方法和停止条件均可由固定 Development 数据直接判定。",
            "data_readiness_assessment": "BNB/XRP 及比较基线均已封存；本轮只生成提案，不执行描述计算。",
            "leakage_and_overfit_risks": ["禁止按未来收益筛选统计口径。", "禁止访问 Validation/Holdout。", "分段和分位数必须在分析前固定。"],
            "transaction_cost_challenge": "本轮不计算策略收益；任何后续经济解释仍需独立的成本授权与证据。",
            "strongest_counterevidence": "ETH 的稳定复现没有证明经济泛化，说明新增币种的描述相似也不能直接支持策略。",
            "alternative_explanations": ["共同市场冲击", "资产波动尺度差异", "成交活动结构差异", "单一时间窗口偏差"],
            "fatal_objections": fatal,
            "score_adjustments": ["优先考虑可由当前封存数据完成、且不触碰交易执行的高信息增益方向。"],
            "knowledge_verification": {
                "selection_id": SELECTION_ID,
                "selection_fingerprint": SELECTION_FP,
                "idea_knowledge_use_verified": True,
                "lesson_checks": [
                    {"lesson_id": lesson, "result": "confirmed_distinct"}
                    for lesson in LESSONS
                ],
                "status": "verified",
                "notes": "知识选择身份、模式卡和四张经验卡差异说明均已核验。",
            },
            "ranking_inputs": dict(zip(keys, values)),
        })
    return results


def main(argv: list[str] | None = None) -> int:
    global SELECTION_ID, SELECTION_FP
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ideas", "critiques"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--inbox", required=True)
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    run_path = repo / "research/discovery/runs" / args.run_id
    task_name = "researcher-task.md" if args.mode == "ideas" else "critic-task.md"
    task_text = (run_path / task_name).read_text(encoding="utf-8")
    selection_ids = re.findall(r'"selection_id"\s*:\s*"(knowledge-selection-[a-f0-9]{16})"', task_text)
    selection_fingerprints = re.findall(r'"selection_fingerprint"\s*:\s*"([a-f0-9]{64})"', task_text)
    if len(set(selection_ids)) != 1 or len(set(selection_fingerprints)) != 1:
        raise ValueError("task packet has no unique Knowledge Broker selection binding")
    SELECTION_ID = selection_ids[0]
    SELECTION_FP = selection_fingerprints[0]
    documents = ideas() if args.mode == "ideas" else critiques(run_path)
    inbox = Path(args.inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    for document in documents:
        key = document["idea_id"] if args.mode == "ideas" else document["critique_id"]
        write_json(inbox / f"{key}.json", document)
    print(json.dumps({"mode": args.mode, "written": len(documents), "inbox": str(inbox)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
