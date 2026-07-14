import copy
import sys
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document  # noqa: E402


SCHEMAS = {
    "research-trigger.schema.json": "research-trigger-v1",
    "research-idea.schema.json": "research-idea-v1",
    "research-critique.schema.json": "research-critique-v1",
    "research-shortlist.schema.json": "research-shortlist-v1",
    "research-direction-approval.schema.json": "research-direction-approval-v1",
    "research-direction-handoff.schema.json": "research-direction-handoff-v1",
}

EXPECTED_REQUIRED = {
    "research-trigger.schema.json": {
        "schema_version",
        "trigger_id",
        "event_type",
        "event_ref",
        "research_state_fingerprint",
        "constitution_fingerprint",
        "source_policy_version",
        "created_at",
        "trigger_fingerprint",
    },
    "research-idea.schema.json": {
        "schema_version",
        "idea_id",
        "idea_version",
        "strategy_family",
        "title",
        "plain_language_summary_zh",
        "falsifiable_hypothesis",
        "proposed_market_mechanism",
        "supporting_evidence",
        "contradictory_evidence",
        "source_refs",
        "novelty_vs_existing_research",
        "required_datasets",
        "data_readiness",
        "fixed_scope_confirmation",
        "minimal_test_method",
        "comparison_baseline",
        "expected_information_gain",
        "estimated_cost",
        "risk_class",
        "contamination_risk",
        "falsification_conditions",
        "stop_conditions",
        "known_limitations",
        "research_state_fingerprint",
        "semantic_fingerprint",
    },
    "research-critique.schema.json": {
        "schema_version",
        "critique_id",
        "idea_id",
        "idea_semantic_fingerprint",
        "verdict",
        "source_verification",
        "duplicate_research_check",
        "falsifiability_assessment",
        "data_readiness_assessment",
        "leakage_and_overfit_risks",
        "transaction_cost_challenge",
        "strongest_counterevidence",
        "alternative_explanations",
        "fatal_objections",
        "score_adjustments",
        "ranking_inputs",
        "critic_fingerprint",
    },
    "research-shortlist.schema.json": {
        "schema_version",
        "discovery_run_id",
        "eligible_idea_count",
        "ranking_policy_version",
        "ranked_ideas",
        "recommended_idea_id",
        "recommendation",
        "recommendation_reason_zh",
        "research_state_fingerprint",
        "shortlist_fingerprint",
    },
    "research-direction-approval.schema.json": {
        "schema_version",
        "discovery_run_id",
        "decision",
        "selected_idea_id",
        "selected_idea_fingerprint",
        "selected_critique_fingerprint",
        "shortlist_fingerprint",
        "research_state_fingerprint",
        "constitution_fingerprint",
        "reviewer_type",
        "decision_reason_zh",
        "decided_at",
        "approval_fingerprint",
    },
    "research-direction-handoff.schema.json": {
        "schema_version",
        "discovery_run_id",
        "idea_ref",
        "critique_ref",
        "approval_ref",
        "idea_fingerprint",
        "critique_fingerprint",
        "approval_fingerprint",
        "shortlist_fingerprint",
        "research_state_fingerprint",
        "constitution_fingerprint",
        "research_question",
        "execution_authorized",
        "handoff_fingerprint",
    },
}

RANKING_KEYS = {
    "expected_information_gain",
    "falsifiability_and_mechanism_clarity",
    "feasibility_with_existing_data",
    "novelty_and_non_duplication",
    "robustness_relevance",
}

FINGERPRINT_PATTERN = "^[a-f0-9]{64}$"


