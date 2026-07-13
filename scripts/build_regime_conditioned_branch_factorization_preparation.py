#!/usr/bin/env python3
"""Build read-only structure and human-review artifacts from a compiled Campaign."""

from __future__ import annotations

import json
from pathlib import Path

from research_director_common import fingerprint, load_document, write_json


ROOT = Path(__file__).resolve().parents[1]
COMPILED = ROOT / "research/director/compiled/regime-conditioned-branch-factorization-v1"
ANALYSIS = ROOT / "research/analysis/regime-conditioned-branch-factorization"


def build() -> tuple[dict, dict, str]:
    campaign = load_document(COMPILED / "campaign.yaml")
    metadata = load_document(COMPILED / "compilation-metadata.json")
    plan = campaign["structural_research_plan"]
    current = plan["current_structure"]
    computed = fingerprint(
        {key: value for key, value in campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}}
    )
    if computed != campaign["campaign_fingerprint"] or computed != metadata["campaign_fingerprint"]:
        raise ValueError("compiled Campaign fingerprint drift")
    if campaign["execution_authorized"] or metadata["execution_authorized"]:
        raise ValueError("preparation cannot run for an execution-authorized Campaign")

    conditions_by_owner = {
        owner: [item["condition_id"] for item in current["condition_ownership"] if item["owner"] == owner]
        for owner in ("shared_router", "long_branch", "short_branch")
    }
    regime_branches: dict[str, list[dict]] = {}
    for group in current["signal_groups"]:
        regime_branches.setdefault(group["regime_branch"], []).append(
            {
                "group_id": group["group_id"],
                "branch": group["branch"],
                "side": group["side"],
                "signal": group["signal"],
                "condition_count": len(group["conditions"]),
                "conditions": group["conditions"],
            }
        )
    structure = {
        "schema_version": "regime-conditioned-current-structure-map-v1",
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "source": current["source"],
        "condition_count": current["condition_count"],
        "signal_group_count": current["signal_group_count"],
        "condition_owner_counts": current["condition_owner_counts"],
        "conditions_by_owner": conditions_by_owner,
        "condition_ownership": current["condition_ownership"],
        "regime_branches": regime_branches,
        "formal_strategy_modified": False,
        "candidate_created": False,
        "backtest_run": False,
    }
    hypothesis = plan["minimum_testable_hypothesis"]
    packet = {
        "schema_version": "regime-conditioned-branch-factorization-human-decision-packet-v1",
        "proposal_id": campaign["proposal_id"],
        "proposal_fingerprint": campaign["proposal_fingerprint"],
        "compiled_campaign_fingerprint": campaign["campaign_fingerprint"],
        "risk_class": campaign["risk_class"],
        "status": "awaiting_human_execution_approval",
        "current_authority": campaign["current_authority"],
        "execution_authorized": False,
        "minimum_research_unit": hypothesis,
        "expected_candidate_count": hypothesis["candidate_count"],
        "expected_backtest_invocations": hypothesis["backtest_invocations"],
        "sequence_decision": "prove_structure_equivalence_before_any_branch_contribution_ablation",
        "read_only_steps_completed": [
            "revalidate Current Research State and Proposal fingerprint",
            "compile and fingerprint the dry-run Campaign Spec",
            "map 29 conditions and five signal groups",
            "freeze single-variable, budget, stop and acceptance gates",
        ],
        "future_candidate_steps_not_authorized": [
            "create one router-extraction Candidate",
            "run four BTC baseline/Candidate fresh-process Backtests",
            "run four ETH baseline/Candidate fresh-process Backtests",
        ],
        "branch_ablation": {
            "included_in_compiled_campaign": False,
            "reason": "Ablation before equivalence would mix structural extraction with contribution change.",
            "required_next_gate": "separate Proposal, Campaign fingerprint and human approval after exact equivalence",
        },
        "primary_risks": [
            "accidental strategy-semantic change disguised as refactor",
            "multiple structural variables changed in one Candidate",
            "reopening the closed threshold branch",
            "false equivalence from non-fresh processes or incomplete signal comparison",
            "Validation/Holdout contamination or formal baseline mutation",
        ],
        "execution_approval_checklist": [
            "approve the exact compiled Campaign fingerprint",
            "approve exactly one Candidate path and router-extraction diff allowlist",
            "approve eight development-only Backtest invocations and 120-minute wall-clock budget",
            "confirm BTC and ETH dataset canonical/semantic/aggregate hashes",
            "confirm zero Validation/Holdout access and unchanged risk/execution settings",
            "confirm branch contribution ablation remains excluded",
        ],
        "decision_rules": plan["decision_rules"],
        "formal_execution_baseline": "RegimeAwareV6",
        "formal_strategy_modified": False,
        "candidate_created": False,
        "backtest_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    owner_lines = []
    for owner, ids in conditions_by_owner.items():
        owner_lines.append(f"- `{owner}` ({len(ids)}): " + ", ".join(f"`{item}`" for item in ids))
    group_lines = []
    for regime, groups in regime_branches.items():
        for group in groups:
            group_lines.append(
                f"- `{regime}` -> `{group['group_id']}` / `{group['side']}` / `{group['signal']}` ({group['condition_count']} conditions)"
            )
    markdown = f"""# Current Regime-conditioned Structure Map

Campaign fingerprint: `{campaign['campaign_fingerprint']}`

```mermaid
flowchart TD
  R["Shared regime router"] --> T["Trending regime"]
  R --> G["Ranging regime"]
  T --> TL["trending_long_entry"]
  T --> TS["trending_short_entry"]
  G --> RL["ranging_long_entry"]
  G --> RS["ranging_short_entry"]
  G --> RB["ranging_breakdown_exit_long"]
  TL --> EL["enter_long"]
  RL --> EL
  TS --> ES["enter_short"]
  RS --> ES
  RB --> XL["exit_long"]
```

## Condition ownership

{chr(10).join(owner_lines)}

All 29 conditions have exactly one structural owner. Shared conditions may be consumed by multiple regime/signal groups without being duplicated.

## Regime and signal groups

{chr(10).join(group_lines)}

## Frozen research order

1. Current work: read-only mapping and dry-run compilation only.
2. Future approval: exactly one Candidate extracting only the router interface/location.
3. Exact semantic-equivalence gate: 8 Backtest invocations across baseline/Candidate, BTC/ETH and RUN-A/RUN-B.
4. Any branch contribution ablation is a separate, later Campaign after equivalence and new human approval.
"""
    return structure, packet, markdown


def main() -> int:
    structure, packet, markdown = build()
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    write_json(ANALYSIS / "current-structure-map.json", structure)
    (ANALYSIS / "current-structure-map.md").write_text(markdown, encoding="utf-8")
    write_json(COMPILED / "human-decision-packet.json", packet)
    print(
        json.dumps(
            {
                "campaign_fingerprint": packet["compiled_campaign_fingerprint"],
                "conditions": structure["condition_count"],
                "signal_groups": structure["signal_group_count"],
                "execution_authorized": packet["execution_authorized"],
                "candidate_created": packet["candidate_created"],
                "backtest_run": packet["backtest_run"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
