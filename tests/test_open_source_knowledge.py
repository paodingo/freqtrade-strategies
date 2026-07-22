import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import open_source_knowledge as knowledge  # noqa: E402
import research_discovery_trigger as discovery_trigger  # noqa: E402
from research_director_common import (  # noqa: E402
    DIRECTOR_SCHEMA_VERSION,
    KNOWLEDGE_TABLE_CONTRACTS,
    LEARNING_TABLE_CONTRACTS,
    load_document,
    director_registry_export,
    open_director_registry,
    sha256_file,
)
from export_director_registry import export_registry, merge_knowledge_tables  # noqa: E402


class OpenSourceKnowledgeTests(unittest.TestCase):
    def test_broker_deterministically_prioritizes_targeted_negative_lesson(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        first = knowledge.broker_selection(
            ROOT, "manual_request", "confirmed-higher-low", "a" * 64, state
        )
        second = knowledge.broker_selection(
            ROOT, "manual_request", "confirmed-higher-low", "a" * 64, state
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first["selected_lessons"][0]["lesson_id"],
            "chan-confirmed-higher-low-direct-entry-v1",
        )
        self.assertLessEqual(len(first["selected_patterns"]), 4)
        self.assertLessEqual(len(first["selected_lessons"]), 4)
        self.assertFalse(first["governance"]["candidate_creation_authorized"])
        self.assertFalse(first["governance"]["backtest_authorized"])
        self.assertEqual(
            first["selection_fingerprint"],
            knowledge.semantic_fingerprint(first, "selection_fingerprint"),
        )

    def test_researcher_packet_automatically_contains_broker_selection(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        policy = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        trigger = discovery_trigger.create_trigger(
            "manual_request",
            "confirmed-higher-low",
            state,
            constitution,
            policy,
            created_at="2026-07-19T12:00:00+08:00",
        )
        expected = discovery_trigger._expected_result(trigger, ROOT)

        packet = discovery_trigger.render_researcher_packet(
            ROOT,
            Path(expected["run_path"]),
            trigger,
            Path(expected["researcher_inbox"]),
        )

        self.assertIn("Automatic Knowledge Broker", packet)
        self.assertIn("chan-confirmed-higher-low-direct-entry-v1", packet)
        self.assertIn("Class C patterns are inspiration only", packet)

    def test_broker_usage_lineage_is_idempotent_per_discovery_run(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        policy = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        trigger = discovery_trigger.create_trigger(
            "branch_closed",
            "ranging-short",
            state,
            constitution,
            policy,
            created_at="2026-07-19T12:00:00+08:00",
        )
        selection = knowledge.broker_selection(
            ROOT,
            "branch_closed",
            "ranging-short",
            trigger["trigger_fingerprint"],
            state,
        )
        expected_count = len(selection["selected_patterns"]) + len(selection["selected_lessons"])
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            connection = open_director_registry(registry)
            discovery_trigger._record_knowledge_broker_usage(
                ROOT, trigger, "discovery-run-test", connection
            )
            first_count = connection.execute(
                "SELECT COUNT(*) FROM open_source_knowledge_lineage"
            ).fetchone()[0]
            discovery_trigger._record_knowledge_broker_usage(
                ROOT, trigger, "discovery-run-test", connection
            )
            second_count = connection.execute(
                "SELECT COUNT(*) FROM open_source_knowledge_lineage"
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT relation,target_type,target_id FROM open_source_knowledge_lineage"
            ).fetchall()
            connection.close()

        self.assertEqual(first_count, expected_count)
        self.assertEqual(second_count, expected_count)
        self.assertEqual(len(rows), expected_count)
        self.assertTrue(
            all(tuple(row) == ("retrieved_for", "discovery_run", "discovery-run-test") for row in rows)
        )

    def test_knowledge_export_merge_preserves_authoritative_history(self):
        base_tables = {
            "director_runs": [{"run_id": "authoritative-history"}],
            **{table: [] for table in {**KNOWLEDGE_TABLE_CONTRACTS, **LEARNING_TABLE_CONTRACTS}},
        }
        base = {
            "integrity": "ok",
            "execution_results_recorded": False,
            "fabricated_execution_results_recorded": False,
            "tables": base_tables,
            "counts": {table: len(rows) for table, rows in base_tables.items()},
        }
        current_tables = {
            "director_runs": [],
            **{
                table: [{"knowledge_id": table}]
                for table in {**KNOWLEDGE_TABLE_CONTRACTS, **LEARNING_TABLE_CONTRACTS}
            },
        }
        current = {
            "integrity": "ok",
            "tables": current_tables,
        }

        merged = merge_knowledge_tables(base, current)

        self.assertEqual(merged["tables"]["director_runs"], base_tables["director_runs"])
        for table in {**KNOWLEDGE_TABLE_CONTRACTS, **LEARNING_TABLE_CONTRACTS}:
            self.assertEqual(merged["tables"][table], current_tables[table])
            self.assertEqual(merged["counts"][table], 1)

    def test_fixed_source_snapshots_are_class_c_and_store_no_source(self):
        sources = knowledge.source_snapshots()

        self.assertEqual(len(sources), 6)
        self.assertEqual(len({item["commit_sha"] for item in sources}), 6)
        for item in sources:
            self.assertEqual(len(item["commit_sha"]), 40)
            self.assertEqual(item["source_class"], "C")
            self.assertFalse(item["full_source_stored"])
            self.assertFalse(item["code_reuse_authorized"])
            self.assertNotEqual(item["license_spdx"], "")

    def test_pattern_catalog_is_bounded_and_cannot_authorize_proposal(self):
        cards = knowledge.pattern_cards(knowledge.source_snapshots())

        self.assertEqual(len(cards), 12)
        self.assertLessEqual(len(cards), 12)
        self.assertTrue(any(item["local_data_readiness"] == "ready" for item in cards))
        self.assertTrue(any(item["local_data_readiness"] == "out_of_v1_scope" for item in cards))
        for item in cards:
            self.assertEqual(item["proposal_eligibility"], "inspiration_only_requires_A_or_B")
            self.assertFalse(item["parameters_copied"])
            self.assertFalse(item["implementation_copied"])
            self.assertFalse(item["alpha_claim"])

    def test_internal_lessons_bind_real_evidence_and_block_duplicates(self):
        lessons = knowledge.lesson_cards(ROOT)
        by_id = {item["lesson_id"]: item for item in lessons}

        chan = by_id["chan-confirmed-higher-low-direct-entry-v1"]
        self.assertEqual(chan["outcome"], "rejected_degradation")
        self.assertEqual(chan["reuse_policy"], "block_semantic_duplicate")
        self.assertLess(chan["metrics"]["btc"]["return_delta_pp"], 0)
        self.assertLess(chan["metrics"]["eth"]["return_delta_pp"], 0)
        for item in lessons:
            for path in item["evidence_paths"]:
                self.assertTrue((ROOT / path).is_file())
            self.assertEqual(item["source_class"], "A")
            self.assertEqual(item["validation_accesses"], 0)
            self.assertEqual(item["holdout_accesses"], 0)

    def test_manifest_hashes_and_read_only_boundaries_are_exact(self):
        manifest = load_document(ROOT / knowledge.OUTPUT_ROOT / "manifest.json")

        self.assertEqual(manifest["counts"], {"sources": 6, "patterns": 12, "lessons": 9})
        self.assertEqual(manifest["backtests_run"], 0)
        self.assertFalse(manifest["candidate_created"])
        self.assertFalse(manifest["formal_strategy_modified"])
        for asset in manifest["assets"]:
            self.assertEqual(asset["sha256"], sha256_file(ROOT / asset["path"]))
        self.assertEqual(manifest["context_sha256"], sha256_file(ROOT / manifest["context_path"]))

    def test_registry_migration_is_idempotent_and_protected_counts_do_not_change(self):
        manifest = load_document(ROOT / knowledge.OUTPUT_ROOT / "manifest.json")
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            first = knowledge.register_knowledge(ROOT, registry, manifest)
            second = knowledge.register_knowledge(ROOT, registry, manifest)
            compact_export = director_registry_export(registry)
            full_export = export_registry(str(registry))["tables"]
            connection = open_director_registry(registry)
            versions = {row[0] for row in connection.execute("SELECT version FROM director_schema_migrations")}
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            connection.close()

        self.assertEqual(DIRECTOR_SCHEMA_VERSION, 13)
        self.assertIn(8, versions)
        self.assertTrue(set(KNOWLEDGE_TABLE_CONTRACTS).issubset(tables))
        self.assertTrue(set(KNOWLEDGE_TABLE_CONTRACTS).issubset(compact_export))
        self.assertTrue(set(KNOWLEDGE_TABLE_CONTRACTS).issubset(full_export))
        self.assertEqual(first["counts"], second["counts"])
        self.assertTrue(first["protected_counts_unchanged"])
        self.assertEqual(first["integrity"], "ok")

    def test_retrieval_returns_relevant_patterns_and_negative_lessons(self):
        cross_pair = knowledge.retrieve_context(ROOT, ["cross-pair"])
        chan = knowledge.retrieve_context(ROOT, ["confirmed-higher-low"])

        self.assertEqual([item["pattern_id"] for item in cross_pair["patterns"]], ["multi-symbol-timeframe-composition"])
        self.assertEqual([item["lesson_id"] for item in chan["lessons"]], ["chan-confirmed-higher-low-direct-entry-v1"])
        self.assertEqual(chan["proposal_eligibility"], "requires_A_or_B_and_human_governance")

    def test_current_state_exposes_only_bounded_context_to_discovery(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        policy = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        knowledge_state = state.get("open_source_knowledge")
        self.assertIsInstance(knowledge_state, dict)
        self.assertTrue(knowledge_state["available"])
        self.assertEqual(knowledge_state["evidence"], ["research/knowledge/open-source-v1/current-context.json"])

        allowed = discovery_trigger._allowed_source_paths(ROOT, state, policy)
        self.assertIn("research/knowledge/open-source-v1/current-context.json", allowed)
        self.assertFalse(any(path.startswith("research/knowledge/open-source-v1/sources/") for path in allowed))

    def test_formal_strategy_hashes_remain_frozen(self):
        manifest = load_document(ROOT / "research/candidates/chan-structure-reversal-v1/candidate-manifest.json")
        self.assertEqual(manifest["formal_strategy_sha256"], sha256_file(ROOT / manifest["formal_strategy_path"]))
        self.assertEqual(manifest["formal_base_sha256"], sha256_file(ROOT / manifest["formal_base_path"]))

    def test_guard_uses_exact_knowledge_paths_without_directory_wildcard(self):
        guard = (ROOT / "scripts/guard_harness_diff.js").read_text(encoding="utf-8")
        manifest = load_document(ROOT / knowledge.OUTPUT_ROOT / "manifest.json")
        exact_paths = [asset["path"] for asset in manifest["assets"]]
        exact_paths.extend(
            [
                "research/knowledge/open-source-v1/manifest.json",
                "research/knowledge/open-source-v1/current-context.json",
                "research/knowledge/schemas/knowledge-broker-selection.schema.json",
                "research/knowledge/schemas/research-lesson-feedback-draft.schema.json",
                "research/knowledge/schemas/knowledge-source-refresh-report.schema.json",
                "research/knowledge/schemas/knowledge-retrieval-evaluation.schema.json",
                "research/knowledge/schemas/research-learning-loop-health.schema.json",
                "research/knowledge/schemas/knowledge-review-packet.schema.json",
                "research/knowledge/schemas/knowledge-review-event.schema.json",
                "research/knowledge/schemas/knowledge-review-recommendations.schema.json",
                "research/knowledge/schemas/knowledge-review-batch-approval.schema.json",
                "research/knowledge/schemas/knowledge-review-batch-handoff.schema.json",
                "research/knowledge/schemas/knowledge-review-human-intent.schema.json",
                "research/knowledge/schemas/knowledge-review-post-approval-plan.schema.json",
                "research/knowledge/schemas/research-lesson-curation-draft-packet.schema.json",
                "research/knowledge/schemas/research-lesson-promotion-human-intent.schema.json",
                "research/knowledge/schemas/research-lesson-curation-candidate.schema.json",
                "research/knowledge/schemas/research-lesson-promotion-packet.schema.json",
                "research/knowledge/schemas/research-lesson-promotion-approval.schema.json",
                "research/knowledge/evaluation/retrieval-cases-v1.json",
                "research/knowledge/prompts/knowledge-review-advisor-v1.md",
                "research/knowledge/prompts/lesson-curation-draft-advisor-v1.md",
                "scripts/open_source_knowledge.py",
                "scripts/research_knowledge_maintenance.py",
                "scripts/research_knowledge_review.py",
                "scripts/research_knowledge_advisory.py",
                "scripts/research_knowledge_batcher.py",
                "scripts/research_knowledge_batch_apply.py",
                "scripts/research_knowledge_post_review.py",
                "scripts/research_knowledge_curation_draft.py",
                "scripts/research_knowledge_candidate_compiler.py",
                "scripts/research_knowledge_promotion_apply.py",
                "scripts/research_worker_queue.py",
                "scripts/research_lesson_feedback.py",
                "scripts/research_lesson_curation.py",
                "scripts/research_lesson_promotion.py",
                "tests/test_open_source_knowledge.py",
                "tests/test_research_knowledge_maintenance.py",
                "tests/test_research_knowledge_review.py",
                "tests/test_research_knowledge_advisory.py",
                "tests/test_research_knowledge_batcher.py",
                "tests/test_research_knowledge_batch_apply.py",
                "tests/test_research_learning_loop.py",
                "tests/test_research_lesson_curation.py",
                "tests/test_research_lesson_promotion.py",
                "reports/audits/open-source-learning-v1/source-refresh-report.json",
                "reports/audits/open-source-learning-v1/retrieval-evaluation.json",
                "reports/audits/open-source-learning-v1/learning-loop-health.json",
                "reports/audits/open-source-learning-v1/pending-review-packet.json",
                "reports/audits/open-source-learning-v1/review-recommendations.json",
                "reports/audits/open-source-learning-v1/review-recommendations.md",
                "reports/audits/open-source-learning-v1/lesson-curation-report.md",
                "reports/audits/open-source-learning-v1/lesson-promotion-report.md",
                "research/governance/approvals/open-source-learning-v1-review-batch-20260719.json",
                "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/packet.json",
                "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/recommendations.json",
                "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/batch-approval.json",
                "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/review-events.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-cross-pair-reproducibility-not-generalization-v1.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-exit-frequency-insufficient-causal-evidence-v1.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-ranging-short-temporal-retention-v1.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-regime-directionality-rotation-no-threshold-search-v1.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-semantic-equivalence-current-artifact-binding-v1.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-strategy-family-baseline-single-structure-hypothesis-v1.json",
                "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/promotion-review-packet.json",
                "research/governance/approvals/open-source-learning-v1-lesson-promotion-20260720.json",
                "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720/packet.json",
                "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720/approval.json",
                "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720/review-events.json",
            ]
        )
        for path in exact_paths:
            self.assertIn(f'{{ path: "{path}" }}', guard)
        self.assertNotIn('{ prefix: "research/knowledge/" }', guard)
        self.assertNotIn('{ prefix: "research/knowledge/open-source-v1/" }', guard)


if __name__ == "__main__":
    unittest.main()
