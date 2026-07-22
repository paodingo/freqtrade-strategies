from __future__ import annotations

import copy
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_director_registry as registry_exporter  # noqa: E402
import open_source_knowledge as knowledge  # noqa: E402
import research_knowledge_batch_apply as batch_apply  # noqa: E402
import research_knowledge_batcher as batcher  # noqa: E402
import research_knowledge_post_review as post_review  # noqa: E402
import research_knowledge_curation_draft as curation_draft  # noqa: E402
import research_knowledge_candidate_compiler as candidate_compiler  # noqa: E402
import research_knowledge_promotion_apply as promotion_apply  # noqa: E402
import research_knowledge_maintenance as knowledge_maintenance  # noqa: E402
from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, write_json  # noqa: E402


class ResearchKnowledgeBatchApplyTests(unittest.TestCase):
    def _promotion_cli_fixture(self, directory: str) -> tuple[Path, str, dict, dict]:
        repo = Path(directory)
        for relative in (
            "research/knowledge/open-source-v1",
            "research/knowledge/schemas",
            "research/knowledge/evaluation",
        ):
            shutil.copytree(ROOT / relative, repo / relative)
        for relative in (
            "research/director/current-research-state.json",
            "research/director/current-research-state.md",
            "research/director/registry-records.json",
            "reports/audits/open-source-learning-v1/source-refresh-report.json",
            "reports/audits/open-source-learning-v1/retrieval-evaluation.json",
            "reports/audits/open-source-learning-v1/learning-loop-health.json",
        ):
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        evidence_path = Path("evidence/e2e-promotion-proof.json")
        write_json(repo / evidence_path, {"scope": "temporary-e2e-only"})
        card = {
            "schema_version": "research-lesson-card-v1",
            "lesson_id": "temporary-e2e-promotion-recertification-v1",
            "title_zh": "临时端到端晋升再认证",
            "outcome": "verified_engineering",
            "mechanism_keys": ["e2e", "promotion", "recertification"],
            "scope": {"environment": "temporary-test-repository"},
            "summary_zh": "验证正式知识晋升、Broker 生效、状态同步与事务回滚。",
            "metrics": {},
            "evidence_paths": [evidence_path.as_posix()],
            "source_class": "A",
            "reuse_policy": "require_recertification",
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        card["lesson_fingerprint"] = knowledge.semantic_fingerprint(card, "lesson_fingerprint")
        candidate = {
            "schema_version": "research-lesson-curation-candidate-v1",
            "candidate_id": "lesson-candidate-temporary-e2e-promotion-recertification-v1",
            "status": "pending_human_promotion_review",
            "source_feedback_ids": ["temporary-e2e-feedback-v1"],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "仅验证通用晋升事务，不表达交易结论。",
            "proposed_card": card,
            "automatic_promotion_authorized": False,
        }
        candidate["candidate_fingerprint"] = knowledge.semantic_fingerprint(
            candidate, "candidate_fingerprint"
        )
        batch_id = "knowledge-review-batch-e2e0000000000001"
        batch_root = Path("reports/audits/open-source-learning-v1/review-batches/aggregated") / batch_id
        candidate_root = batch_root / "lesson-candidates"
        candidate_path = candidate_root / f"{candidate['candidate_id']}.json"
        packet_path = batch_root / "promotion-review-packet.json"
        context = load_document(repo / "research/knowledge/open-source-v1/current-context.json")
        packet = {
            "schema_version": "research-lesson-promotion-packet-v1",
            "packet_id": "knowledge-lesson-promotion-review-temporary-e2e",
            "generated_at": "2026-07-21T06:00:00Z",
            "source_review_batch": batch_id,
            "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
            "approved_feedback_count": 1,
            "candidate_count": 1,
            "formal_lesson_count_before": len(context["lessons"]),
            "candidates": [{
                "candidate_id": candidate["candidate_id"],
                "proposed_lesson_id": card["lesson_id"],
                "path": candidate_path.as_posix(),
                "candidate_fingerprint": candidate["candidate_fingerprint"],
                "source_feedback_ids": candidate["source_feedback_ids"],
                "supersedes_lesson_ids": [],
            }],
            "coverage": {
                "approved_feedback_ids": candidate["source_feedback_ids"],
                "covered_feedback_ids": candidate["source_feedback_ids"],
                "uncovered_feedback_ids": [],
                "duplicate_feedback_merged": 0,
            },
            "human_approval_required": True,
            "automatic_promotion_authorized": False,
            "execution_authorized": False,
        }
        packet["packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "packet_fingerprint")
        handoff = {
            "batch_id": batch_id,
            "planned_curation_candidate_root": candidate_root.as_posix(),
            "planned_promotion_review_packet_path": packet_path.as_posix(),
            "planned_promotion_human_intent_path": (batch_root / "promotion-human-intent.json").as_posix(),
            "planned_promotion_approval_path": (batch_root / "promotion-approval.json").as_posix(),
            "planned_promotion_events_path": (batch_root / "promotion-events.json").as_posix(),
            "planned_published_manifest_path": (batch_root / "promotion-published-manifest.json").as_posix(),
        }
        write_json(repo / batch_root / "handoff.json", handoff)
        write_json(repo / candidate_path, candidate)
        write_json(repo / packet_path, packet)
        registry = repo / "research/registry/stage4a-director.db"
        connection = open_director_registry(registry)
        connection.close()
        return repo, batch_id, handoff, candidate

    def _run_promotion_cli(self, repo: Path, batch_id: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/research_knowledge_promotion_apply.py"),
                "--repo-root", str(repo),
                "--batch-id", batch_id,
                "--registry", "research/registry/stage4a-director.db",
                "--registry-export", "research/director/registry-records.json",
                "--human-statement", "批准临时端到端 Candidate，仅用于事务再认证测试",
                "--reviewer-id", "test-human",
                "--decided-at", "2026-07-21T06:30:00Z",
                "--approve-all",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def _policy(self) -> dict:
        policy = {
            "schema_version": "knowledge-review-batch-policy-v1",
            "policy_id": "development-knowledge-review-batch-policy-v1",
            "status": "active",
            "count_threshold": 1,
            "max_wait_hours": 168,
            "included_review_types": ["source_update", "lesson_feedback", "license_review"],
            "output_root": "reports/audits/open-source-learning-v1/review-batches/aggregated",
            "idle_behavior": "silent_no_write",
            "triggered_behavior": "immutable_human_review_handoff",
            "advisory_drafting_authorized": True,
            "automatic_decision_authorized": False,
            "automatic_application_authorized": False,
            "automatic_lesson_promotion_authorized": False,
            "execution_authorized": False,
        }
        policy["policy_fingerprint"] = knowledge.semantic_fingerprint(policy, "policy_fingerprint")
        return policy

    def _seed(self, registry: Path) -> None:
        payload = {
            "source_kind": "campaign",
            "evidence_artifacts": [{
                "path": "tests/test_research_knowledge_batch_apply.py",
                "sha256": "0" * 64,
            }],
        }
        connection = open_director_registry(registry)
        try:
            connection.execute(
                "INSERT INTO research_lesson_feedback_drafts VALUES(?,?,?,?,?,?,?,?)",
                (
                    "feedback-1", "run-1", "campaign-1", "proposal-1", "negative",
                    "pending_human_review", json.dumps(payload), "2026-07-20T00:00:00Z",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _assets(self, registry: Path) -> tuple[dict, dict, dict]:
        result = batcher.build_batch(
            ROOT,
            registry_exporter.export_registry(str(registry)),
            self._policy(),
            "2026-07-20T01:00:00Z",
        )
        packet = result["packet"]
        advisory = {
            "schema_version": "knowledge-review-recommendations-v1",
            "advisory_id": f"knowledge-review-advisory-{packet['packet_fingerprint'][:16]}",
            "generated_at": packet["generated_at"],
            "packet_fingerprint": packet["packet_fingerprint"],
            "recommendations": [{
                "review_key": "lesson_feedback:feedback-1",
                "review_type": "lesson_feedback",
                "target_id": "feedback-1",
                "recommended_decision": "approved",
                "confidence": "high",
                "disposition": "curate_standalone",
                "rationale": "the local evidence supports a scoped curation review",
                "references": ["tests/test_research_knowledge_batch_apply.py"],
                "constraints": ["manual curation only"],
            }],
            "summary": {"approved": 1, "rejected": 0, "total": 1},
            "human_decision_required": True,
            "automatic_application_authorized": False,
            "execution_authorized": False,
        }
        advisory["advisory_fingerprint"] = knowledge.semantic_fingerprint(advisory, "advisory_fingerprint")
        basis = {
            "batch_id": result["batch_id"],
            "reviewer_type": "human_user",
            "reviewer_id": "test-human",
            "decision": "approve_recommendations",
            "statement": "批准按 1 项通过、0 项拒绝执行",
            "decided_at": "2026-07-20T02:00:00Z",
            "authorization_source": "explicit_user_instruction",
            "packet_fingerprint": packet["packet_fingerprint"],
            "advisory_fingerprint": advisory["advisory_fingerprint"],
            "approved_count": 1,
            "rejected_count": 0,
            "review_event_application_authorized": True,
            "automatic_source_update_authorized": False,
            "automatic_lesson_promotion_authorized": False,
            "execution_authorized": False,
        }
        intent = {
            "schema_version": "knowledge-review-human-intent-v1",
            "intent_id": f"knowledge-review-human-intent-{fingerprint(basis)[:16]}",
            **basis,
        }
        intent["intent_fingerprint"] = knowledge.semantic_fingerprint(intent, "intent_fingerprint")
        return result, advisory, intent

    def test_explicit_count_bound_intent_applies_once_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed(registry)
            result, advisory, intent = self._assets(registry)
            approval, events = batch_apply.apply_human_approved_batch(
                ROOT, registry, result["handoff"], result["packet"], advisory, intent
            )
            replay_approval, replay_events = batch_apply.apply_human_approved_batch(
                ROOT, registry, result["handoff"], result["packet"], advisory, intent
            )
            connection = sqlite3.connect(registry)
            try:
                status = connection.execute(
                    "SELECT review_status FROM research_lesson_feedback_drafts WHERE feedback_id='feedback-1'"
                ).fetchone()[0]
                event_count = connection.execute("SELECT COUNT(*) FROM research_knowledge_review_events").fetchone()[0]
                registry_candidate_count = connection.execute(
                    "SELECT COUNT(*) FROM research_lesson_curation_candidates"
                ).fetchone()[0]
            finally:
                connection.close()
        self.assertEqual(approval, replay_approval)
        self.assertEqual(events, replay_events)
        self.assertEqual(status, "approved_for_manual_curation")
        self.assertEqual(event_count, 1)
        self.assertEqual(registry_candidate_count, 0)
        self.assertFalse(approval["automatic_lesson_promotion_authorized"])
        self.assertFalse(events[0]["execution_authorized"])
        plan = post_review.build_post_approval_plan(
            ROOT, result["handoff"], result["packet"], advisory, approval, events
        )
        self.assertEqual(plan["summary"], {
            "lesson_curation_drafts": 1,
            "source_snapshot_rebuilds": 0,
            "source_metadata_rebuilds": 0,
            "closed": 0,
            "total": 1,
        })
        self.assertEqual(plan["actions"][0]["resulting_status"], "approved_for_manual_curation")
        self.assertFalse(plan["actions"][0]["manual_action_required"])
        self.assertFalse(plan["automatic_candidate_creation_authorized"])
        self.assertFalse(plan["automatic_lesson_promotion_authorized"])

    def test_human_statement_compiles_the_exact_intent_without_manual_fingerprints(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed(registry)
            result, advisory, expected = self._assets(registry)
            compiled = batch_apply.build_human_intent(
                ROOT,
                result["handoff"],
                result["packet"],
                advisory,
                "test-human",
                "批准按 1 项通过、0 项拒绝执行",
                "2026-07-20T02:00:00Z",
                1,
                0,
            )
        self.assertEqual(compiled, expected)
        with self.assertRaisesRegex(ValueError, "counts do not match"):
            batch_apply.build_human_intent(
                ROOT,
                result["handoff"],
                result["packet"],
                advisory,
                "test-human",
                "批准错误计数",
                "2026-07-20T02:00:00Z",
                0,
                1,
            )

    def test_post_approval_action_mapping_is_closed_and_deterministic(self):
        self.assertEqual(
            post_review._action("lesson_feedback", "approved"),
            ("approved_for_manual_curation", "prepare_non_authoritative_lesson_curation_draft", "knowledge_curator", False),
        )
        self.assertEqual(
            post_review._action("source_update", "approved"),
            ("approved_for_manual_rebuild", "manual_source_snapshot_rebuild", "human_source_maintainer", True),
        )
        self.assertEqual(
            post_review._action("license_review", "approved"),
            ("active_pinned", "manual_source_metadata_rebuild", "human_source_maintainer", True),
        )
        self.assertEqual(
            post_review._action("lesson_feedback", "rejected"),
            ("rejected", "closed_no_follow_up", "none", False),
        )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            post_review._action("unknown", "approved")

    def test_non_authoritative_curation_draft_has_exact_local_evidence_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed(registry)
            result, advisory, intent = self._assets(registry)
            approval, events = batch_apply.apply_human_approved_batch(
                ROOT, registry, result["handoff"], result["packet"], advisory, intent
            )
        plan = post_review.build_post_approval_plan(
            ROOT, result["handoff"], result["packet"], advisory, approval, events
        )
        evidence = ["tests/test_research_knowledge_batch_apply.py"]
        card = {
            "schema_version": "research-lesson-card-v1",
            "lesson_id": "test-scoped-negative-evidence-v1",
            "title_zh": "测试范围内的负向证据",
            "outcome": "closed_evidence_exhausted",
            "mechanism_keys": ["development-only", "negative-evidence"],
            "scope": {"data": "Development-only"},
            "summary_zh": "该草案仅用于验证本地证据和覆盖约束。",
            "metrics": {},
            "evidence_paths": evidence,
            "source_class": "A",
            "reuse_policy": "warn_and_require_material_difference",
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        card["lesson_fingerprint"] = knowledge.semantic_fingerprint(card, "lesson_fingerprint")
        draft = {
            "draft_id": "lesson-curation-draft-test-scoped-negative-evidence-v1",
            "source_feedback_ids": ["feedback-1"],
            "source_review_event_ids": [events[0]["review_event_id"]],
            "merge_disposition": "standalone",
            "supersedes_lesson_ids": [],
            "material_difference_zh": "测试草案不与现有正式经验卡重复。",
            "evidence_paths": evidence,
            "proposed_card": card,
            "automatic_candidate_registration_authorized": False,
            "automatic_promotion_authorized": False,
        }
        draft["draft_fingerprint"] = knowledge.semantic_fingerprint(draft, "draft_fingerprint")
        context = load_document(ROOT / "research/knowledge/open-source-v1/current-context.json")
        packet = {
            "schema_version": "research-lesson-curation-draft-packet-v1",
            "draft_packet_id": f"knowledge-curation-draft-{plan['plan_fingerprint'][:16]}",
            "generated_at": plan["generated_at"],
            "batch_id": result["batch_id"],
            "post_approval_plan_fingerprint": plan["plan_fingerprint"],
            "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
            "drafts": [draft],
            "coverage": {
                "eligible_feedback_ids": ["feedback-1"],
                "covered_feedback_ids": ["feedback-1"],
                "uncovered_feedback_ids": [],
                "duplicate_feedback_merged": 0,
            },
            "human_promotion_review_required": True,
            "automatic_candidate_registration_authorized": False,
            "automatic_promotion_authorized": False,
            "execution_authorized": False,
        }
        packet["draft_packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "draft_packet_fingerprint")
        self.assertEqual(
            curation_draft.validate_draft_packet(ROOT, result["handoff"], plan, packet),
            {"eligible_feedback": 1, "drafts": 1},
        )
        candidates, promotion_packet = candidate_compiler.compile_candidate_artifacts(
            ROOT, result["handoff"], plan, packet
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["status"], "pending_human_promotion_review")
        self.assertFalse(candidates[0]["automatic_promotion_authorized"])
        self.assertEqual(promotion_packet["candidate_count"], 1)
        self.assertTrue(promotion_packet["human_approval_required"])
        self.assertFalse(promotion_packet["automatic_promotion_authorized"])
        decision_request = candidate_compiler.build_promotion_decision_request(
            result["batch_id"], promotion_packet, candidates
        )
        self.assertEqual(decision_request["candidate_count"], 1)
        self.assertEqual(
            decision_request["candidates"][0]["candidate_fingerprint"],
            candidates[0]["candidate_fingerprint"],
        )
        self.assertIn(result["batch_id"], decision_request["decision_contract"]["approve_all_statement_zh"])
        self.assertTrue(decision_request["human_decision_required"])
        self.assertIn("automatic_lesson_promotion", decision_request["prohibited_effects"])
        self.assertEqual(
            knowledge.semantic_fingerprint(decision_request, "decision_request_fingerprint"),
            decision_request["decision_request_fingerprint"],
        )
        first_compile_result = candidate_compiler.build_compilation_result(
            result["batch_id"], result["handoff"], candidates, promotion_packet, True
        )
        repeated_compile_result = candidate_compiler.build_compilation_result(
            result["batch_id"], result["handoff"], candidates, promotion_packet, False
        )
        self.assertEqual(first_compile_result["decision_request"], decision_request)
        self.assertNotIn("decision_request", repeated_compile_result)
        self.assertEqual(repeated_compile_result["status"], "awaiting_human_promotion_review")
        promotion_intent = promotion_apply.build_human_intent(
            ROOT,
            result["batch_id"],
            promotion_packet,
            candidates,
            "test-human",
            "批准全部 1 项 lesson 晋升",
            "2026-07-20T03:00:00Z",
            {candidates[0]["candidate_id"]: "approved"},
        )
        promotion_approval = promotion_apply.build_approval(
            ROOT, promotion_packet, candidates, promotion_intent
        )
        promotion_events = promotion_apply.build_events(ROOT, promotion_packet, promotion_approval)
        target_context, target_manifest, target_payloads, superseded = promotion_apply.build_target_snapshot(
            ROOT, promotion_packet, candidates, promotion_approval
        )
        self.assertEqual(target_manifest["counts"]["lessons"], len(context["lessons"]) + 1)
        self.assertIn(card["lesson_id"], {item["lesson_id"] for item in target_context["lessons"]})
        self.assertEqual(superseded, set())
        self.assertFalse(promotion_approval["automatic_lesson_promotion_authorized"])
        self.assertFalse(promotion_events[0]["execution_authorized"])
        with tempfile.TemporaryDirectory() as snapshot_directory:
            snapshot_repo = Path(snapshot_directory)
            shutil.copytree(
                ROOT / "research/knowledge/open-source-v1",
                snapshot_repo / "research/knowledge/open-source-v1",
            )
            shutil.copytree(
                ROOT / "research/knowledge/schemas",
                snapshot_repo / "research/knowledge/schemas",
            )
            shutil.copytree(
                ROOT / "research/knowledge/evaluation",
                snapshot_repo / "research/knowledge/evaluation",
            )
            state_path = snapshot_repo / "research/director/current-research-state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "research/director/current-research-state.json", state_path)
            restore_snapshot = promotion_apply._publish_snapshot(
                snapshot_repo, target_payloads, target_context
            )
            self.assertEqual(
                load_document(snapshot_repo / "research/knowledge/open-source-v1/current-context.json"),
                target_context,
            )
            effective_state = promotion_apply.build_effective_research_state(
                snapshot_repo,
                result["handoff"],
                promotion_packet,
                promotion_approval,
            )
            self.assertEqual(
                effective_state["open_source_knowledge"]["knowledge_snapshot_fingerprint"],
                target_manifest["knowledge_snapshot_fingerprint"],
            )
            retrieval_evaluation = knowledge_maintenance.evaluate_retrieval(
                snapshot_repo, effective_state
            )
            self.assertEqual(retrieval_evaluation["status"], "passed")
            self.assertEqual(
                retrieval_evaluation["knowledge_snapshot_fingerprint"],
                target_manifest["knowledge_snapshot_fingerprint"],
            )
            generic_archive = (
                snapshot_repo / result["handoff"]["planned_promotion_review_packet_path"]
            ).parent
            write_json(generic_archive / "promotion-review-packet.json", promotion_packet)
            write_json(generic_archive / "promotion-approval.json", promotion_approval)
            write_json(generic_archive / "promotion-published-manifest.json", target_manifest)
            summarized = knowledge.knowledge_state_summary(snapshot_repo)
            self.assertEqual(
                summarized["maintenance"]["last_promotion_batch"]["approved"], 1
            )
            self.assertEqual(
                summarized["maintenance"]["promotion_review_packet"],
                result["handoff"]["planned_promotion_review_packet_path"],
            )
            restore_snapshot()
            self.assertEqual(
                load_document(snapshot_repo / "research/knowledge/open-source-v1/current-context.json"),
                context,
            )
        with tempfile.TemporaryDirectory() as registry_directory:
            promotion_registry = Path(registry_directory) / "director.db"
            connection = open_director_registry(promotion_registry)
            try:
                for _ in range(2):
                    connection.execute("BEGIN IMMEDIATE")
                    promotion_apply.apply_registry_state(
                        connection,
                        candidates,
                        promotion_approval,
                        promotion_events,
                        target_context,
                        superseded,
                    )
                    connection.commit()
                promoted_status = connection.execute(
                    "SELECT status FROM research_lesson_curation_candidates WHERE candidate_id=?",
                    (candidates[0]["candidate_id"],),
                ).fetchone()[0]
                promotion_event_count = connection.execute(
                    "SELECT COUNT(*) FROM research_knowledge_review_events WHERE review_type='lesson_promotion'"
                ).fetchone()[0]
                formal_lesson_count = connection.execute(
                    "SELECT COUNT(*) FROM open_source_research_lessons"
                ).fetchone()[0]
                promotion_apply.register_effective_research_state(
                    connection, effective_state, promotion_approval
                )
                promotion_apply.register_effective_research_state(
                    connection, effective_state, promotion_approval
                )
                full_registry_view = registry_exporter.export_connection(connection)
                registry_view = registry_exporter.merge_knowledge_tables(
                    load_document(ROOT / "research/director/registry-records.json"),
                    full_registry_view,
                )
                registry_view = promotion_apply.merge_effective_state_snapshots(
                    registry_view,
                    full_registry_view,
                )
                promotion_health = knowledge_maintenance.build_health(
                    ROOT,
                    registry_view,
                    load_document(ROOT / "reports/audits/open-source-learning-v1/source-refresh-report.json"),
                    retrieval_evaluation,
                    promotion_approval["decided_at"],
                )
            finally:
                connection.close()
        self.assertEqual(promoted_status, "promoted")
        self.assertEqual(promotion_event_count, 1)
        self.assertEqual(formal_lesson_count, len(context["lessons"]) + 1)
        self.assertNotEqual(promotion_health["status"], "failed")
        self.assertEqual(
            promotion_health["metrics"]["lesson_curation_candidates_pending_promotion"], 0
        )
        self.assertIn(
            effective_state["snapshot_id"],
            {
                row["snapshot_id"]
                for row in registry_view["tables"]["research_state_snapshots"]
            },
        )
        rejected_intent = promotion_apply.build_human_intent(
            ROOT,
            result["batch_id"],
            promotion_packet,
            candidates,
            "test-human",
            "拒绝该 lesson 晋升",
            "2026-07-20T03:10:00Z",
            {candidates[0]["candidate_id"]: "rejected"},
        )
        rejected_approval = promotion_apply.build_approval(
            ROOT, promotion_packet, candidates, rejected_intent
        )
        rejected_context, rejected_manifest, _, rejected_superseded = promotion_apply.build_target_snapshot(
            ROOT, promotion_packet, candidates, rejected_approval
        )
        self.assertEqual(rejected_manifest["counts"]["lessons"], len(context["lessons"]))
        self.assertNotIn(card["lesson_id"], {item["lesson_id"] for item in rejected_context["lessons"]})
        self.assertEqual(rejected_superseded, set())

        replacement_candidates = copy.deepcopy(candidates)
        replaced_id = context["lessons"][0]["lesson_id"]
        replacement_candidates[0]["merge_disposition"] = "replace_existing_lesson"
        replacement_candidates[0]["supersedes_lesson_ids"] = [replaced_id]
        replacement_candidates[0]["candidate_fingerprint"] = knowledge.semantic_fingerprint(
            replacement_candidates[0], "candidate_fingerprint"
        )
        replacement_packet = copy.deepcopy(promotion_packet)
        replacement_packet["candidates"][0]["candidate_fingerprint"] = replacement_candidates[0]["candidate_fingerprint"]
        replacement_packet["candidates"][0]["supersedes_lesson_ids"] = [replaced_id]
        replacement_packet["packet_fingerprint"] = knowledge.semantic_fingerprint(
            replacement_packet, "packet_fingerprint"
        )
        replacement_intent = promotion_apply.build_human_intent(
            ROOT,
            result["batch_id"],
            replacement_packet,
            replacement_candidates,
            "test-human",
            "批准替换一项正式 lesson",
            "2026-07-20T03:20:00Z",
            {replacement_candidates[0]["candidate_id"]: "approved"},
        )
        replacement_approval = promotion_apply.build_approval(
            ROOT, replacement_packet, replacement_candidates, replacement_intent
        )
        replacement_context, replacement_manifest, _, replacement_superseded = promotion_apply.build_target_snapshot(
            ROOT, replacement_packet, replacement_candidates, replacement_approval
        )
        replacement_ids = {item["lesson_id"] for item in replacement_context["lessons"]}
        self.assertEqual(replacement_manifest["counts"]["lessons"], len(context["lessons"]))
        self.assertNotIn(replaced_id, replacement_ids)
        self.assertIn(card["lesson_id"], replacement_ids)
        self.assertEqual(replacement_superseded, {replaced_id})
        with tempfile.TemporaryDirectory() as output_directory:
            output_repo = Path(output_directory)
            base_root = output_repo / "research/knowledge/open-source-v1"
            base_root.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(
                ROOT / "research/knowledge/open-source-v1/current-context.json",
                base_root / "current-context.json",
            )
            shutil.copyfile(
                ROOT / "research/knowledge/open-source-v1/manifest.json",
                base_root / "manifest.json",
            )
            self.assertTrue(candidate_compiler.publish_candidate_artifacts(
                output_repo, result["handoff"], candidates, promotion_packet
            ))
            self.assertFalse(candidate_compiler.publish_candidate_artifacts(
                output_repo, result["handoff"], candidates, promotion_packet
            ))
            archived_context = output_repo / result["handoff"]["planned_promotion_base_context_path"]
            archived_manifest = output_repo / result["handoff"]["planned_promotion_base_manifest_path"]
            self.assertEqual(
                sha256_file(archived_context),
                load_document(archived_manifest)["context_sha256"],
            )
            candidate_path = (
                output_repo
                / result["handoff"]["planned_curation_candidate_root"]
                / f"{candidates[0]['candidate_id']}.json"
            )
            candidate_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable curation candidate artifact conflict"):
                candidate_compiler.publish_candidate_artifacts(
                    output_repo, result["handoff"], candidates, promotion_packet
                )
        tampered = copy.deepcopy(packet)
        tampered["drafts"][0]["evidence_paths"] = ["README.md"]
        tampered["drafts"][0]["proposed_card"]["evidence_paths"] = ["README.md"]
        tampered["drafts"][0]["proposed_card"]["lesson_fingerprint"] = knowledge.semantic_fingerprint(
            tampered["drafts"][0]["proposed_card"], "lesson_fingerprint"
        )
        tampered["drafts"][0]["draft_fingerprint"] = knowledge.semantic_fingerprint(
            tampered["drafts"][0], "draft_fingerprint"
        )
        tampered["draft_packet_fingerprint"] = knowledge.semantic_fingerprint(tampered, "draft_packet_fingerprint")
        with self.assertRaisesRegex(ValueError, "outside its approved actions"):
            curation_draft.validate_draft_packet(ROOT, result["handoff"], plan, tampered)

        collision = copy.deepcopy(packet)
        collision["drafts"][0]["proposed_card"]["lesson_id"] = context["lessons"][0]["lesson_id"]
        collision["drafts"][0]["proposed_card"]["lesson_fingerprint"] = knowledge.semantic_fingerprint(
            collision["drafts"][0]["proposed_card"], "lesson_fingerprint"
        )
        collision["drafts"][0]["draft_fingerprint"] = knowledge.semantic_fingerprint(
            collision["drafts"][0], "draft_fingerprint"
        )
        collision["draft_packet_fingerprint"] = knowledge.semantic_fingerprint(collision, "draft_packet_fingerprint")
        with self.assertRaisesRegex(ValueError, "collides with a formal lesson"):
            curation_draft.validate_draft_packet(ROOT, result["handoff"], plan, collision)

    def test_promotion_cli_is_transactional_and_idempotent_in_isolation(self):
        real_context_before = (
            ROOT / "research/knowledge/open-source-v1/current-context.json"
        ).read_bytes()
        strategy_hashes_before = {
            path.name: sha256_file(path)
            for path in (
                ROOT / "strategies/RegimeAwareV6.py",
                ROOT / "strategies/regime_aware_base.py",
            )
        }
        with tempfile.TemporaryDirectory() as directory:
            repo, batch_id, handoff, candidate = self._promotion_cli_fixture(directory)
            formal_before = len(
                load_document(repo / "research/knowledge/open-source-v1/current-context.json")["lessons"]
            )
            first = self._run_promotion_cli(repo, batch_id)
            self.assertEqual(first.returncode, 0, msg=f"{first.stdout}\n{first.stderr}")
            first_result = json.loads(first.stdout)
            self.assertEqual(first_result["retrieval_recertification"], "passed")
            self.assertTrue(first_result["knowledge_broker_ready"])
            self.assertNotEqual(first_result["learning_loop_health"], "failed")
            context = load_document(repo / "research/knowledge/open-source-v1/current-context.json")
            state = load_document(repo / "research/director/current-research-state.json")
            evaluation = load_document(
                repo / "reports/audits/open-source-learning-v1/retrieval-evaluation.json"
            )
            self.assertEqual(len(context["lessons"]), formal_before + 1)
            self.assertEqual(
                state["open_source_knowledge"]["knowledge_snapshot_fingerprint"],
                context["knowledge_snapshot_fingerprint"],
            )
            self.assertEqual(
                evaluation["knowledge_snapshot_fingerprint"],
                context["knowledge_snapshot_fingerprint"],
            )
            selection = knowledge.broker_selection(
                repo,
                "manual_request",
                "e2e promotion recertification",
                fingerprint({"temporary": "promotion-e2e"}),
                state,
            )
            self.assertIn(
                candidate["proposed_card"]["lesson_id"],
                {item["lesson_id"] for item in selection["selected_lessons"]},
            )
            archive_paths = [
                repo / handoff[key]
                for key in (
                    "planned_promotion_human_intent_path",
                    "planned_promotion_approval_path",
                    "planned_promotion_events_path",
                    "planned_published_manifest_path",
                )
            ]
            archive_before_replay = {path: path.read_bytes() for path in archive_paths}
            second = self._run_promotion_cli(repo, batch_id)
            self.assertEqual(second.returncode, 0, msg=f"{second.stdout}\n{second.stderr}")
            self.assertEqual(
                {path: path.read_bytes() for path in archive_paths},
                archive_before_replay,
            )
            connection = sqlite3.connect(repo / "research/registry/stage4a-director.db")
            try:
                candidate_count = connection.execute(
                    "SELECT COUNT(*) FROM research_lesson_curation_candidates"
                ).fetchone()[0]
                event_count = connection.execute(
                    "SELECT COUNT(*) FROM research_knowledge_review_events WHERE review_type='lesson_promotion'"
                ).fetchone()[0]
                state_count = connection.execute(
                    "SELECT COUNT(*) FROM research_state_snapshots WHERE snapshot_id=?",
                    (state["snapshot_id"],),
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(candidate_count, 1)
            self.assertEqual(event_count, 1)
            self.assertEqual(state_count, 1)
        self.assertEqual(
            (ROOT / "research/knowledge/open-source-v1/current-context.json").read_bytes(),
            real_context_before,
        )
        self.assertEqual(
            {
                path.name: sha256_file(path)
                for path in (
                    ROOT / "strategies/RegimeAwareV6.py",
                    ROOT / "strategies/regime_aware_base.py",
                )
            },
            strategy_hashes_before,
        )

    def test_promotion_cli_retrieval_failure_rolls_back_every_surface(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, batch_id, handoff, candidate = self._promotion_cli_fixture(directory)
            cases_path = repo / "research/knowledge/evaluation/retrieval-cases-v1.json"
            cases = load_document(cases_path)
            for case in cases["cases"]:
                case["expected_id"] = "intentionally-missing-retrieval-target"
            write_json(cases_path, cases)
            protected_paths = [
                repo / relative
                for relative in (
                    "research/knowledge/open-source-v1/current-context.json",
                    "research/knowledge/open-source-v1/manifest.json",
                    "research/director/current-research-state.json",
                    "research/director/current-research-state.md",
                    "research/director/registry-records.json",
                    "reports/audits/open-source-learning-v1/retrieval-evaluation.json",
                    "reports/audits/open-source-learning-v1/learning-loop-health.json",
                )
            ]
            before = {path: path.read_bytes() for path in protected_paths}
            failed = self._run_promotion_cli(repo, batch_id)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("failed retrieval recertification", failed.stderr)
            self.assertEqual({path: path.read_bytes() for path in protected_paths}, before)
            self.assertFalse(
                (
                    repo
                    / "research/knowledge/open-source-v1/lessons"
                    / f"{candidate['proposed_card']['lesson_id']}.json"
                ).exists()
            )
            for key in (
                "planned_promotion_human_intent_path",
                "planned_promotion_approval_path",
                "planned_promotion_events_path",
                "planned_published_manifest_path",
            ):
                self.assertFalse((repo / handoff[key]).exists())
            connection = sqlite3.connect(repo / "research/registry/stage4a-director.db")
            try:
                counts = [
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "research_lesson_curation_candidates",
                        "research_knowledge_review_events",
                        "open_source_research_lessons",
                        "research_state_snapshots",
                    )
                ]
            finally:
                connection.close()
            self.assertEqual(counts, [0, 0, 0, 0])

    def test_promotion_cli_immutable_archive_conflict_stops_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, batch_id, handoff, candidate = self._promotion_cli_fixture(directory)
            conflict_path = repo / handoff["planned_promotion_approval_path"]
            write_json(conflict_path, {"conflict": True})
            context_before = (
                repo / "research/knowledge/open-source-v1/current-context.json"
            ).read_bytes()
            failed = self._run_promotion_cli(repo, batch_id)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("immutable promotion artifact conflict", failed.stderr)
            self.assertEqual(
                (
                    repo / "research/knowledge/open-source-v1/current-context.json"
                ).read_bytes(),
                context_before,
            )
            self.assertEqual(load_document(conflict_path), {"conflict": True})
            self.assertFalse(
                (
                    repo
                    / "research/knowledge/open-source-v1/lessons"
                    / f"{candidate['proposed_card']['lesson_id']}.json"
                ).exists()
            )
            connection = sqlite3.connect(repo / "research/registry/stage4a-director.db")
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM research_lesson_curation_candidates"
                    ).fetchone()[0],
                    0,
                )
            finally:
                connection.close()

    def test_promotion_cli_database_failure_rolls_back_published_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, batch_id, handoff, candidate = self._promotion_cli_fixture(directory)
            registry = repo / "research/registry/stage4a-director.db"
            connection = sqlite3.connect(registry)
            try:
                connection.execute(
                    """
                    CREATE TRIGGER inject_promotion_state_failure
                    BEFORE INSERT ON research_state_snapshots
                    BEGIN
                      SELECT RAISE(ABORT, 'injected-promotion-state-failure');
                    END
                    """
                )
                connection.commit()
            finally:
                connection.close()
            protected_paths = [
                repo / relative
                for relative in (
                    "research/knowledge/open-source-v1/current-context.json",
                    "research/knowledge/open-source-v1/manifest.json",
                    "research/director/current-research-state.json",
                    "research/director/current-research-state.md",
                    "research/director/registry-records.json",
                    "reports/audits/open-source-learning-v1/retrieval-evaluation.json",
                    "reports/audits/open-source-learning-v1/learning-loop-health.json",
                )
            ]
            before = {path: path.read_bytes() for path in protected_paths}
            failed = self._run_promotion_cli(repo, batch_id)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("injected-promotion-state-failure", failed.stderr)
            self.assertEqual({path: path.read_bytes() for path in protected_paths}, before)
            self.assertFalse(
                (
                    repo
                    / "research/knowledge/open-source-v1/lessons"
                    / f"{candidate['proposed_card']['lesson_id']}.json"
                ).exists()
            )
            connection = sqlite3.connect(registry)
            try:
                counts = [
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "research_lesson_curation_candidates",
                        "research_knowledge_review_events",
                        "open_source_research_lessons",
                        "research_state_snapshots",
                    )
                ]
            finally:
                connection.close()
            self.assertEqual(counts, [0, 0, 0, 0])
            for key in (
                "planned_promotion_human_intent_path",
                "planned_promotion_approval_path",
                "planned_promotion_events_path",
                "planned_published_manifest_path",
            ):
                self.assertFalse((repo / handoff[key]).exists())

    def test_count_drift_fails_before_registry_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed(registry)
            result, advisory, intent = self._assets(registry)
            stale = copy.deepcopy(intent)
            stale["approved_count"] = 0
            stale["rejected_count"] = 1
            identity = {key: value for key, value in stale.items() if key not in {"schema_version", "intent_id", "intent_fingerprint"}}
            stale["intent_id"] = f"knowledge-review-human-intent-{fingerprint(identity)[:16]}"
            stale["intent_fingerprint"] = knowledge.semantic_fingerprint(stale, "intent_fingerprint")
            with self.assertRaisesRegex(ValueError, "counts do not match"):
                batch_apply.apply_human_approved_batch(
                    ROOT, registry, result["handoff"], result["packet"], advisory, stale
                )
            connection = sqlite3.connect(registry)
            try:
                status = connection.execute(
                    "SELECT review_status FROM research_lesson_feedback_drafts WHERE feedback_id='feedback-1'"
                ).fetchone()[0]
                event_count = connection.execute("SELECT COUNT(*) FROM research_knowledge_review_events").fetchone()[0]
            finally:
                connection.close()
        self.assertEqual(status, "pending_human_review")
        self.assertEqual(event_count, 0)


if __name__ == "__main__":
    unittest.main()