class ResearchDiscoveryContractTests(unittest.TestCase):
    def test_schemas_are_valid_draft_2020_12_and_pin_schema_version(self):
        root = ROOT / "research/discovery/schemas"
        for filename, version in SCHEMAS.items():
            schema = load_document(root / filename)
            jsonschema.Draft202012Validator.check_schema(schema)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["properties"]["schema_version"]["const"], version)
            self.assertEqual(set(schema["required"]), EXPECTED_REQUIRED[filename])
            self.assertEqual(set(schema["properties"]), EXPECTED_REQUIRED[filename])
            self.assertFalse(schema["additionalProperties"])

            for property_schema in schema["properties"].values():
                if property_schema.get("type") == "array":
                    self.assertIn("items", property_schema)

            pending = [schema]
            while pending:
                current = pending.pop()
                if not isinstance(current, dict):
                    continue
                if current.get("type") == "object":
                    self.assertFalse(current["additionalProperties"])
                    for field in current.get("required", []):
                        field_schema = current["properties"][field]
                        field_type = field_schema.get("type")
                        if field_type == "string" or (
                            isinstance(field_type, list) and "string" in field_type
                        ):
                            self.assertEqual(
                                field_schema.get("minLength"),
                                1,
                                f"{filename}:{field} must reject empty strings",
                            )
                pending.extend(value for value in current.values() if isinstance(value, dict))
                for value in current.values():
                    if isinstance(value, list):
                        pending.extend(item for item in value if isinstance(item, dict))

        trigger = load_document(root / "research-trigger.schema.json")
        self.assertEqual(
            trigger["properties"]["event_type"]["enum"],
            ["campaign_completed", "branch_closed", "director_no_research", "manual_request"],
        )
        self.assertEqual(
            trigger["properties"]["source_policy_version"]["const"],
            "research-source-policy-v1",
        )
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(
                trigger["properties"]["trigger_fingerprint"]
            ).validate("not-a-fingerprint")

        idea = load_document(root / "research-idea.schema.json")
        fixed_scope = idea["properties"]["fixed_scope_confirmation"]
        expected_scope = {
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
        }
        self.assertEqual(set(fixed_scope["required"]), set(expected_scope))
        self.assertEqual(set(fixed_scope["properties"]), set(expected_scope))
        self.assertFalse(fixed_scope["additionalProperties"])
        jsonschema.Draft202012Validator(fixed_scope).validate(expected_scope)
        invalid_scope = copy.deepcopy(expected_scope)
        invalid_scope["validation_access"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(fixed_scope).validate(invalid_scope)

        estimated_cost = idea["properties"]["estimated_cost"]
        self.assertEqual(
            set(estimated_cost["required"]),
            {"experiments", "wall_clock_minutes", "compute_class"},
        )
        self.assertFalse(estimated_cost["additionalProperties"])
        self.assertEqual(estimated_cost["properties"]["compute_class"]["enum"], ["low", "medium", "high"])

        critique = load_document(root / "research-critique.schema.json")
        ranking_inputs = critique["properties"]["ranking_inputs"]
        self.assertEqual(set(ranking_inputs["required"]), RANKING_KEYS)
        self.assertEqual(set(ranking_inputs["properties"]), RANKING_KEYS)
        self.assertFalse(ranking_inputs["additionalProperties"])
        boundary_values = {key: 0 for key in RANKING_KEYS}
        boundary_values["expected_information_gain"] = 1
        jsonschema.Draft202012Validator(ranking_inputs).validate(boundary_values)
        for invalid_value in (-0.01, 1.01):
            invalid = copy.deepcopy(boundary_values)
            invalid["expected_information_gain"] = invalid_value
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.Draft202012Validator(ranking_inputs).validate(invalid)

        shortlist = load_document(root / "research-shortlist.schema.json")
        self.assertEqual(shortlist["properties"]["ranking_policy_version"]["const"], "research-ranking-policy-v1")
        self.assertEqual(shortlist["properties"]["ranked_ideas"]["maxItems"], 3)
        self.assertIn("null", shortlist["properties"]["recommended_idea_id"]["type"])

        approval = load_document(root / "research-direction-approval.schema.json")
        for field in (
            "selected_idea_id",
            "selected_idea_fingerprint",
            "selected_critique_fingerprint",
        ):
            self.assertIn("null", approval["properties"][field]["type"])
        for field in ("selected_idea_fingerprint", "selected_critique_fingerprint"):
            self.assertEqual(approval["properties"][field]["pattern"], FINGERPRINT_PATTERN)

        handoff = load_document(root / "research-direction-handoff.schema.json")
        execution_authorized = handoff["properties"]["execution_authorized"]
        self.assertEqual(execution_authorized, {"const": False})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(execution_authorized).validate(True)

    def test_source_and_ranking_policy_are_frozen(self):
        source = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        ranking = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        self.assertEqual(source["schema_version"], "research-source-policy-v1")
        self.assertEqual(
            source,
            {
                "schema_version": "research-source-policy-v1",
                "classes": {
                    "A": ["repository_frozen_data", "completed_research_artifact", "research_registry", "branch_closure", "approved_governance", "official_exchange_documentation"],
                    "B": ["peer_reviewed_paper", "reputable_preprint", "textbook", "institutional_research_report"],
                    "C": ["public_strategy_repository", "blog", "forum", "social_media", "video", "ranking", "commercial_claim"],
                },
                "pass_requirement": "at_least_one_A_or_B",
                "class_c_only_result": "reject",
                "external_required_fields": ["canonical_url", "source_class", "publisher_type", "retrieved_at", "claim", "content_fingerprint", "staleness_assessment", "licensing_constraints"],
                "forbidden_inputs": ["validation_result", "holdout", "private_api", "secret", "live_account", "unapproved_dataset"],
                "store_full_copyrighted_source": False,
            },
        )
        self.assertEqual(ranking["schema_version"], "research-ranking-policy-v1")
        self.assertEqual(sum(ranking["weights"].values()), 1.0)
        self.assertEqual(ranking["shortlist_threshold"], 0.55)
        self.assertEqual(ranking["max_shortlist"], 3)
        self.assertEqual(set(ranking["weights"]), RANKING_KEYS)
        self.assertEqual(
            ranking["penalties"],
            {
                "risk": {"low": 0.00, "medium": 0.05, "high": 0.15, "forbidden": "reject"},
                "cost": {"low": 0.00, "medium": 0.03, "high": 0.08},
                "contamination": {"none": 0.00, "low": 0.02, "medium": 0.08, "high": "reject"},
                "sources": {"includes_A": 0.00, "B_without_A": 0.02, "C_only": "reject"},
            },
        )
        self.assertEqual(ranking["initial_idea_min"], 6)
        self.assertEqual(ranking["initial_idea_max"], 10)
        self.assertEqual(ranking["max_ideas_per_family"], 2)
        self.assertEqual(ranking["max_revisions_per_cycle"], 1)
        self.assertEqual(ranking["tie_breakers"], ["lower_risk", "lower_cost", "semantic_fingerprint"])
        self.assertFalse(ranking["return_metrics_are_ranking_inputs"])


if __name__ == "__main__":
    unittest.main()
