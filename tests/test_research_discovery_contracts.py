import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document  # noqa: E402
from research_discovery_common import (  # noqa: E402
    TRANSITIONS,
    DiscoveryError,
    artifact_fingerprint,
    assert_fixed_scope,
    rank_eligible,
    score_idea,
    validate_artifact,
    validate_sources,
    validate_transition,
    write_immutable_json,
)


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

EXPECTED_OPTIONAL = {
    "research-idea.schema.json": {"knowledge_use"},
    "research-critique.schema.json": {"knowledge_verification"},
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


def ranking_pair(
    policy,
    idea_id="trend-v1",
    input_value=0.8,
    risk_class="low",
    cost_class="low",
    contamination_risk="none",
    source_class="A",
    semantic_fingerprint="1" * 64,
    verdict="pass",
):
    idea = {
        "idea_id": idea_id,
        "strategy_family": "trend_following",
        "risk_class": risk_class,
        "estimated_cost": {"compute_class": cost_class},
        "contamination_risk": contamination_risk,
        "semantic_fingerprint": semantic_fingerprint,
    }
    critique = {
        "verdict": verdict,
        "critic_fingerprint": "2" * 64,
        "source_verification": {"highest_class": source_class},
        "ranking_inputs": {key: input_value for key in policy["weights"]},
    }
    return idea, critique


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
    def test_load_document_reads_json_and_json_compatible_simple_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "document.json"
            yaml_path = root / "document.yaml"
            json_path.write_text(
                json.dumps({"name": "json", "enabled": True, "values": [1, 2]}),
                encoding="utf-8",
            )
            yaml_path.write_text(
                'name: "yaml"\nenabled: true\nvalues: [1, 2]\nweights: {"a": 1}\n',
                encoding="utf-8",
            )
            self.assertEqual(
                load_document(json_path),
                {"name": "json", "enabled": True, "values": [1, 2]},
            )
            self.assertEqual(
                load_document(yaml_path),
                {"name": "yaml", "enabled": True, "values": [1, 2], "weights": {"a": 1}},
            )

    def test_load_document_rejects_unsupported_or_malformed_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_documents = {
                "non_mapping.json": "[1, 2]",
                "malformed.json": '{"broken":',
                "malformed.yaml": "not yaml",
            }
            for filename, content in invalid_documents.items():
                with self.subTest(filename=filename):
                    path = root / filename
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_document(path)

    def test_semantic_fingerprint_ignores_identity_and_display_fields_only(self):
        idea = valid_artifacts()["research-idea.schema.json"]
        idea["created_at"] = "2026-07-14T00:00:00Z"
        idea["decided_at"] = "2026-07-14T00:00:00Z"
        baseline = artifact_fingerprint(idea, "semantic_fingerprint")
        self.assertEqual(
            baseline,
            artifact_fingerprint(dict(reversed(list(idea.items()))), "semantic_fingerprint"),
        )
        for field, replacement in (
            ("semantic_fingerprint", "b" * 64),
            ("title", "A display-only title change"),
            ("created_at", "2026-07-15T00:00:00Z"),
            ("decided_at", "2026-07-15T00:00:00Z"),
        ):
            with self.subTest(stable_field=field):
                changed = copy.deepcopy(idea)
                changed[field] = replacement
                self.assertEqual(
                    baseline,
                    artifact_fingerprint(changed, "semantic_fingerprint"),
                )

        semantic_mutations = {
            "falsifiable_hypothesis": "A different falsifiable hypothesis.",
            "proposed_market_mechanism": "A different proposed mechanism.",
            "fixed_scope_confirmation": {**idea["fixed_scope_confirmation"], "primary_timeframe": "4h"},
            "source_refs": [{**idea["source_refs"][0], "claim": "A materially different source claim."}],
            "estimated_cost": {**idea["estimated_cost"], "experiments": 2},
            "stop_conditions": ["A materially different stop condition"],
        }
        for field, replacement in semantic_mutations.items():
            with self.subTest(semantic_field=field):
                changed = copy.deepcopy(idea)
                changed[field] = replacement
                self.assertNotEqual(
                    baseline,
                    artifact_fingerprint(changed, "semantic_fingerprint"),
                )

    def test_each_artifact_fingerprint_has_a_fixed_exclusion_policy(self):
        fingerprint_fields = (
            "trigger_fingerprint",
            "semantic_fingerprint",
            "critic_fingerprint",
            "shortlist_fingerprint",
            "approval_fingerprint",
            "handoff_fingerprint",
        )
        for fingerprint_field in fingerprint_fields:
            with self.subTest(fingerprint_field=fingerprint_field):
                payload = {
                    "schema_version": "v1",
                    "title": "display title",
                    "semantic_value": "mechanism-a",
                    "created_at": "2026-07-14T00:00:00Z",
                    "decided_at": "2026-07-14T00:00:00Z",
                    fingerprint_field: "a" * 64,
                }
                baseline = artifact_fingerprint(payload, fingerprint_field)
                for field, replacement in (
                    (fingerprint_field, "b" * 64),
                    ("created_at", "2026-07-15T00:00:00Z"),
                    ("decided_at", "2026-07-15T00:00:00Z"),
                ):
                    changed = copy.deepcopy(payload)
                    changed[field] = replacement
                    self.assertEqual(baseline, artifact_fingerprint(changed, fingerprint_field))
                semantic_change = copy.deepcopy(payload)
                semantic_change["semantic_value"] = "mechanism-b"
                self.assertNotEqual(
                    baseline,
                    artifact_fingerprint(semantic_change, fingerprint_field),
                )
                title_change = copy.deepcopy(payload)
                title_change["title"] = "another display title"
                if fingerprint_field == "semantic_fingerprint":
                    self.assertEqual(baseline, artifact_fingerprint(title_change, fingerprint_field))
                else:
                    self.assertNotEqual(baseline, artifact_fingerprint(title_change, fingerprint_field))
        with self.assertRaisesRegex(DiscoveryError, "fingerprint_field_invalid"):
            artifact_fingerprint({"value": 1}, "unknown_fingerprint")

    def test_validate_artifact_accepts_all_six_allowlisted_contracts(self):
        for schema_filename, payload in valid_artifacts().items():
            with self.subTest(schema_filename=schema_filename):
                validate_artifact(ROOT, schema_filename, payload)

    def test_validate_artifact_rejects_non_allowlisted_schema_names(self):
        for schema_filename in (
            "../policy/ranking-policy.yaml",
            "ranking-policy.yaml",
            "unknown.schema.json",
            "research-trigger.schema.json/../unknown",
        ):
            with self.subTest(schema_filename=schema_filename):
                with self.assertRaisesRegex(DiscoveryError, "schema_not_allowed"):
                    validate_artifact(ROOT, schema_filename, {})

    def test_validate_artifact_wraps_instance_failure_with_json_path(self):
        invalid = valid_artifacts()["research-idea.schema.json"]
        invalid["fixed_scope_confirmation"]["validation_access"] = True
        with self.assertRaises(DiscoveryError) as caught:
            validate_artifact(ROOT, "research-idea.schema.json", invalid)
        self.assertEqual(caught.exception.reason_code, "artifact_validation_failed")
        self.assertIn("$.fixed_scope_confirmation.validation_access", str(caught.exception))
        self.assertIn("False was expected", str(caught.exception))

    def test_validate_artifact_wraps_schema_read_parse_shape_and_version_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            schema_root = repo / "research/discovery/schemas"
            schema_root.mkdir(parents=True)
            schema_path = schema_root / "research-trigger.schema.json"

            with self.assertRaisesRegex(DiscoveryError, "schema_load_failed"):
                validate_artifact(repo, "research-trigger.schema.json", {})

            schema_path.write_text('{"broken":', encoding="utf-8")
            with self.assertRaisesRegex(DiscoveryError, "schema_load_failed"):
                validate_artifact(repo, "research-trigger.schema.json", {})

            invalid_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "not-a-valid-json-schema-type",
                "properties": {"schema_version": {"const": "research-trigger-v1"}},
            }
            schema_path.write_text(json.dumps(invalid_schema), encoding="utf-8")
            with self.assertRaisesRegex(DiscoveryError, "schema_invalid"):
                validate_artifact(repo, "research-trigger.schema.json", {})

            wrong_version = load_document(
                ROOT / "research/discovery/schemas/research-trigger.schema.json"
            )
            wrong_version["properties"]["schema_version"]["const"] = "wrong-version"
            schema_path.write_text(json.dumps(wrong_version), encoding="utf-8")
            with self.assertRaisesRegex(DiscoveryError, "schema_version_mismatch"):
                validate_artifact(repo, "research-trigger.schema.json", {})

            wrong_version["properties"]["schema_version"] = True
            schema_path.write_text(json.dumps(wrong_version), encoding="utf-8")
            with self.assertRaisesRegex(DiscoveryError, "schema_version_mismatch"):
                validate_artifact(repo, "research-trigger.schema.json", {})

    def test_fixed_scope_requires_exact_keys_and_every_frozen_value(self):
        assert_fixed_scope(copy.deepcopy(FIXED_SCOPE))
        extra = {**FIXED_SCOPE, "extra": True}
        with self.assertRaisesRegex(DiscoveryError, "fixed_scope_violation"):
            assert_fixed_scope(extra)
        for field in FIXED_SCOPE:
            with self.subTest(field=field, case="missing"):
                missing = copy.deepcopy(FIXED_SCOPE)
                del missing[field]
                with self.assertRaisesRegex(DiscoveryError, "fixed_scope_violation"):
                    assert_fixed_scope(missing)
            with self.subTest(field=field, case="wrong"):
                wrong = copy.deepcopy(FIXED_SCOPE)
                wrong[field] = WRONG_FIXED_SCOPE_VALUES[field]
                reason = "validation_forbidden" if field == "validation_access" else "fixed_scope_violation"
                with self.assertRaisesRegex(DiscoveryError, reason):
                    assert_fixed_scope(wrong)
        for field in (
            "development_only",
            "risk_parameters_unchanged",
            "new_dataset",
            "validation_access",
            "holdout_access",
        ):
            with self.subTest(field=field, case="integer_boolean_impostor"):
                wrong_type = copy.deepcopy(FIXED_SCOPE)
                wrong_type[field] = int(FIXED_SCOPE[field])
                reason = "validation_forbidden" if field == "validation_access" else "fixed_scope_violation"
                with self.assertRaisesRegex(DiscoveryError, reason):
                    assert_fixed_scope(wrong_type)

    def test_source_gate_accepts_valid_a_b_and_mixed_evidence(self):
        class_a = {
            "source_class": "A",
            "path": "research/director/current-research-state.json",
            "claim": "Repository state is frozen evidence.",
        }
        class_b = external_source("B")
        class_c = external_source("C")
        self.assertEqual(validate_sources([class_a], ROOT), "includes_A")
        self.assertEqual(validate_sources([class_b], ROOT), "B_without_A")
        self.assertEqual(validate_sources([class_a, class_b], ROOT), "includes_A")
        self.assertEqual(validate_sources([class_b, class_c], ROOT), "B_without_A")

    def test_source_gate_rejects_invalid_class_claim_and_class_a_paths(self):
        class_a = {
            "source_class": "A",
            "path": "research/director/current-research-state.json",
            "claim": "Repository state is frozen evidence.",
        }
        with self.assertRaisesRegex(DiscoveryError, "source_class_invalid"):
            validate_sources([class_a, external_source("D")], ROOT)
        with self.assertRaisesRegex(DiscoveryError, "source_class_invalid"):
            validate_sources([class_a, "not-a-source-mapping"], ROOT)
        with self.assertRaisesRegex(DiscoveryError, "source_class_invalid"):
            validate_sources([class_a, {"source_class": ["A"], "claim": "invalid"}], ROOT)

        for source in (
            {"source_class": "A", "path": class_a["path"]},
            {**external_source("B"), "claim": ""},
            {**external_source("C"), "claim": "   "},
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(DiscoveryError, "source_claim_missing"):
                    validate_sources([source], ROOT)

        existing = ROOT / "research/director/current-research-state.json"
        invalid_paths = (
            None,
            "",
            str(existing),
            "../freqtrade-strategies-clean/research/director/current-research-state.json",
            "research/director",
            "research/director/does-not-exist.json",
        )
        for invalid_path in invalid_paths:
            with self.subTest(invalid_path=invalid_path):
                source = {
                    **external_source("A"),
                    "path": invalid_path,
                    "claim": "External metadata cannot substitute for a Class A path.",
                }
                with self.assertRaisesRegex(DiscoveryError, "source_missing"):
                    validate_sources([source], ROOT)

    def test_source_gate_requires_nonempty_external_metadata_and_rejects_c_only(self):
        metadata_fields = [
            field
            for field in EXTERNAL_REQUIRED_FIELDS
            if field not in {"source_class", "claim"}
        ]
        for source_class in ("B", "C"):
            for field in metadata_fields:
                for replacement in (None, "", "   "):
                    with self.subTest(
                        source_class=source_class,
                        field=field,
                        replacement=replacement,
                    ):
                        source = external_source(source_class)
                        if replacement is None:
                            del source[field]
                        else:
                            source[field] = replacement
                        with self.assertRaisesRegex(
                            DiscoveryError,
                            "external_source_metadata_incomplete",
                        ):
                            validate_sources([source], ROOT)
        with self.assertRaisesRegex(DiscoveryError, "class_c_only"):
            validate_sources([external_source("C")], ROOT)

    def test_write_immutable_json_is_idempotent_and_preserves_conflicting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/artifact.json"
            payload = {"schema_version": "v1", "nested": {"value": 1}}
            write_immutable_json(path, payload)
            self.assertEqual(load_document(path), payload)
            first_bytes = path.read_bytes()
            write_immutable_json(path, {"nested": {"value": 1}, "schema_version": "v1"})
            self.assertEqual(path.read_bytes(), first_bytes)
            with self.assertRaisesRegex(DiscoveryError, "immutable_artifact_conflict"):
                write_immutable_json(path, {"schema_version": "v1", "nested": {"value": 2}})
            self.assertEqual(path.read_bytes(), first_bytes)

    def test_transition_matrix_is_exact_and_rejects_unknown_or_skipped_states(self):
        expected = {
            "discovered": {
                "critic_rejected",
                "criticized",
                "revision_exhausted",
                "out_of_v1_scope",
                "insufficient_source_evidence",
                "data_readiness_required",
            },
            "criticized": {"shortlisted", "critic_rejected"},
            "shortlisted": {
                "human_approved",
                "rejected",
                "deferred",
                "no_research_recommended",
                "fingerprint_invalidated",
            },
            "human_approved": {"handed_to_director", "fingerprint_invalidated"},
            "handed_to_director": {"converted", "director_rejected"},
        }
        self.assertEqual(TRANSITIONS, expected)
        for current, targets in expected.items():
            for target in targets:
                with self.subTest(current=current, target=target, allowed=True):
                    validate_transition(current, target)
        for current, target in (
            ("shortlisted", "handed_to_director"),
            ("discovered", "human_approved"),
            ("criticized", "converted"),
            ("unknown", "shortlisted"),
            ("shortlisted", "unknown"),
        ):
            with self.subTest(current=current, target=target, allowed=False):
                with self.assertRaisesRegex(DiscoveryError, "illegal_transition"):
                    validate_transition(current, target)

    def test_ranking_uses_frozen_raw_formula_and_each_numeric_penalty(self):
        policy = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        idea, critique = ranking_pair(policy)
        critique["ranking_inputs"] = {
            "expected_information_gain": 0.9,
            "falsifiability_and_mechanism_clarity": 0.8,
            "feasibility_with_existing_data": 0.7,
            "novelty_and_non_duplication": 0.6,
            "robustness_relevance": 0.5,
        }
        base = round(
            sum(
                policy["weights"][key] * critique["ranking_inputs"][key]
                for key in policy["weights"]
            ),
            6,
        )
        self.assertEqual(base, 0.735)
        self.assertEqual(score_idea(idea, critique, policy), base)

        penalty_cases = (
            ("risk_medium", {"risk_class": "medium"}, {}, 0.05),
            ("risk_high", {"risk_class": "high"}, {}, 0.15),
            ("cost_medium", {"estimated_cost": {"compute_class": "medium"}}, {}, 0.03),
            ("cost_high", {"estimated_cost": {"compute_class": "high"}}, {}, 0.08),
            ("contamination_low", {"contamination_risk": "low"}, {}, 0.02),
            ("contamination_medium", {"contamination_risk": "medium"}, {}, 0.08),
            ("source_b", {}, {"source_verification": {"highest_class": "B"}}, 0.02),
        )
        for name, idea_update, critique_update, penalty in penalty_cases:
            with self.subTest(name=name):
                penalized_idea = copy.deepcopy(idea)
                penalized_critique = copy.deepcopy(critique)
                penalized_idea.update(idea_update)
                penalized_critique.update(critique_update)
                self.assertEqual(
                    score_idea(penalized_idea, penalized_critique, policy),
                    round(base - penalty, 6),
                )

    def test_ranking_rejects_policy_blocks_and_honors_threshold_and_top_three(self):
        policy = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        reject_cases = (
            {"risk_class": "forbidden"},
            {"contamination_risk": "high"},
        )
        for idea_update in reject_cases:
            idea, critique = ranking_pair(policy)
            idea.update(idea_update)
            with self.subTest(idea_update=idea_update):
                with self.assertRaisesRegex(DiscoveryError, "ranking_policy_reject"):
                    score_idea(idea, critique, policy)
        idea, critique = ranking_pair(policy, source_class="C")
        with self.assertRaisesRegex(DiscoveryError, "ranking_policy_reject"):
            score_idea(idea, critique, policy)
        idea, critique = ranking_pair(policy, verdict="reject")
        with self.assertRaisesRegex(DiscoveryError, "critic_not_passed"):
            score_idea(idea, critique, policy)

        at_threshold = ranking_pair(
            policy,
            idea_id="at-threshold",
            input_value=0.55,
            semantic_fingerprint="a" * 64,
        )
        below_threshold = ranking_pair(
            policy,
            idea_id="below-threshold",
            input_value=0.549999,
            semantic_fingerprint="b" * 64,
        )
        ranked = rank_eligible([below_threshold, at_threshold], policy)
        self.assertEqual([entry["idea_id"] for entry in ranked], ["at-threshold"])
        self.assertEqual(rank_eligible([], policy), [])

        four_items = [
            ranking_pair(
                policy,
                idea_id=f"idea-{index}",
                input_value=0.8,
                semantic_fingerprint=f"{index + 1:064x}",
            )
            for index in range(4)
        ]
        top_three = rank_eligible(list(reversed(four_items)), policy)
        self.assertEqual(len(top_three), 3)
        self.assertEqual(
            [entry["idea_id"] for entry in top_three],
            ["idea-0", "idea-1", "idea-2"],
        )

    def test_ranking_tie_breaks_by_risk_then_cost_then_fingerprint(self):
        policy = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        risk_tie = [
            ranking_pair(
                policy,
                idea_id="high-risk",
                input_value=0.85,
                risk_class="high",
                semantic_fingerprint="0" * 64,
            ),
            ranking_pair(
                policy,
                idea_id="medium-risk",
                input_value=0.75,
                risk_class="medium",
                semantic_fingerprint="1" * 64,
            ),
            ranking_pair(
                policy,
                idea_id="low-risk",
                input_value=0.7,
                risk_class="low",
                semantic_fingerprint="f" * 64,
            ),
        ]
        self.assertEqual(
            [entry["idea_id"] for entry in rank_eligible(risk_tie, policy)],
            ["low-risk", "medium-risk", "high-risk"],
        )

        cost_tie = [
            ranking_pair(
                policy,
                idea_id="high-cost",
                input_value=0.78,
                cost_class="high",
                semantic_fingerprint="0" * 64,
            ),
            ranking_pair(
                policy,
                idea_id="medium-cost",
                input_value=0.73,
                cost_class="medium",
                semantic_fingerprint="1" * 64,
            ),
            ranking_pair(
                policy,
                idea_id="low-cost",
                input_value=0.7,
                cost_class="low",
                semantic_fingerprint="f" * 64,
            ),
        ]
        self.assertEqual(
            [entry["idea_id"] for entry in rank_eligible(cost_tie, policy)],
            ["low-cost", "medium-cost", "high-cost"],
        )

        fingerprint_tie = [
            ranking_pair(
                policy,
                idea_id="fingerprint-c",
                input_value=0.7,
                semantic_fingerprint="c" * 64,
            ),
            ranking_pair(
                policy,
                idea_id="fingerprint-a",
                input_value=0.7,
                semantic_fingerprint="a" * 64,
            ),
            ranking_pair(
                policy,
                idea_id="fingerprint-b",
                input_value=0.7,
                semantic_fingerprint="b" * 64,
            ),
        ]
        self.assertEqual(
            [entry["idea_id"] for entry in rank_eligible(fingerprint_tie, policy)],
            ["fingerprint-a", "fingerprint-b", "fingerprint-c"],
        )

    def test_ranking_does_not_mutate_inputs_or_use_return_profit_win_rate(self):
        policy = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        idea, critique = ranking_pair(policy, input_value=0.7)
        baseline_score = score_idea(idea, critique, policy)
        idea.update({"expected_return": 999, "profit": 999, "win_rate": 1})
        critique["ranking_inputs"].update(
            {"expected_return": 1, "profit": 1, "win_rate": 1}
        )
        self.assertEqual(score_idea(idea, critique, policy), baseline_score)
        self.assertTrue(
            {"expected_return", "profit", "win_rate"}.isdisjoint(policy["weights"])
        )
        items = [(idea, critique)]
        items_before = copy.deepcopy(items)
        policy_before = copy.deepcopy(policy)
        rank_eligible(items, policy)
        self.assertEqual(items, items_before)
        self.assertEqual(policy, policy_before)

    def test_fixed_scope_rejects_validation_and_new_dataset(self):
        fixed = {
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
        assert_fixed_scope(fixed)
        invalid = copy.deepcopy(fixed)
        invalid["validation_access"] = True
        with self.assertRaisesRegex(DiscoveryError, "validation_forbidden"):
            assert_fixed_scope(invalid)

    def test_source_gate_requires_class_a_or_b(self):
        validate_sources([{"source_class": "A", "path": "research/director/current-research-state.json", "claim": "state"}], ROOT)
        with self.assertRaisesRegex(DiscoveryError, "class_c_only"):
            validate_sources([{"source_class": "C", "canonical_url": "https://example.invalid/post", "publisher_type": "blog", "retrieved_at": "2026-07-14T00:00:00Z", "claim": "idea", "content_fingerprint": "a" * 64, "staleness_assessment": "unknown", "licensing_constraints": "summary_only"}], ROOT)

    def test_ranking_is_deterministic_and_excludes_rejected_items(self):
        policy = load_document(ROOT / "research/discovery/policy/ranking-policy.yaml")
        idea = {"idea_id": "trend-v1", "strategy_family": "trend_following", "risk_class": "low", "estimated_cost": {"compute_class": "low"}, "contamination_risk": "none", "semantic_fingerprint": "1" * 64}
        critique = {"verdict": "pass", "critic_fingerprint": "2" * 64, "source_verification": {"highest_class": "A"}, "ranking_inputs": {key: 0.8 for key in policy["weights"]}}
        self.assertEqual(score_idea(idea, critique, policy), 0.8)
        ranked = rank_eligible([(idea, critique), ({**idea, "idea_id": "rejected"}, {**critique, "verdict": "reject"})], policy)
        self.assertEqual([entry["idea_id"] for entry in ranked], ["trend-v1"])

    def test_state_machine_does_not_skip_human_approval(self):
        validate_transition("shortlisted", "human_approved")
        with self.assertRaisesRegex(DiscoveryError, "illegal_transition"):
            validate_transition("shortlisted", "handed_to_director")

    def test_schemas_are_valid_draft_2020_12_and_pin_schema_version(self):
        root = ROOT / "research/discovery/schemas"
        for filename, version in SCHEMAS.items():
            schema = load_document(root / filename)
            jsonschema.Draft202012Validator.check_schema(schema)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["properties"]["schema_version"]["const"], version)
            self.assertEqual(set(schema["required"]), EXPECTED_REQUIRED[filename])
            self.assertEqual(
                set(schema["properties"]),
                EXPECTED_REQUIRED[filename] | EXPECTED_OPTIONAL.get(filename, set()),
            )
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

        validator = jsonschema.Draft202012Validator(approval)
        for decision in ("rejected", "deferred"):
            unselected = copy.deepcopy(
                valid_artifacts()["research-direction-approval.schema.json"]
            )
            unselected["decision"] = decision
            unselected["selected_idea_id"] = None
            unselected["selected_idea_fingerprint"] = None
            unselected["selected_critique_fingerprint"] = None
            validator.validate(unselected)
            for field in (
                "selected_idea_id",
                "selected_idea_fingerprint",
                "selected_critique_fingerprint",
            ):
                with self.subTest(decision=decision, nonnull_field=field):
                    invalid = copy.deepcopy(unselected)
                    invalid[field] = (
                        "idea-1" if field == "selected_idea_id" else FINGERPRINT
                    )
                    with self.assertRaises(jsonschema.ValidationError):
                        validator.validate(invalid)

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
