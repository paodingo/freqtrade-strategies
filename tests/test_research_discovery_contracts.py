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
FINGERPRINT = "a" * 64

EXTERNAL_REQUIRED_FIELDS = [
    "canonical_url",
    "source_class",
    "publisher_type",
    "retrieved_at",
    "claim",
    "content_fingerprint",
    "staleness_assessment",
    "licensing_constraints",
]

FIXED_SCOPE = {
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

WRONG_FIXED_SCOPE_VALUES = {
    "exchange": "other",
    "market": "spot",
    "margin_mode": "cross",
    "primary_timeframe": "5m",
    "informative_timeframes": ["1h"],
    "development_only": False,
    "risk_parameters_unchanged": False,
    "new_dataset": True,
    "validation_access": True,
    "holdout_access": True,
}

EXPECTED_WEIGHTS = {
    "expected_information_gain": 0.30,
    "falsifiability_and_mechanism_clarity": 0.20,
    "feasibility_with_existing_data": 0.20,
    "novelty_and_non_duplication": 0.15,
    "robustness_relevance": 0.15,
}

FINGERPRINT_PATHS = {
    "research-trigger.schema.json": [
        ("research_state_fingerprint",),
        ("constitution_fingerprint",),
        ("trigger_fingerprint",),
    ],
    "research-idea.schema.json": [
        ("source_refs", 0, "content_fingerprint"),
        ("research_state_fingerprint",),
        ("semantic_fingerprint",),
    ],
    "research-critique.schema.json": [
        ("idea_semantic_fingerprint",),
        ("critic_fingerprint",),
    ],
    "research-shortlist.schema.json": [
        ("ranked_ideas", 0, "idea_fingerprint"),
        ("ranked_ideas", 0, "critique_fingerprint"),
        ("research_state_fingerprint",),
        ("shortlist_fingerprint",),
    ],
    "research-direction-approval.schema.json": [
        ("selected_idea_fingerprint",),
        ("selected_critique_fingerprint",),
        ("shortlist_fingerprint",),
        ("research_state_fingerprint",),
        ("constitution_fingerprint",),
        ("approval_fingerprint",),
    ],
    "research-direction-handoff.schema.json": [
        ("idea_fingerprint",),
        ("critique_fingerprint",),
        ("approval_fingerprint",),
        ("shortlist_fingerprint",),
        ("research_state_fingerprint",),
        ("constitution_fingerprint",),
        ("handoff_fingerprint",),
    ],
}

NESTED_OBJECT_PATHS = {
    "research-idea.schema.json": [
        ("source_refs", 0),
        ("fixed_scope_confirmation",),
        ("estimated_cost",),
    ],
    "research-critique.schema.json": [
        ("source_verification",),
        ("ranking_inputs",),
    ],
    "research-shortlist.schema.json": [
        ("ranked_ideas", 0),
    ],
}

REQUIRED_STRING_PATHS = {
    "research-trigger.schema.json": [
        (field,)
        for field in (
            "schema_version",
            "trigger_id",
            "event_type",
            "event_ref",
            "research_state_fingerprint",
            "constitution_fingerprint",
            "source_policy_version",
            "created_at",
            "trigger_fingerprint",
        )
    ],
    "research-idea.schema.json": [
        (field,)
        for field in (
            "schema_version",
            "idea_id",
            "strategy_family",
            "title",
            "plain_language_summary_zh",
            "falsifiable_hypothesis",
            "proposed_market_mechanism",
            "novelty_vs_existing_research",
            "data_readiness",
            "minimal_test_method",
            "comparison_baseline",
            "risk_class",
            "contamination_risk",
            "research_state_fingerprint",
            "semantic_fingerprint",
        )
    ]
    + [("source_refs", 0, field) for field in EXTERNAL_REQUIRED_FIELDS]
    + [
        ("fixed_scope_confirmation", "exchange"),
        ("fixed_scope_confirmation", "market"),
        ("fixed_scope_confirmation", "margin_mode"),
        ("fixed_scope_confirmation", "primary_timeframe"),
        ("estimated_cost", "compute_class"),
    ],
    "research-critique.schema.json": [
        (field,)
        for field in (
            "schema_version",
            "critique_id",
            "idea_id",
            "idea_semantic_fingerprint",
            "verdict",
            "duplicate_research_check",
            "falsifiability_assessment",
            "data_readiness_assessment",
            "transaction_cost_challenge",
            "strongest_counterevidence",
            "critic_fingerprint",
        )
    ]
    + [("source_verification", "highest_class")],
    "research-shortlist.schema.json": [
        (field,)
        for field in (
            "schema_version",
            "discovery_run_id",
            "ranking_policy_version",
            "recommended_idea_id",
            "recommendation",
            "recommendation_reason_zh",
            "research_state_fingerprint",
            "shortlist_fingerprint",
        )
    ]
    + [
        ("ranked_ideas", 0, "idea_id"),
        ("ranked_ideas", 0, "idea_fingerprint"),
        ("ranked_ideas", 0, "critique_fingerprint"),
        ("ranked_ideas", 0, "strategy_family"),
        ("ranked_ideas", 0, "risk_class"),
        ("ranked_ideas", 0, "cost_class"),
    ],
    "research-direction-approval.schema.json": [
        (field,)
        for field in (
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
        )
    ],
    "research-direction-handoff.schema.json": [
        (field,)
        for field in (
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
            "handoff_fingerprint",
        )
    ],
}


def external_source(source_class="B"):
    return {
        "canonical_url": "https://example.invalid/research",
        "source_class": source_class,
        "publisher_type": "institutional_research_report",
        "retrieved_at": "2026-07-14T00:00:00Z",
        "claim": "The source supports a falsifiable market-mechanism claim.",
        "content_fingerprint": FINGERPRINT,
        "staleness_assessment": "current_for_discovery",
        "licensing_constraints": "summary_only",
    }


def valid_artifacts():
    ranking_inputs = {key: 0.5 for key in RANKING_KEYS}
    return {
        "research-trigger.schema.json": {
            "schema_version": "research-trigger-v1",
            "trigger_id": "trigger-1",
            "event_type": "manual_request",
            "event_ref": "request-1",
            "research_state_fingerprint": FINGERPRINT,
            "constitution_fingerprint": FINGERPRINT,
            "source_policy_version": "research-source-policy-v1",
            "created_at": "2026-07-14T00:00:00Z",
            "trigger_fingerprint": FINGERPRINT,
        },
        "research-idea.schema.json": {
            "schema_version": "research-idea-v1",
            "idea_id": "idea-1",
            "idea_version": 1,
            "strategy_family": "trend_following",
            "title": "Trend persistence",
            "plain_language_summary_zh": "研究趋势持续性。",
            "falsifiable_hypothesis": "Persistence exceeds the frozen baseline.",
            "proposed_market_mechanism": "Slow information diffusion.",
            "supporting_evidence": ["Repository evidence"],
            "contradictory_evidence": ["Transaction costs may dominate"],
            "source_refs": [external_source()],
            "novelty_vs_existing_research": "Distinct from registered work.",
            "required_datasets": ["approved-development-data"],
            "data_readiness": "ready",
            "fixed_scope_confirmation": copy.deepcopy(FIXED_SCOPE),
            "minimal_test_method": "One frozen comparison.",
            "comparison_baseline": "RegimeAwareV6",
            "expected_information_gain": 0.5,
            "estimated_cost": {
                "experiments": 1,
                "wall_clock_minutes": 30,
                "compute_class": "low",
            },
            "risk_class": "low",
            "contamination_risk": "none",
            "falsification_conditions": ["No improvement in mechanism clarity"],
            "stop_conditions": ["Any scope violation"],
            "known_limitations": ["Development-only conclusion"],
            "research_state_fingerprint": FINGERPRINT,
            "semantic_fingerprint": FINGERPRINT,
        },
        "research-critique.schema.json": {
            "schema_version": "research-critique-v1",
            "critique_id": "critique-1",
            "idea_id": "idea-1",
            "idea_semantic_fingerprint": FINGERPRINT,
            "verdict": "pass",
            "source_verification": {"highest_class": "B"},
            "duplicate_research_check": "No duplicate found.",
            "falsifiability_assessment": "Falsifiable.",
            "data_readiness_assessment": "Ready.",
            "leakage_and_overfit_risks": ["Temporal selection risk"],
            "transaction_cost_challenge": "Costs must be included.",
            "strongest_counterevidence": "Persistence may reverse.",
            "alternative_explanations": ["Regime mix"],
            "fatal_objections": [],
            "score_adjustments": ["No manual adjustment"],
            "ranking_inputs": ranking_inputs,
            "critic_fingerprint": FINGERPRINT,
        },
        "research-shortlist.schema.json": {
            "schema_version": "research-shortlist-v1",
            "discovery_run_id": "run-1",
            "eligible_idea_count": 1,
            "ranking_policy_version": "research-ranking-policy-v1",
            "ranked_ideas": [
                {
                    "idea_id": "idea-1",
                    "idea_fingerprint": FINGERPRINT,
                    "critique_fingerprint": FINGERPRINT,
                    "strategy_family": "trend_following",
                    "risk_class": "low",
                    "cost_class": "low",
                    "final_score": 0.6,
                }
            ],
            "recommended_idea_id": "idea-1",
            "recommendation": "research_recommended",
            "recommendation_reason_zh": "该方向值得正式准备。",
            "research_state_fingerprint": FINGERPRINT,
            "shortlist_fingerprint": FINGERPRINT,
        },
        "research-direction-approval.schema.json": {
            "schema_version": "research-direction-approval-v1",
            "discovery_run_id": "run-1",
            "decision": "approved_for_director_handoff",
            "selected_idea_id": "idea-1",
            "selected_idea_fingerprint": FINGERPRINT,
            "selected_critique_fingerprint": FINGERPRINT,
            "shortlist_fingerprint": FINGERPRINT,
            "research_state_fingerprint": FINGERPRINT,
            "constitution_fingerprint": FINGERPRINT,
            "reviewer_type": "human_user",
            "decision_reason_zh": "批准进入 Director 准备阶段。",
            "decided_at": "2026-07-14T00:00:00Z",
            "approval_fingerprint": FINGERPRINT,
        },
        "research-direction-handoff.schema.json": {
            "schema_version": "research-direction-handoff-v1",
            "discovery_run_id": "run-1",
            "idea_ref": "ideas/idea-1-v1.json",
            "critique_ref": "critiques/idea-1-v1.json",
            "approval_ref": "approval.json",
            "idea_fingerprint": FINGERPRINT,
            "critique_fingerprint": FINGERPRINT,
            "approval_fingerprint": FINGERPRINT,
            "shortlist_fingerprint": FINGERPRINT,
            "research_state_fingerprint": FINGERPRINT,
            "constitution_fingerprint": FINGERPRINT,
            "research_question": "Does the mechanism merit a frozen experiment?",
            "execution_authorized": False,
            "handoff_fingerprint": FINGERPRINT,
        },
    }


def value_at(payload, path):
    current = payload
    for part in path:
        current = current[part]
    return current


def set_value_at(payload, path, value):
    current = payload
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def schema_at(schema, path):
    current = schema
    for part in path:
        current = current["items"] if isinstance(part, int) else current["properties"][part]
    return current


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

    def test_external_sources_follow_the_frozen_policy_fields(self):
        schema = load_document(ROOT / "research/discovery/schemas/research-idea.schema.json")
        validator = jsonschema.Draft202012Validator(schema)

        class_a_idea = valid_artifacts()["research-idea.schema.json"]
        class_a_idea["source_refs"] = [
            {
                "source_class": "A",
                "path": "research/director/current-research-state.json",
                "claim": "The repository state is frozen evidence.",
            }
        ]
        validator.validate(class_a_idea)

        for source_class in ("B", "C"):
            complete = valid_artifacts()["research-idea.schema.json"]
            complete["source_refs"] = [external_source(source_class)]
            validator.validate(complete)
            for field in EXTERNAL_REQUIRED_FIELDS:
                with self.subTest(source_class=source_class, missing=field):
                    invalid = copy.deepcopy(complete)
                    del invalid["source_refs"][0][field]
                    with self.assertRaises(jsonschema.ValidationError):
                        validator.validate(invalid)

    def test_schemas_reject_root_and_nested_contract_relaxation(self):
        artifacts = valid_artifacts()
        root = ROOT / "research/discovery/schemas"
        for filename, payload in artifacts.items():
            validator = jsonschema.Draft202012Validator(load_document(root / filename))
            validator.validate(payload)
            with self.subTest(filename=filename, case="root_non_object"):
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate([])
            with self.subTest(filename=filename, case="root_extra_field"):
                invalid = copy.deepcopy(payload)
                invalid["unexpected"] = True
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(invalid)

            for path in NESTED_OBJECT_PATHS.get(filename, []):
                with self.subTest(filename=filename, path=path, case="nested_non_object"):
                    invalid = copy.deepcopy(payload)
                    set_value_at(invalid, path, "not-an-object")
                    with self.assertRaises(jsonschema.ValidationError):
                        validator.validate(invalid)
                with self.subTest(filename=filename, path=path, case="nested_extra_field"):
                    invalid = copy.deepcopy(payload)
                    nested = value_at(invalid, path)
                    nested["unexpected"] = True
                    with self.assertRaises(jsonschema.ValidationError):
                        validator.validate(invalid)

    def test_required_strings_reject_non_strings_and_empty_values(self):
        artifacts = valid_artifacts()
        root = ROOT / "research/discovery/schemas"
        for filename, paths in REQUIRED_STRING_PATHS.items():
            validator = jsonschema.Draft202012Validator(load_document(root / filename))
            for path in paths:
                for invalid_value in (123, ""):
                    with self.subTest(filename=filename, path=path, value=invalid_value):
                        invalid = copy.deepcopy(artifacts[filename])
                        set_value_at(invalid, path, invalid_value)
                        with self.assertRaises(jsonschema.ValidationError):
                            validator.validate(invalid)

    def test_all_fingerprint_paths_are_strict_lowercase_sha256(self):
        artifacts = valid_artifacts()
        root = ROOT / "research/discovery/schemas"
        invalid_fingerprints = ("A" * 64, "a" * 63, "a" * 65, "g" * 64)
        for filename, paths in FINGERPRINT_PATHS.items():
            schema = load_document(root / filename)
            validator = jsonschema.Draft202012Validator(schema)
            for path in paths:
                with self.subTest(filename=filename, path=path, case="pattern"):
                    self.assertEqual(schema_at(schema, path)["pattern"], FINGERPRINT_PATTERN)
                for invalid_value in invalid_fingerprints:
                    with self.subTest(filename=filename, path=path, value=invalid_value):
                        invalid = copy.deepcopy(artifacts[filename])
                        set_value_at(invalid, path, invalid_value)
                        with self.assertRaises(jsonschema.ValidationError):
                            validator.validate(invalid)

    def test_fixed_scope_fields_are_exact_and_reject_each_wrong_value(self):
        schema = load_document(ROOT / "research/discovery/schemas/research-idea.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        valid = valid_artifacts()["research-idea.schema.json"]
        validator.validate(valid)
        fixed_schema = schema["properties"]["fixed_scope_confirmation"]
        for field, expected_value in FIXED_SCOPE.items():
            with self.subTest(field=field, case="const"):
                self.assertEqual(fixed_schema["properties"][field].get("const"), expected_value)
            with self.subTest(field=field, case="wrong_value"):
                invalid = copy.deepcopy(valid)
                invalid["fixed_scope_confirmation"][field] = WRONG_FIXED_SCOPE_VALUES[field]
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(invalid)

    def test_all_ranking_inputs_enforce_zero_to_one_boundaries(self):
        schema = load_document(ROOT / "research/discovery/schemas/research-critique.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        valid = valid_artifacts()["research-critique.schema.json"]
        for field in RANKING_KEYS:
            for boundary in (0, 1):
                with self.subTest(field=field, boundary=boundary):
                    payload = copy.deepcopy(valid)
                    payload["ranking_inputs"][field] = boundary
                    validator.validate(payload)
            for invalid_value in (-0.01, 1.01):
                with self.subTest(field=field, invalid=invalid_value):
                    payload = copy.deepcopy(valid)
                    payload["ranking_inputs"][field] = invalid_value
                    with self.assertRaises(jsonschema.ValidationError):
                        validator.validate(payload)

    def test_source_and_ranking_policy_are_frozen(self):
        source = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        ranking = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        self.assertEqual(
            set(source),
            {
                "schema_version",
                "classes",
                "pass_requirement",
                "class_c_only_result",
                "external_required_fields",
                "forbidden_inputs",
                "store_full_copyrighted_source",
            },
        )
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
        self.assertEqual(source["external_required_fields"], EXTERNAL_REQUIRED_FIELDS)
        self.assertEqual(
            set(ranking),
            {
                "schema_version",
                "weights",
                "penalties",
                "shortlist_threshold",
                "max_shortlist",
                "initial_idea_min",
                "initial_idea_max",
                "max_ideas_per_family",
                "max_revisions_per_cycle",
                "tie_breakers",
                "return_metrics_are_ranking_inputs",
            },
        )
        self.assertEqual(ranking["schema_version"], "research-ranking-policy-v1")
        self.assertEqual(ranking["weights"], EXPECTED_WEIGHTS)
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
