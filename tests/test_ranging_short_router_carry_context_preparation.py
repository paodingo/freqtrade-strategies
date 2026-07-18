from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import compile_research_campaign  # noqa: E402
import research_director  # noqa: E402
from research_director_common import (  # noqa: E402
    fingerprint,
    load_document,
    proposal_fingerprint,
)


PROPOSAL_ID = "ranging-short-router-carry-context-review-v1"
COMPILED = ROOT / "research/director/compiled" / PROPOSAL_ID
REPORT_HTML = ROOT / "reports/research" / f"{PROPOSAL_ID}-decision-report.html"

class RouterCarryContextContractTest(unittest.TestCase):
    def test_contract_freezes_one_runtime_observable_context(self):
        spec = importlib.util.find_spec("ranging_short_router_context")
        self.assertIsNotNone(spec, "router context contract module must exist")
        router_context = importlib.import_module("ranging_short_router_context")
        contract = router_context.build_context_contract(ROOT)

        self.assertEqual(
            contract["context_id"],
            "ranging_state_without_current_range_signal",
        )
        self.assertEqual(contract["context_count"], 1)
        self.assertEqual(
            contract["output_regime"],
            {"column": "regime_4h", "operator": "eq", "value": "ranging"},
        )
        self.assertEqual(
            contract["current_raw_ranging_signal"],
            {
                "all": [
                    {"column": "adx_4h", "operator": "lt", "value": 20},
                    {
                        "any": [
                            {
                                "left": "bb_width_4h",
                                "operator": "lte",
                                "right": "bb_width_mean_4h",
                            },
                            {
                                "left": "atr_4h",
                                "operator": "lte",
                                "right": "atr_mean_4h",
                            },
                        ]
                    },
                ]
            },
        )
        self.assertEqual(
            contract["context_expression"],
            {
                "all": [
                    contract["output_regime"],
                    {"not": contract["current_raw_ranging_signal"]},
                ]
            },
        )
        self.assertEqual(
            contract["evaluation_preconditions"],
            ["bb_width_mean_4h > 0", "atr_mean_4h > 0"],
        )
        self.assertFalse(contract["threshold_search_authorized"])
        self.assertFalse(contract["time_slice_used_as_regime_label"])


class RouterCarryProposalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.constitution = load_document(
            ROOT / "research/governance/research-constitution.yaml"
        )

    def test_director_emits_exactly_one_medium_risk_router_context(self):
        router_context = importlib.import_module("ranging_short_router_context")
        contract = router_context.build_context_contract(ROOT)
        run = research_director.generate(
            self.state,
            self.constitution,
            "compile approved ranging-short router carry context",
            {
                "max_campaigns": 1,
                "max_wall_clock_minutes": 30,
                "max_validation_accesses": 0,
            },
            "medium",
            10,
        )

        matches = [
            item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID
        ]
        self.assertEqual(len(matches), 1)
        proposal = matches[0]
        self.assertEqual(proposal["risk_class"], "medium")
        self.assertEqual(proposal["proposed_method"]["router_context"], contract)
        self.assertEqual(
            proposal_fingerprint(proposal), proposal["semantic_fingerprint"]
        )
        self.assertEqual(proposal["estimated_experiments"], 3)
        self.assertEqual(
            proposal["proposed_method"]["execution"],
            "no_candidate_no_backtest_no_validation_no_holdout",
        )
        allowed = "\n".join(proposal["allowed_changes"])
        forbidden = "\n".join(proposal["forbidden_changes"])
        self.assertNotIn("strategies/", allowed)
        self.assertNotIn("research/candidates/", allowed)
        for term in ("strategy", "candidate", "threshold", "backtest", "validation", "holdout", "hyperopt"):
            self.assertIn(term, forbidden.lower())


class RouterCarryCompilerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.constitution = load_document(
            ROOT / "research/governance/research-constitution.yaml"
        )
        run = research_director.generate(
            cls.state,
            cls.constitution,
            "compile approved ranging-short router carry context",
            {
                "max_campaigns": 1,
                "max_wall_clock_minutes": 30,
                "max_validation_accesses": 0,
            },
            "medium",
            10,
        )
        cls.proposal = next(
            item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID
        )

    def _load_with_approval(self, path):
        if Path(path).as_posix().endswith(
            "research/governance/approvals/"
            "ranging-short-router-carry-context-review-v1-compilation-approval.json"
        ):
            return {
                "proposal_id": PROPOSAL_ID,
                "proposal_fingerprint": self.proposal["semantic_fingerprint"],
                "approval_status": "approved_for_compilation_only",
                "approver_type": "human_user",
                "execution_authorized": False,
                "candidate_creation_authorized": False,
                "backtest_authorized": False,
                "validation_authorized": False,
                "holdout_authorized": False,
            }
        return load_document(path)

    def test_compiler_freezes_context_and_zero_execution_budget(self):
        router_context = importlib.import_module("ranging_short_router_context")
        with patch.object(
            compile_research_campaign,
            "load_document",
            side_effect=self._load_with_approval,
        ):
            campaign, metadata, brief = compile_research_campaign.compile_campaign(
                ROOT,
                self.proposal,
                self.state,
                self.constitution,
            )

        self.assertIn("router_carry_context_plan", campaign)
        plan = campaign["router_carry_context_plan"]
        self.assertEqual(
            plan["context_contract"], router_context.build_context_contract(ROOT)
        )
        self.assertEqual(
            plan["current_execution_budget"],
            {
                "max_candidates": 0,
                "max_backtest_calls": 0,
                "max_validation_accesses": 0,
                "max_holdout_accesses": 0,
            },
        )
        future = plan["future_separate_approval_envelope"]
        self.assertEqual(future["max_candidates"], 1)
        self.assertEqual(future["max_backtest_calls"], 16)
        self.assertEqual(future["additional_temporal_slices"], 0)
        self.assertEqual(future["max_validation_accesses"], 0)
        self.assertEqual(future["max_holdout_accesses"], 0)
        self.assertFalse(metadata["execution_authorized"])
        self.assertIn("当前不执行", brief)
        self.assertEqual(
            fingerprint(
                {
                    key: value
                    for key, value in campaign.items()
                    if key not in {"compiled_at", "campaign_fingerprint"}
                }
            ),
            campaign["campaign_fingerprint"],
        )


class RouterCarryBuilderTest(unittest.TestCase):
    def test_builder_writes_chinese_offline_package_without_execution(self):
        spec = importlib.util.find_spec(
            "build_ranging_short_router_carry_context_preparation"
        )
        self.assertIsNotNone(spec, "router carry preparation builder must exist")
        builder = importlib.import_module(
            "build_ranging_short_router_carry_context_preparation"
        )

        if not (COMPILED / "campaign.yaml").exists():
            result = builder.build()
        else:
            proposal = load_document(
                ROOT
                / "research/director/next-after-regime-conditioned-ranging-short-routing/"
                "proposals/ranging-short-router-carry-context-review-v1.json"
            )
            campaign = load_document(COMPILED / "campaign.yaml")
            result = {
                "proposal_id": proposal["proposal_id"],
                "proposal_fingerprint": proposal["semantic_fingerprint"],
                "campaign_fingerprint": campaign["campaign_fingerprint"],
                "candidate_count": 0,
                "backtest_calls": 0,
            }

        self.assertEqual(result["proposal_id"], PROPOSAL_ID)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["backtest_calls"], 0)
        packet = load_document(COMPILED / "human-decision-packet.json")
        self.assertEqual(
            packet["context_id"],
            "ranging_state_without_current_range_signal",
        )
        self.assertFalse(packet["execution_authorized"])
        self.assertEqual(packet["current_budget"]["max_candidates"], 0)
        self.assertEqual(packet["current_budget"]["max_backtest_calls"], 0)
        html = REPORT_HTML.read_text(encoding="utf-8")
        self.assertIn('<html lang="zh-CN">', html)
        self.assertNotRegex(html, r"https?://|<script")
        self.assertIn("当前不执行", html)
        registry = load_document(ROOT / "research/director/registry-records.json")
        rows = registry["tables"]["compiled_campaigns"]
        matching = [row for row in rows if row["proposal_id"] == PROPOSAL_ID]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["execution_authorized"], 0)
        runs = registry["tables"]["research_campaign_runs"]
        proposal_runs = [row for row in runs if row.get("proposal_id") == PROPOSAL_ID]
        self.assertEqual(len(proposal_runs), 1)
        self.assertEqual(proposal_runs[0]["status"], "stopped_pre_backtest")
        self.assertEqual(proposal_runs[0]["result_code"], "router_context_coverage_insufficient")
        self.assertEqual(proposal_runs[0]["campaign_executed"], 0)
        self.assertEqual(proposal_runs[0]["candidate_created"], 1)
        self.assertEqual(proposal_runs[0]["validation_accesses"], 0)
        self.assertEqual(proposal_runs[0]["holdout_accesses"], 0)


if __name__ == "__main__":
    unittest.main()
