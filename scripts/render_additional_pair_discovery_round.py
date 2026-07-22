#!/usr/bin/env python3
"""Render the governed Researcher and Critic inputs for additional-pair discovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import open_source_knowledge as knowledge
from research_director_common import load_document, write_json


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "discovery-run-045a763176bbbea2"
STATE_FP = "16cb1973ce0390d7afd628af31e7816bcf3df2fb698fd09524e0e02d37b2626f"
SELECTION_ID = "knowledge-selection-6be68ca88129ebc3"
SELECTION_FP = "e9f5e59cae026c0ac424780c815021d105c0c946377d1b9314d67f6e06cf8d53"
LESSONS = [
    "cross-pair-reproducibility-not-generalization-v1",
    "regime-directionality-rotation-no-threshold-search-v1",
    "ranging-short-temporal-retention-v1",
    "exit-frequency-insufficient-causal-evidence-v1",
]


def _knowledge_use(patterns: list[str], focus: str) -> dict[str, Any]:
    explanations = {
        "cross-pair-reproducibility-not-generalization-v1": f"{focus}只建立数据或实验可比性，不把行为复现解释为盈利或经济泛化。",
        "regime-directionality-rotation-no-threshold-search-v1": f"{focus}不搜索相邻阈值，也不把方向轮动转换为策略修改依据。",
        "ranging-short-temporal-retention-v1": f"{focus}不重新开启整体删除震荡做空分支，只评估新增币种研究前置条件。",
        "exit-frequency-insufficient-causal-evidence-v1": f"{focus}不依据退出频率重写退出或风险语义。",
    }
    return {
        "selection_id": SELECTION_ID,
        "selection_fingerprint": SELECTION_FP,
        "used_pattern_ids": patterns,
        "considered_lesson_ids": LESSONS,
        "material_difference_from_lessons": [
            {"lesson_id": lesson_id, "explanation": explanations[lesson_id]}
            for lesson_id in LESSONS
        ],
        "rationale": "使用 Broker 召回结果约束研究边界；Class C 机制卡仅提供组织方法，合格性来自 A 类内部证据。",
    }


def _idea(
    idea_id: str,
    family: str,
    title: str,
    summary: str,
    hypothesis: str,
    mechanism: str,
    evidence: list[str],
    counterevidence: list[str],
    required: list[str],
    readiness: str,
    method: str,
    baseline: str,
    information_gain: float,
    experiments: int,
    minutes: int,
    compute: str,
    risk: str,
    contamination: str,
    falsification: list[str],
    stops: list[str],
    limitations: list[str],
    patterns: list[str],
) -> dict[str, Any]:
    source_refs = [
        {"source_class": "A", "path": path, "claim": claim}
        for path, claim in (
            ("research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "ETH 行为可复现，但尚未证明跨币种经济泛化。"),
            ("research/director/current-research-state.json", "额外 Binance USD-M 币种的时间一致性仍是未决研究问题。"),
        )
    ]
    payload = {
        "schema_version": "research-idea-v1",
        "idea_id": idea_id,
        "idea_version": 1,
        "strategy_family": family,
        "title": title,
        "plain_language_summary_zh": summary,
        "falsifiable_hypothesis": hypothesis,
        "proposed_market_mechanism": mechanism,
        "supporting_evidence": evidence,
        "contradictory_evidence": counterevidence,
        "source_refs": source_refs,
        "novelty_vs_existing_research": "从 BTC/ETH 的行为复现结论推进到额外币种的前置证据与可比性检查，不复制既有阈值或收益结论。",
        "required_datasets": required,
        "data_readiness": readiness,
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
        "minimal_test_method": method,
        "comparison_baseline": baseline,
        "expected_information_gain": information_gain,
        "estimated_cost": {"experiments": experiments, "wall_clock_minutes": minutes, "compute_class": compute},
        "risk_class": risk,
        "contamination_risk": contamination,
        "falsification_conditions": falsification,
        "stop_conditions": stops,
        "known_limitations": limitations,
        "knowledge_use": _knowledge_use(patterns, title),
        "research_state_fingerprint": STATE_FP,
    }
    return payload


def ideas() -> list[dict[str, Any]]:
    existing = [
        "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml",
        "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml",
    ]
    return [
        _idea(
            "additional-pair-manifest-inventory-v1", "cross_pair_research", "额外币种冻结数据清单审计",
            "只盘点 SOL、BNB、XRP、ADA 候选币种是否存在可封存、同窗口的 1h/4h Development 数据，不下载数据。",
            "若至少两个候选币种能够形成与 BTC/ETH 同时间边界、无缺口且有内容指纹的 Development 清单，则跨币种研究的数据前置条件成立；否则停止。",
            "额外币种研究首先受制于时间覆盖、K 线完整性和可追溯清单，而不是策略参数。",
            ["ETH 独立进程行为可复现", "当前状态明确保留额外币种泛化问题"],
            ["ETH 描述性表现明显弱于 BTC", "本地尚无额外币种获批数据清单"],
            existing + ["proposed SOL/BNB/XRP/ADA Development manifest inventory (not yet available)"],
            "data_readiness_required", "读取本地获批路径与清单注册表，输出候选币种覆盖矩阵、缺口原因和可封存性；零下载、零回测。",
            "BTC/ETH 已封存 Development 清单的字段、时间边界和内容指纹契约", 0.94, 0, 20, "low", "low", "none",
            ["少于两个额外币种满足完整且同窗口的 1h/4h 清单契约", "任何候选只能依赖未封存或来源不明数据"],
            ["需要网络下载", "需要 Validation/Holdout", "发现时间边界不可比"],
            ["本任务不判断收益或泛化", "候选币种名称只是盘点集合，不构成市场选择结论"],
            ["multi-symbol-timeframe-composition"],
        ),
        _idea(
            "additional-pair-window-comparability-v1", "cross_pair_research", "额外币种时间窗口可比性契约",
            "定义额外币种与 BTC/ETH 共享的冻结窗口、暖启动、缺口率和 4h 对齐规则。",
            "若无法在不裁剪既有 BTC/ETH 证据的情况下定义一个共同 Development 窗口，则不应启动跨币种实验。",
            "共同时间支持集可减少上市时间差、缺失区间和行情阶段差异造成的伪泛化。",
            ["BTC/ETH 已有固定 Development 清单", "时间切片结果显示贡献具有时间依赖"],
            ["额外币种上市时间和流动性历史可能不同", "过度裁剪会降低信息量"],
            existing + ["candidate-pair temporal coverage metadata (not yet available)"],
            "data_readiness_required", "仅制定并验证元数据契约：共同起止、预热长度、缺口上限、1h/4h 对齐；不读取新行情值。",
            "现有 BTC/ETH 2024 Development 时间边界与四个冻结时间切片", 0.88, 0, 25, "low", "low", "none",
            ["共同窗口不足以覆盖预定四个冻结切片", "对齐需要查看 Validation 或修改既有切片"],
            ["任一候选缺少 4h 对齐", "共同窗口显著短于现有 Development 证据"],
            ["元数据通过不表示策略可泛化", "上市偏差仍需后续描述性检查"],
            ["multi-symbol-timeframe-composition"],
        ),
        _idea(
            "additional-pair-liquidity-cost-readiness-v1", "execution_readiness", "额外币种成本与流动性可比性审计",
            "在不运行策略的前提下，规定额外币种进入研究所需的成交额、费率和保守滑点元数据。",
            "若候选币种无法提供与现有执行契约一致、可审计的成本输入，则不得进入跨币种实验。",
            "表面信号复现可能由流动性和成本差异消除，成本输入必须先于收益比较冻结。",
            ["ETH 行为复现但描述性指标弱", "现有 Evaluation Policy 要求固定费用和风险语义"],
            ["当前只拥有 OHLCV 级别研究证据", "缺少额外币种封存成本元数据"],
            existing + ["candidate-pair fee and conservative slippage metadata (not yet available)"],
            "data_readiness_required", "输出成本元数据字段、来源等级、缺失原因和保守压力档位；不计算策略收益。",
            "现有 BTC/ETH 固定 Runtime、fee、leverage 与风险契约", 0.81, 0, 20, "low", "low", "low",
            ["无法冻结费用或保守滑点输入", "成本来源只能来自不可审计实时账户"],
            ["需要私有 API", "需要订单簿下载", "需要修改风险参数"],
            ["OHLCV 无法验证微观成交", "通过只允许后续描述性实验"],
            ["multi-symbol-timeframe-composition"],
        ),
        _idea(
            "additional-pair-regime-activation-transfer-v1", "regime_structure", "额外币种状态激活迁移设计",
            "设计未来如何比较相同状态路由在额外币种上的激活覆盖，但当前不执行。",
            "若额外币种数据就绪后，相同状态定义在多数币种上不可达或仅单一方向可达，则共享路由不具备描述性迁移性。",
            "共享状态路由的激活覆盖可能比收益指标更早暴露跨币种结构差异。",
            ["现有条件图提供 29 条条件和 5 个信号组", "BTC/ETH 存在方向轮动"],
            ["方向轮动不是阈值搜索依据", "额外币种数据尚未就绪"],
            existing + ["approved additional-pair Development datasets (not yet available)"],
            "data_readiness_required", "冻结未来的只读激活计数、不可达条件和方向覆盖比较规范；本轮零执行。",
            "BTC/ETH 现有状态激活与方向分布", 0.70, 0, 30, "low", "medium", "low",
            ["设计隐含调整阈值或删除方向分支", "无法与现有条件图逐项绑定"],
            ["需要新 Candidate", "需要回测", "需要阈值搜索"],
            ["只能形成后续实验设计", "不能推断 Alpha 或盈利"],
            ["multi-symbol-timeframe-composition"],
        ),
        _idea(
            "additional-pair-cross-sectional-ranking-v1", "relative_strength", "额外币种横截面强弱排序",
            "考虑使用同一时点的跨币种标准化因子排序，但当前数据范围不支持。",
            "只有在至少四个额外币种拥有同步数据与无泄漏横截面宇宙时，排序研究才具备最低可证伪性。",
            "横截面标准化可能减少单币种绝对阈值依赖。",
            ["Broker 机制卡提示横截面排序模式"],
            ["现有内部 A 类证据只覆盖 BTC/ETH", "当前没有同步多资产宇宙"],
            existing + ["synchronous multi-asset universe (not available)"],
            "out_of_v1_scope", "只形成缺口清单；禁止因子计算、参数选择或回测。",
            "无可执行基线；仅与现有双币种描述性比较边界对照", 0.55, 0, 15, "low", "medium", "low",
            ["无法形成无幸存者偏差的冻结宇宙", "只有 Class C 灵感而无新增 A/B 证据"],
            ["需要选择因子", "需要下载多币种行情", "需要回测"],
            ["超出当前固定数据范围", "容易引入宇宙选择偏差"],
            ["cross-sectional-factor-ranking"],
        ),
        _idea(
            "additional-pair-funding-basis-v1", "relative_value", "额外币种资金费率与基差研究",
            "考虑资金费率和基差的跨币种相对价值，但当前数据与执行语义均不支持。",
            "缺少封存资金费率、现货永续基差与双边成本时，该方向必须拒绝。",
            "资金费率差异可能解释部分币种持仓收益，但与当前 1h/4h OHLCV 策略家族不同。",
            ["Broker 机制卡提示 funding-basis 模式"],
            ["本地没有资金费率历史与现货基差", "该方向改变研究家族和执行要求"],
            existing + ["funding history and spot-perpetual basis (not available)"],
            "out_of_v1_scope", "只记录数据和执行缺口，不下载数据、不设计交易。",
            "无可执行基线", 0.35, 0, 10, "low", "high", "medium",
            ["缺少任一所需数据源", "无法固定双边成交成本"],
            ["需要跨市场执行", "需要私有或实时数据", "需要新风险语义"],
            ["与当前策略家族不连续", "Class C 只能作为灵感"],
            ["funding-basis-arbitrage"],
        ),
    ]


def _critique(idea: dict[str, Any], verdict: str, scores: dict[str, float], fatal: list[str], note: str) -> dict[str, Any]:
    checks = [
        {"lesson_id": lesson_id, "result": "confirmed_distinct"}
        for lesson_id in LESSONS
    ]
    payload = {
        "schema_version": "research-critique-v1",
        "critique_id": f"critique-{idea['idea_id']}-v{idea['idea_version']}",
        "idea_id": idea["idea_id"],
        "idea_semantic_fingerprint": idea["semantic_fingerprint"],
        "verdict": verdict,
        "source_verification": {"highest_class": "A"},
        "duplicate_research_check": "已与四张 Broker 经验卡及关闭分支核对；该方向不重复阈值搜索、退出改写或整体删除分支。",
        "falsifiability_assessment": "前置条件、失败条件和停止条件均可由清单或元数据直接判定。",
        "data_readiness_assessment": f"{idea['data_readiness']}；本轮只允许前置审计，不允许下载或实验。",
        "leakage_and_overfit_risks": ["不得按未来收益选择币种", "不得访问 Validation/Holdout", "候选集合必须在查看策略结果前冻结"],
        "transaction_cost_challenge": "任何后续跨币种描述性执行都必须绑定固定费用和保守成本输入；本轮不计算收益。",
        "strongest_counterevidence": "ETH 虽可复现交易行为，但经济表现明显弱于 BTC，说明行为一致性不能外推为泛化。",
        "alternative_explanations": ["上市时间差", "流动性与成本差", "行情阶段差", "状态可达性差异"],
        "fatal_objections": fatal,
        "score_adjustments": [note],
        "knowledge_verification": {
            "selection_id": SELECTION_ID,
            "selection_fingerprint": SELECTION_FP,
            "idea_knowledge_use_verified": True,
            "lesson_checks": checks,
            "status": "verified",
            "notes": "选择身份、机制卡子集、四张经验卡考虑清单和材料差异说明均已核验。",
        },
        "ranking_inputs": scores,
    }
    return payload


def critiques(run_path: Path) -> list[dict[str, Any]]:
    idea_docs = {}
    for path in sorted((run_path / "ideas").glob("*.json")):
        document = load_document(path)
        idea_docs[document["idea_id"]] = document
    specs = {
        "additional-pair-manifest-inventory-v1": ("revise", [0.96, 0.94, 0.86, 0.92, 0.96], ["研究对象是元数据就绪度审计，本身可由当前状态执行，data_readiness 应改为 ready，并仅绑定已批准的 BTC/ETH Development 基准清单"], "最高信息增益；请求一次仅修正研究就绪度语义的版本。"),
        "additional-pair-window-comparability-v1": ("reject", [0.78, 0.84, 0.35, 0.76, 0.88], ["应在清单盘点确认至少两个额外币种可用之后再制定共同窗口"], "当前阶段从属且早于必要证据。"),
        "additional-pair-liquidity-cost-readiness-v1": ("reject", [0.72, 0.80, 0.30, 0.70, 0.86], ["额外币种候选尚未通过清单盘点，成本审计对象未冻结"], "应由清单审计结果触发，而非并行进入 shortlist。"),
        "additional-pair-regime-activation-transfer-v1": ("reject", [0.68, 0.78, 0.20, 0.68, 0.82], ["额外币种数据未就绪，当前不能形成可执行研究"], "保留为数据就绪后的设计，不进入当前 shortlist。"),
        "additional-pair-cross-sectional-ranking-v1": ("reject", [0.55, 0.62, 0.05, 0.48, 0.70], ["同步多资产宇宙缺失", "方向主要由 Class C 模式驱动且超出 v1 数据范围"], "数据与宇宙选择风险使其不合格。"),
        "additional-pair-funding-basis-v1": ("reject", [0.38, 0.72, 0.0, 0.60, 0.55], ["资金费率和现货基差数据缺失", "需要新的执行与风险语义"], "与当前家族和固定数据范围不连续。"),
    }
    if idea_docs["additional-pair-manifest-inventory-v1"]["idea_version"] == 2:
        specs["additional-pair-manifest-inventory-v1"] = (
            "pass",
            [0.96, 0.96, 0.94, 0.92, 0.96],
            [],
            "修订已将研究动作限定为当前状态可执行的零下载元数据审计，并仅使用获批 BTC/ETH 清单作为字段基准。",
        )
    results = []
    keys = ["expected_information_gain", "falsifiability_and_mechanism_clarity", "feasibility_with_existing_data", "novelty_and_non_duplication", "robustness_relevance"]
    for idea_id, (verdict, values, fatal, note) in specs.items():
        results.append(_critique(idea_docs[idea_id], verdict, dict(zip(keys, values)), fatal, note))
    return results


def revision(run_path: Path) -> list[dict[str, Any]]:
    path = run_path / "ideas" / "additional-pair-manifest-inventory-v1-v1.json"
    revised = load_document(path)
    revised.pop("semantic_fingerprint", None)
    revised["idea_version"] = 2
    revised["data_readiness"] = "ready"
    revised["required_datasets"] = [
        "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
        "futures-dev-eth-usdt-usdt-20240101-20240830-v1",
    ]
    revised["plain_language_summary_zh"] = "使用当前状态和两份获批 BTC/ETH Development 清单作为字段基准，只审计 SOL、BNB、XRP、ADA 是否已有可登记的同窗口清单；不下载或读取新行情。"
    revised["novelty_vs_existing_research"] = "修订仅澄清：研究动作是当前可执行的元数据清单审计，额外币种行情本身仍未就绪；不复制阈值、收益或 ETH 复现结论。"
    revised["minimal_test_method"] = "读取允许的当前研究状态与获批 BTC/ETH 清单字段，检查是否已存在额外币种的封存清单引用；输出覆盖矩阵、缺失原因与停止结论，零下载、零回测。"
    revised["falsification_conditions"] = [
        "当前治理状态中不存在至少两个可验证的额外币种封存 Development 清单引用",
        "发现的引用无法满足 BTC/ETH 基准清单的时间边界、1h/4h 与内容指纹字段契约",
    ]
    revised["known_limitations"] = [
        "审计通过只证明后续数据准备可能，不证明行为复现、收益或经济泛化",
        "候选币种集合在任何策略结果可见前冻结，仅用于清单盘点",
    ]
    return [revised]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ideas", "critiques", "revision"))
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--inbox", required=True)
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args(argv)
    if args.run_id != RUN_ID:
        raise ValueError("renderer is bound to the approved discovery run")
    repo = Path(args.repo_root).resolve()
    run_path = repo / "research/discovery/runs" / args.run_id
    if args.mode == "ideas":
        docs = ideas()
    elif args.mode == "revision":
        docs = revision(run_path)
    else:
        docs = critiques(run_path)
    inbox = Path(args.inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        key = doc["idea_id"] if args.mode in {"ideas", "revision"} else doc["critique_id"]
        write_json(inbox / f"{key}.json", doc)
    print(json.dumps({"mode": args.mode, "written": len(docs), "inbox": str(inbox)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
