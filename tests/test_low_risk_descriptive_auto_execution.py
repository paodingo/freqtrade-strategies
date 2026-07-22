import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_director_common import fingerprint, load_document, open_director_registry, sha256_file  # noqa: E402
import research_lesson_feedback as lesson_feedback  # noqa: E402
import export_director_registry as registry_exporter  # noqa: E402
import research_knowledge_review as knowledge_review  # noqa: E402
import research_descriptive_worker as descriptive_worker  # noqa: E402
import research_worker_supervisor as worker_supervisor  # noqa: E402
import research_worker_queue as worker_queue  # noqa: E402
from route_research_approval import route_proposal  # noqa: E402


CONSTITUTION_PATH = ROOT / "research/governance/research-constitution.yaml"
CONTRACT_PATH = ROOT / "research/governance/low-risk-development-descriptive-execution-contract-v1.json"
CONTRACT_APPROVAL_PATH = ROOT / "research/governance/approvals/low-risk-development-descriptive-execution-v1-approval.json"


class LowRiskDescriptiveAutoExecutionTests(unittest.TestCase):
    def setUp(self):
        self.constitution = load_document(CONSTITUTION_PATH)
        self.contract = load_document(CONTRACT_PATH)
        self.contract_approval = load_document(CONTRACT_APPROVAL_PATH)
        self.proposal_id = "discovery-contract-fixture-v1"
        artifacts = [
            f"research/analysis/{self.proposal_id}/analysis.json",
            f"reports/audits/{self.proposal_id}/report.md",
        ]
        self.proposal = {
            "proposal_id": self.proposal_id,
            "risk_class": "low",
            "estimated_experiments": 0,
            "estimated_wall_clock_minutes": 35,
            "estimated_compute_cost": "low",
            "contamination_risk": "none",
            "required_datasets": [
                {
                    "dataset_id": "futures-dev-fixture",
                    "manifest_path": "research/data/snapshots/futures-dev-fixture/manifest.yaml",
                    "manifest_sha256": "a" * 64,
                    "access": "development_only",
                }
            ],
            "required_runtime": {"path": "research/runtime/freqtrade-runtime.yaml", "sha256": "b" * 64},
            "required_policy": {"path": "research/evaluation/evaluation-policy.yaml", "sha256": "c" * 64},
            "data_scope": {"sealed_development_only": True, "validation": False, "holdout": False},
            "validation_requirement": "none",
            "holdout_requirement": "none",
            "allowed_changes": artifacts,
            "required_artifacts": artifacts,
            "forbidden_changes": list(self.contract["prohibited_actions"]),
            "referenced_variables": [],
            "referenced_mechanisms": ["cross_pair_descriptive"],
            "proposed_method": {"type": "discovery_cross_pair_descriptive_minimal_test", "execution": "unexecuted_proposal_requires_separate_authorization"},
            "branch_closure_reopen_check": {"checked": True, "blocked": False, "reason_code": None},
            "duplicate_research_check": {"checked": True, "duplicate": False, "reason_code": None},
            "execution_authorized": False,
        }

    def route(self, proposal):
        return route_proposal(
            proposal,
            self.constitution,
            low_risk_contract=self.contract,
            low_risk_contract_approval=self.contract_approval,
            constitution_sha256=sha256_file(CONSTITUTION_PATH),
            contract_sha256=sha256_file(CONTRACT_PATH),
            created_at="2026-07-20T12:00:00Z",
        )

    def test_exact_development_only_proposal_receives_descriptive_authority(self):
        route = self.route(self.proposal)
        self.assertEqual(route["decision"], "auto_approved_under_constitution")
        self.assertTrue(route["approval_granted"])
        self.assertTrue(route["descriptive_execution_authorized_under_contract"])
        self.assertFalse(route["execution_authorized_under_constitution"])
        self.assertFalse(route["authorization"]["campaign_execution_authorized"])
        self.assertFalse(route["authorization"]["trading_execution_authorized"])
        self.assertEqual(
            route["authorization"]["exact_artifact_paths"],
            self.proposal["required_artifacts"],
        )

    def test_scope_expansion_fails_closed(self):
        cases = []
        experiments = copy.deepcopy(self.proposal)
        experiments["estimated_experiments"] = 1
        cases.append(experiments)
        validation = copy.deepcopy(self.proposal)
        validation["data_scope"]["validation"] = True
        cases.append(validation)
        artifact = copy.deepcopy(self.proposal)
        artifact["allowed_changes"].append("research/candidates/forbidden.yaml")
        cases.append(artifact)
        prohibition = copy.deepcopy(self.proposal)
        prohibition["forbidden_changes"].remove("backtest")
        cases.append(prohibition)
        for proposal in cases:
            with self.subTest(proposal=proposal):
                route = self.route(proposal)
                self.assertFalse(route["descriptive_execution_authorized_under_contract"])
                self.assertFalse(route["authorization"]["descriptive_execution_authorized"])

    def test_contract_or_human_approval_hash_drift_fails_closed(self):
        approval = copy.deepcopy(self.contract_approval)
        approval["approved_contract_sha256"] = "0" * 64
        route = route_proposal(
            self.proposal,
            self.constitution,
            low_risk_contract=self.contract,
            low_risk_contract_approval=approval,
            constitution_sha256=sha256_file(CONSTITUTION_PATH),
            contract_sha256=sha256_file(CONTRACT_PATH),
            created_at="2026-07-20T12:00:00Z",
        )
        self.assertFalse(route["descriptive_execution_authorized_under_contract"])
        self.assertFalse(route["approval_granted"])

    def test_worker_job_carries_only_bounded_descriptive_authority(self):
        route = self.route(self.proposal)
        proposal = copy.deepcopy(self.proposal)
        proposal.update(
            {
                "approval_requirement": route["decision"],
                "descriptive_execution_authorized": True,
                "descriptive_execution_authorization": route["authorization"],
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            connection = open_director_registry(Path(temporary) / "director.db")
            job = worker_queue.enqueue_descriptive_execution_job(
                connection,
                run_id="discovery-run-fixture",
                proposal=proposal,
                task_path="research/director/discovery-handoff/proposals/fixture.json",
                created_at="2026-07-20T12:00:00Z",
            )
            connection.commit()
            connection.close()
        payload = json.loads(job["payload_json"])
        self.assertEqual(job["stage"], "descriptive_execution")
        self.assertTrue(payload["descriptive_execution_authorized"])
        self.assertFalse(payload["campaign_execution_authorized"])
        self.assertFalse(payload["candidate_creation_authorized"])
        self.assertFalse(payload["strategy_mutation_authorized"])

    def test_guard_derives_only_exact_paths_from_valid_authorized_proposal(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            guard = repo / "scripts/guard_harness_diff.js"
            guard.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/guard_harness_diff.js", guard)
            constitution = repo / "research/governance/research-constitution.yaml"
            constitution.parent.mkdir(parents=True)
            shutil.copy2(CONSTITUTION_PATH, constitution)
            contract = repo / "research/governance/low-risk-development-descriptive-execution-contract-v1.json"
            shutil.copy2(CONTRACT_PATH, contract)
            contract_approval = repo / "research/governance/approvals/low-risk-development-descriptive-execution-v1-approval.json"
            contract_approval.parent.mkdir(parents=True)
            shutil.copy2(CONTRACT_APPROVAL_PATH, contract_approval)

            proposal_id = "discovery-guard-fixture-v1"
            artifacts = [
                f"research/analysis/{proposal_id}/analysis.json",
                f"reports/audits/{proposal_id}/report.md",
            ]
            authorization = {
                "authorization_mode": "standing_l1_development_descriptive_contract",
                "contract_id": "low-risk-development-descriptive-execution-v1",
                "contract_sha256": sha256_file(contract),
                "exact_artifact_paths": artifacts,
                "descriptive_execution_authorized": True,
                "campaign_execution_authorized": False,
                "trading_execution_authorized": False,
                "strategy_mutation_authorized": False,
            }
            authorization["authorization_fingerprint"] = fingerprint(authorization)
            proposal = {
                "proposal_id": proposal_id,
                "risk_class": "low",
                "execution_authorized": False,
                "descriptive_execution_authorized": True,
                "approval_requirement": "auto_approved_under_constitution",
                "allowed_changes": artifacts,
                "required_artifacts": artifacts,
                "descriptive_execution_authorization": authorization,
            }
            run_path = repo / "research/director/discovery-handoff/proposals/fixture.json"
            run_path.parent.mkdir(parents=True)
            run_path.write_text(json.dumps({"proposals": [proposal]}), encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-qm", "baseline"],
                cwd=repo,
                check=True,
            )
            analysis = repo / artifacts[0]
            analysis.parent.mkdir(parents=True)
            analysis.write_text("{}\n", encoding="utf-8")
            valid = subprocess.run(
                ["node", str(guard)], cwd=repo, text=True, capture_output=True
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)

            proposal["descriptive_execution_authorization"]["campaign_execution_authorized"] = True
            run_path.write_text(json.dumps({"proposals": [proposal]}), encoding="utf-8")
            invalid = subprocess.run(
                ["node", str(guard)], cwd=repo, text=True, capture_output=True
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertIn(artifacts[0], invalid.stderr)

    def _feedback_repo(self, root: Path) -> tuple[Path, dict]:
        for relative in (
            "research/governance/low-risk-development-descriptive-execution-contract-v1.json",
            "research/governance/low-risk-descriptive-knowledge-feedback-contract-v1.json",
            "research/governance/approvals/low-risk-descriptive-knowledge-feedback-v1-approval.json",
            "research/governance/descriptive-worker-handler-contract-v1.json",
            "research/governance/approvals/descriptive-worker-handler-v1-approval.json",
            "research/governance/legacy-development-manifest-compatibility-v1.json",
            "research/governance/approvals/legacy-development-manifest-compatibility-v1-approval.json",
            "research/temporal/ranging-short-ablation-temporal-slices-v1.yaml",
            "research/director/descriptive-worker-supervisor-v1.json",
            "research/governance/approvals/development-descriptive-worker-supervisor-v1-approval.json",
            "research/governance/descriptive-worker-failure-recovery-contract-v1.json",
            "research/governance/approvals/descriptive-worker-failure-recovery-v1-approval.json",
            "research/director/knowledge-review-batch-policy-v1.json",
            "research/director/knowledge-review-sla-policy-v1.json",
            "research/knowledge/schemas/research-lesson-feedback-draft.schema.json",
            "research/knowledge/schemas/knowledge-review-packet.schema.json",
            "research/knowledge/schemas/knowledge-review-batch-handoff.schema.json",
            "research/knowledge/schemas/knowledge-review-recommendations.schema.json",
            "research/knowledge/prompts/knowledge-review-advisor-v1.md",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        route = self.route(self.proposal)
        proposal = copy.deepcopy(self.proposal)
        proposal.update(
            {
                "approval_requirement": route["decision"],
                "descriptive_execution_authorized": True,
                "descriptive_execution_authorization": route["authorization"],
            }
        )
        return root, proposal

    def _sealed_fixture_dataset(self, repo: Path, symbol: str, offset: float) -> dict:
        dataset_id = f"futures-dev-{symbol.lower()}-fixture-v1"
        root = repo / "research/data/snapshots" / dataset_id
        data_root = root / "data/futures"
        data_root.mkdir(parents=True, exist_ok=True)
        files = []
        for timeframe, periods, hours in (("1h", 5800, 1), ("4h", 1450, 4)):
            dates = pd.date_range("2024-01-01T00:00:00Z", periods=periods, freq=f"{hours}h")
            trend = np.linspace(0, 25 + offset, periods)
            cycle = np.sin(np.arange(periods) / (17 + offset)) * (1 + offset / 10)
            close = 100 + offset + trend + cycle
            frame = pd.DataFrame(
                {
                    "date": dates,
                    "open": close - 0.1,
                    "high": close + 0.4,
                    "low": close - 0.4,
                    "close": close,
                    "volume": 1000 + offset * 100 + (np.arange(periods) % 97),
                }
            )
            relative = (
                f"research/data/snapshots/{dataset_id}/data/futures/"
                f"{symbol}_USDT_USDT-{timeframe}-futures.feather"
            )
            path = repo / relative
            frame.to_feather(path)
            files.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        manifest = {
            "schema_version": "fixture-manifest-v1",
            "dataset_id": dataset_id,
            "pairs": [f"{symbol}/USDT:USDT"],
            "timeframes": ["1h", "4h"],
            "candle_types": ["futures"],
            "files": files,
            "validation_or_holdout": False,
            "backtest_calls": 0,
            "candidate_created": False,
            "strategy_modified": False,
            "campaign_mutable": False,
            "sealed": True,
            "intended_use": "development_descriptive_only",
        }
        manifest_path = root / "manifest.yaml"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        return {
            "dataset_id": dataset_id,
            "manifest_path": manifest_path.relative_to(repo).as_posix(),
            "manifest_sha256": sha256_file(manifest_path),
            "access": "development_only",
        }

    def _queued_worker_fixture(self, repo: Path, proposal: dict) -> tuple[Path, dict]:
        proposal["required_datasets"] = [
            self._sealed_fixture_dataset(repo, "AAA", 1.0),
            self._sealed_fixture_dataset(repo, "BBB", 3.0),
        ]
        route = self.route(proposal)
        proposal.update(
            {
                "approval_requirement": route["decision"],
                "descriptive_execution_authorized": True,
                "descriptive_execution_authorization": route["authorization"],
            }
        )
        task_relative = "research/director/discovery-handoff/proposals/worker-fixture.json"
        task_path = repo / task_relative
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(json.dumps({"proposals": [proposal]}, sort_keys=True), encoding="utf-8")
        registry = repo / "research/registry/stage4a-director.db"
        connection = open_director_registry(registry)
        worker_queue.enqueue_worker_job(
            connection,
            run_id="unrelated-research-run",
            stage="researcher",
            round_number=1,
            task_path="research/discovery/runs/unrelated/task.md",
            inbox_path="research/discovery/runs/unrelated/inbox",
            created_at="2026-07-20T12:29:00Z",
        )
        job = worker_queue.enqueue_descriptive_execution_job(
            connection,
            run_id="descriptive-worker-run",
            proposal=proposal,
            task_path=task_relative,
            created_at="2026-07-20T12:30:00Z",
        )
        connection.commit()
        connection.close()
        return registry, job

    def _claim_with_artifacts(self, repo: Path, registry: Path, proposal: dict) -> dict:
        connection = open_director_registry(registry)
        job = worker_queue.enqueue_descriptive_execution_job(
            connection,
            run_id="discovery-run-feedback-fixture",
            proposal=proposal,
            task_path="research/director/discovery-handoff/proposals/fixture.json",
            created_at="2026-07-20T12:20:00Z",
        )
        connection.commit()
        connection.close()
        claimed = worker_queue.claim_next_job(
            registry,
            "worker-feedback",
            now="2026-07-20T12:20:01Z",
        )
        analysis_path = repo / proposal["required_artifacts"][0]
        report_path = repo / proposal["required_artifacts"][1]
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(
            json.dumps(
                {
                    "schema_version": "descriptive-test-v1",
                    "proposal_id": proposal["proposal_id"],
                    "execution_scope": {
                        "development_only": True,
                        "network_accessed": False,
                        "validation_accesses": 0,
                        "holdout_accesses": 0,
                        "backtests": 0,
                        "signals_or_trades_generated": 0,
                        "candidates_created": 0,
                        "strategy_changes": 0,
                        "promotions": 0,
                    },
                    "source_integrity": {"all_ok": True},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        report_path.write_text("# descriptive test\n", encoding="utf-8")
        self.assertEqual(claimed["job_id"], job["job_id"])
        return claimed

    def _seed_pending_feedback(
        self, repo: Path, registry: Path, count: int, created_at: str
    ) -> None:
        evidence_path = repo / "evidence/supervisor-feedback.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("{}\n", encoding="utf-8")
        payload = json.dumps(
            {
                "evidence_artifacts": [
                    {
                        "path": "evidence/supervisor-feedback.json",
                        "sha256": sha256_file(evidence_path),
                    }
                ]
            },
            sort_keys=True,
        )
        connection = open_director_registry(registry)
        try:
            for index in range(count):
                connection.execute(
                    "INSERT INTO research_lesson_feedback_drafts "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (
                        f"supervisor-feedback-{index}",
                        f"supervisor-run-{index}",
                        "supervisor-fixture",
                        f"supervisor-proposal-{index}",
                        "descriptive_profile_recorded",
                        "pending_human_review",
                        payload,
                        created_at,
                    ),
                )
            connection.commit()
        finally:
            connection.close()

    def _write_supervisor_advisory(
        self, repo: Path, review: dict, generated_at: str | None = None
    ) -> dict:
        packet = load_document(repo / review["packet_path"])
        recommendations = [
            {
                "review_key": item["review_key"],
                "review_type": item["review_type"],
                "target_id": item["target_id"],
                "recommended_decision": "approved",
                "confidence": "high",
                "disposition": "curate_standalone",
                "rationale": "local descriptive evidence supports manual curation review",
                "references": [item["evidence"][0]],
                "constraints": ["manual curation only"],
            }
            for item in packet["items"]
        ]
        advisory = {
            "schema_version": "knowledge-review-recommendations-v1",
            "advisory_id": (
                f"knowledge-review-advisory-{packet['packet_fingerprint'][:16]}"
            ),
            "generated_at": generated_at or packet["generated_at"],
            "packet_fingerprint": packet["packet_fingerprint"],
            "recommendations": recommendations,
            "summary": {
                "approved": len(recommendations),
                "rejected": 0,
                "total": len(recommendations),
            },
            "human_decision_required": True,
            "automatic_application_authorized": False,
            "execution_authorized": False,
        }
        advisory["advisory_fingerprint"] = (
            worker_supervisor.knowledge_batcher.knowledge.semantic_fingerprint(
                advisory, "advisory_fingerprint"
            )
        )
        path = repo / review["planned_advisory_path"]
        path.write_text(
            json.dumps(advisory, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return advisory

    def test_verified_completion_creates_one_hash_bound_review_only_draft(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry = repo / "director.db"
            claimed = self._claim_with_artifacts(repo, registry, proposal)
            with self.assertRaisesRegex(ValueError, "verified result recording"):
                worker_queue.finish_job(
                    registry, claimed["job_id"], "worker-feedback", "completed"
                )
            result = worker_queue.finish_descriptive_execution_job(
                repo,
                registry,
                claimed["job_id"],
                "worker-feedback",
                "descriptive_profile_recorded",
                updated_at="2026-07-20T12:20:02Z",
            )
            replay = worker_queue.finish_descriptive_execution_job(
                repo,
                registry,
                claimed["job_id"],
                "worker-feedback",
                "descriptive_profile_recorded",
                updated_at="2026-07-20T12:20:03Z",
            )
            drafts = lesson_feedback.pending_feedback_drafts(repo, registry)
            packet = knowledge_review.build_review_packet(
                ROOT,
                registry_exporter.export_registry(str(registry)),
                "2026-07-20T12:20:04Z",
            )
            connection = open_director_registry(registry)
            counts = {
                "results": connection.execute(
                    "SELECT COUNT(*) FROM research_descriptive_execution_results"
                ).fetchone()[0],
                "drafts": connection.execute(
                    "SELECT COUNT(*) FROM research_lesson_feedback_drafts"
                ).fetchone()[0],
                "formal_lessons": connection.execute(
                    "SELECT COUNT(*) FROM open_source_research_lessons"
                ).fetchone()[0],
            }
            connection.close()

        self.assertEqual(result["result_fingerprint"], replay["result_fingerprint"])
        self.assertEqual(counts, {"results": 1, "drafts": 1, "formal_lessons": 0})
        self.assertEqual(drafts[0]["source_kind"], "descriptive_execution")
        self.assertEqual(len(drafts[0]["evidence_artifacts"]), 2)
        self.assertFalse(drafts[0]["automatic_promotion_authorized"])
        self.assertEqual(packet["counts"]["lesson_feedback"], 1)
        self.assertEqual(packet["items"][0]["evidence"], sorted(proposal["required_artifacts"]))
        self.assertFalse(packet["items"][0]["automatic_application_authorized"])

    def test_invalid_attestation_or_contract_drift_leaves_no_result_or_draft(self):
        for failure in ("attestation", "contract"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                repo, proposal = self._feedback_repo(Path(temporary))
                registry = repo / "director.db"
                claimed = self._claim_with_artifacts(repo, registry, proposal)
                if failure == "attestation":
                    analysis_path = repo / proposal["required_artifacts"][0]
                    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
                    analysis["execution_scope"]["backtests"] = 1
                    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
                else:
                    contract_path = repo / worker_queue.FEEDBACK_CONTRACT_PATH
                    contract = json.loads(contract_path.read_text(encoding="utf-8"))
                    contract["knowledge_semantics"]["trusted_broker_lesson"] = True
                    contract_path.write_text(json.dumps(contract), encoding="utf-8")
                with self.assertRaises(ValueError):
                    worker_queue.finish_descriptive_execution_job(
                        repo,
                        registry,
                        claimed["job_id"],
                        "worker-feedback",
                        "descriptive_profile_recorded",
                    )
                connection = open_director_registry(registry)
                result_count = connection.execute(
                    "SELECT COUNT(*) FROM research_descriptive_execution_results"
                ).fetchone()[0]
                draft_count = connection.execute(
                    "SELECT COUNT(*) FROM research_lesson_feedback_drafts"
                ).fetchone()[0]
                job_status = connection.execute(
                    "SELECT status FROM research_worker_jobs WHERE job_id=?",
                    (claimed["job_id"],),
                ).fetchone()[0]
                connection.close()
                self.assertEqual((result_count, draft_count, job_status), (0, 0, "claimed"))

    def test_allowlisted_worker_executes_only_descriptive_stage_end_to_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            result = worker_supervisor.run_supervisor(
                repo, checked_at="2026-07-23T23:59:00Z"
            )
            analysis = load_document(repo / proposal["required_artifacts"][0])
            report = (repo / proposal["required_artifacts"][1]).read_text(encoding="utf-8")
            connection = open_director_registry(registry)
            descriptive_status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE job_id=?", (job["job_id"],)
            ).fetchone()[0]
            researcher_status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE run_id='unrelated-research-run'"
            ).fetchone()[0]
            result_count = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results"
            ).fetchone()[0]
            result_code = connection.execute(
                "SELECT result_code FROM research_descriptive_execution_results"
            ).fetchone()[0]
            feedback_count = connection.execute(
                "SELECT COUNT(*) FROM research_lesson_feedback_drafts"
            ).fetchone()[0]
            supervisor_status = connection.execute(
                "SELECT status FROM research_supervisor_runs"
            ).fetchone()[0]
            supervisor_event_count = connection.execute(
                "SELECT COUNT(*) FROM research_supervisor_run_events"
            ).fetchone()[0]
            supervisor_lock_count = connection.execute(
                "SELECT COUNT(*) FROM research_supervisor_locks"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["notification_required"])
        self.assertEqual(result["knowledge_review"]["status"], "idle")
        self.assertEqual(result["knowledge_review"]["pending_count"], 1)
        self.assertEqual(
            result["knowledge_review"]["count_threshold_remaining"], 4
        )
        self.assertEqual(result["knowledge_review"]["artifacts_written"], [])
        self.assertEqual(result_code, "descriptive_profile_recorded")
        self.assertEqual((descriptive_status, researcher_status), ("completed", "queued"))
        self.assertEqual((result_count, feedback_count), (1, 1))
        self.assertEqual(
            (supervisor_status, supervisor_event_count, supervisor_lock_count),
            ("completed", 2, 0),
        )
        self.assertEqual(result["run_ledger"]["status"], "completed")
        self.assertTrue(analysis["source_integrity"]["all_ok"])
        self.assertEqual(analysis["summary"]["window_count"], 5)
        self.assertEqual(analysis["summary"]["asset_count"], 2)
        self.assertIn(
            "full_window_mean_timeframe_rank_tau", analysis["summary"]
        )
        self.assertIn(
            "timeframe_coherence", analysis["results"]["windows"][0]
        )
        self.assertIn("1h—4h timeframe coherence", report)
        self.assertIn("Governance conclusion", report)
        self.assertEqual(
            analysis["handler"]["proposal_payload_fingerprint"], fingerprint(proposal)
        )

    def test_supervisor_config_drift_fails_before_claiming_worker_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            config_path = repo / worker_supervisor.DEFAULT_CONFIG
            config = load_document(config_path)
            config["max_jobs_per_run"] = 15
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "config fingerprint mismatch"):
                worker_supervisor.run_supervisor(repo)

            connection = open_director_registry(registry)
            status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE job_id=?", (job["job_id"],)
            ).fetchone()[0]
            result_count = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results"
            ).fetchone()[0]
            connection.close()
            self.assertEqual((status, result_count), ("queued", 0))
            self.assertFalse((repo / proposal["required_artifacts"][0]).exists())
            self.assertFalse((repo / proposal["required_artifacts"][1]).exists())

    def test_self_consistent_config_drift_requires_new_human_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            config_path = repo / worker_supervisor.DEFAULT_CONFIG
            config = load_document(config_path)
            config["max_jobs_per_run"] = 15
            config["config_fingerprint"] = worker_supervisor._semantic_fingerprint(
                config, "config_fingerprint"
            )
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "approval binding is invalid"):
                worker_supervisor.run_supervisor(repo)

            connection = open_director_registry(registry)
            status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE job_id=?", (job["job_id"],)
            ).fetchone()[0]
            connection.close()
            self.assertEqual(status, "queued")
            self.assertFalse((repo / proposal["required_artifacts"][0]).exists())

    def test_supervisor_approval_or_dependency_drift_fails_closed(self):
        for drift in (
            "approval",
            "policy",
            "advisor_prompt",
            "recovery_contract",
            "recovery_approval",
        ):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temporary:
                repo, proposal = self._feedback_repo(Path(temporary))
                registry, job = self._queued_worker_fixture(repo, proposal)
                if drift == "approval":
                    approval_path = repo / worker_supervisor.DEFAULT_APPROVAL
                    approval = load_document(approval_path)
                    approval["approved_config_sha256"] = "0" * 64
                    approval["approval_fingerprint"] = (
                        worker_supervisor._semantic_fingerprint(
                            approval, "approval_fingerprint"
                        )
                    )
                    approval_path.write_text(
                        json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    expected_error = "approval binding is invalid"
                elif drift == "policy":
                    dependency = repo / (
                        "research/director/knowledge-review-batch-policy-v1.json"
                    )
                    dependency.write_text(
                        dependency.read_text(encoding="utf-8") + "\n",
                        encoding="utf-8",
                    )
                    expected_error = "dependency hash mismatch"
                elif drift == "advisor_prompt":
                    dependency = repo / (
                        "research/knowledge/prompts/knowledge-review-advisor-v1.md"
                    )
                    dependency.write_text(
                        dependency.read_text(encoding="utf-8") + "\n",
                        encoding="utf-8",
                    )
                    expected_error = "dependency hash mismatch"
                elif drift == "recovery_contract":
                    dependency = repo / (
                        "research/governance/"
                        "descriptive-worker-failure-recovery-contract-v1.json"
                    )
                    dependency.write_text(
                        dependency.read_text(encoding="utf-8") + "\n",
                        encoding="utf-8",
                    )
                    expected_error = "dependency hash mismatch"
                else:
                    dependency = repo / (
                        "research/governance/approvals/"
                        "descriptive-worker-failure-recovery-v1-approval.json"
                    )
                    dependency.write_text(
                        dependency.read_text(encoding="utf-8") + "\n",
                        encoding="utf-8",
                    )
                    expected_error = "dependency hash mismatch"

                with self.assertRaisesRegex(ValueError, expected_error):
                    worker_supervisor.run_supervisor(repo)

                connection = open_director_registry(registry)
                status = connection.execute(
                    "SELECT status FROM research_worker_jobs WHERE job_id=?",
                    (job["job_id"],),
                ).fetchone()[0]
                result_count = connection.execute(
                    "SELECT COUNT(*) FROM research_descriptive_execution_results"
                ).fetchone()[0]
                connection.close()
                self.assertEqual((status, result_count), ("queued", 0))
                self.assertFalse((repo / proposal["required_artifacts"][0]).exists())

    def test_supervisor_lock_contention_skips_without_claiming_or_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            config, governance = worker_supervisor._config(
                repo, worker_supervisor.DEFAULT_CONFIG
            )
            holder = worker_supervisor.supervisor_ledger.acquire(
                registry,
                supervisor_id=config["supervisor_id"],
                lock_name=config["concurrency_control"]["lock_name"],
                lease_seconds=config["concurrency_control"]["lease_seconds"],
                governance_binding=governance,
                started_at="2026-07-21T00:00:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-lock-holder",
            )
            result = worker_supervisor.run_supervisor(
                repo,
                checked_at="2026-07-21T00:01:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-lock-contender",
            )
            connection = open_director_registry(registry)
            job_status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE job_id=?",
                (job["job_id"],),
            ).fetchone()[0]
            contender_status = connection.execute(
                "SELECT status FROM research_supervisor_runs "
                "WHERE supervisor_run_id='supervisor-run-lock-contender'"
            ).fetchone()[0]
            result_count = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results"
            ).fetchone()[0]
            connection.close()
            worker_supervisor.supervisor_ledger.fail(
                registry,
                holder,
                RuntimeError("test cleanup"),
                failed_at="2026-07-21T00:01:01Z",
            )

        self.assertEqual(result["status"], "skipped_lock_held")
        self.assertFalse(result["queue_checked"])
        self.assertFalse(result["notification_required"])
        self.assertEqual(result["knowledge_review"]["artifacts_written"], [])
        self.assertEqual((job_status, contender_status, result_count), ("queued", "skipped_lock_held", 0))
        self.assertFalse((repo / proposal["required_artifacts"][0]).exists())
        self.assertFalse((repo / proposal["required_artifacts"][1]).exists())

    def test_supervisor_auto_recovers_one_hash_approved_io_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            claimed = worker_queue.claim_next_job(
                registry,
                "io-failure-worker",
                stages={"descriptive_execution"},
                now="2026-07-21T00:00:00Z",
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                claimed["job_id"],
                "io-failure-worker",
                "descriptive_worker_io_failed",
                updated_at="2026-07-21T00:00:01Z",
            )

            result = worker_supervisor.run_supervisor(
                repo,
                checked_at="2026-07-23T23:59:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-io-recovery",
            )
            connection = open_director_registry(registry)
            job_row = connection.execute(
                "SELECT status,attempt_count FROM research_worker_jobs WHERE job_id=?",
                (job["job_id"],),
            ).fetchone()
            auto_retry_events = connection.execute(
                "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
                "AND event_type='descriptive_execution_auto_retry_authorized'",
                (job["run_id"],),
            ).fetchone()[0]
            connection.close()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["failure_recovery"]["status"], "auto_retry_queued")
        self.assertFalse(result["notification_required"])
        self.assertEqual(len(result["failure_recovery"]["automatic_retries_queued"]), 1)
        self.assertEqual((job_row["status"], job_row["attempt_count"]), ("completed", 2))
        self.assertEqual(auto_retry_events, 1)

    def test_supervisor_never_auto_retries_deterministic_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            claimed = worker_queue.claim_next_job(
                registry,
                "deterministic-failure-worker",
                stages={"descriptive_execution"},
                now="2026-07-21T00:00:00Z",
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                claimed["job_id"],
                "deterministic-failure-worker",
                "descriptive_worker_contract_or_input_failed",
                updated_at="2026-07-21T00:00:01Z",
            )

            result = worker_supervisor.run_supervisor(
                repo,
                checked_at="2026-07-21T00:01:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-deterministic-failure",
            )
            connection = open_director_registry(registry)
            job_row = connection.execute(
                "SELECT status,attempt_count FROM research_worker_jobs WHERE job_id=?",
                (job["job_id"],),
            ).fetchone()
            auto_retry_events = connection.execute(
                "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
                "AND event_type='descriptive_execution_auto_retry_authorized'",
                (job["run_id"],),
            ).fetchone()[0]
            connection.close()

        self.assertEqual(result["status"], "attention_required")
        self.assertTrue(result["notification_required"])
        self.assertEqual(
            result["failure_recovery"]["alerts"][0]["classification"],
            "deterministic_manual_review",
        )
        self.assertEqual((job_row["status"], job_row["attempt_count"]), ("failed", 1))
        self.assertEqual(auto_retry_events, 0)

    def test_supervisor_stops_after_one_automatic_io_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            first = worker_queue.claim_next_job(
                registry,
                "first-io-worker",
                stages={"descriptive_execution"},
                now="2026-07-21T00:00:00Z",
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                first["job_id"],
                "first-io-worker",
                "descriptive_worker_io_failed",
                updated_at="2026-07-21T00:00:01Z",
            )
            first_recovery = worker_supervisor.worker_recovery.reconcile_failures(
                repo,
                registry,
                checked_at="2026-07-21T00:01:00Z",
            )
            second = worker_queue.claim_next_job(
                registry,
                "second-io-worker",
                stages={"descriptive_execution"},
                now="2026-07-21T00:01:01Z",
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                second["job_id"],
                "second-io-worker",
                "descriptive_worker_io_failed",
                updated_at="2026-07-21T00:01:02Z",
            )

            result = worker_supervisor.run_supervisor(
                repo,
                checked_at="2026-07-21T00:02:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-io-exhausted",
            )
            connection = open_director_registry(registry)
            job_row = connection.execute(
                "SELECT status,attempt_count FROM research_worker_jobs WHERE job_id=?",
                (job["job_id"],),
            ).fetchone()
            auto_retry_events = connection.execute(
                "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
                "AND event_type='descriptive_execution_auto_retry_authorized'",
                (job["run_id"],),
            ).fetchone()[0]
            connection.close()

        self.assertEqual(first_recovery["status"], "auto_retry_queued")
        self.assertEqual(result["status"], "attention_required")
        self.assertTrue(result["notification_required"])
        self.assertEqual(
            result["failure_recovery"]["alerts"][0]["classification"],
            "automatic_retry_exhausted",
        )
        self.assertEqual((job_row["status"], job_row["attempt_count"]), ("failed", 2))
        self.assertEqual(auto_retry_events, 1)

    def test_supervisor_blocks_io_retry_when_job_binding_drifted(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            claimed = worker_queue.claim_next_job(
                registry,
                "binding-drift-worker",
                stages={"descriptive_execution"},
                now="2026-07-21T00:00:00Z",
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                claimed["job_id"],
                "binding-drift-worker",
                "descriptive_worker_io_failed",
                updated_at="2026-07-21T00:00:01Z",
            )
            task_path = repo / (
                "research/director/discovery-handoff/proposals/worker-fixture.json"
            )
            task = load_document(task_path)
            task["proposals"][0]["proposed_method"]["type"] = "drifted_handler"
            task_path.write_text(
                json.dumps(task, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )

            result = worker_supervisor.run_supervisor(
                repo,
                checked_at="2026-07-21T00:01:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-binding-drift",
            )
            connection = open_director_registry(registry)
            job_status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE job_id=?",
                (job["job_id"],),
            ).fetchone()[0]
            auto_retry_events = connection.execute(
                "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
                "AND event_type='descriptive_execution_auto_retry_authorized'",
                (job["run_id"],),
            ).fetchone()[0]
            connection.close()

        self.assertEqual(result["status"], "attention_required")
        self.assertTrue(result["notification_required"])
        self.assertEqual(
            result["failure_recovery"]["alerts"][0]["classification"],
            "recovery_binding_invalid",
        )
        self.assertEqual(
            result["failure_recovery"]["alerts"][0]["binding_error"],
            "proposal_payload_fingerprint_mismatch",
        )
        self.assertEqual((job_status, auto_retry_events), ("failed", 0))

    def test_recovery_ignores_failure_with_completed_higher_round_successor(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, failed_job = self._queued_worker_fixture(repo, proposal)
            claimed = worker_queue.claim_next_job(
                registry,
                "historical-failure-worker",
                stages={"descriptive_execution"},
                now="2026-07-21T00:00:00Z",
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                claimed["job_id"],
                "historical-failure-worker",
                "descriptive_worker_contract_or_input_failed",
                updated_at="2026-07-21T00:00:01Z",
            )
            payload = json.loads(failed_job["payload_json"])
            connection = open_director_registry(registry)
            successor = worker_queue.enqueue_worker_job(
                connection,
                run_id=failed_job["run_id"],
                stage="descriptive_execution",
                round_number=2,
                task_path=failed_job["task_path"],
                inbox_path=failed_job["inbox_path"],
                created_at="2026-07-21T00:00:02Z",
                authorization=payload["authorization"],
                proposal_id=payload["proposal_id"],
                proposal_payload_fingerprint=payload["proposal_payload_fingerprint"],
            )
            connection.execute(
                "UPDATE research_worker_jobs SET status='completed',updated_at=? "
                "WHERE job_id=?",
                ("2026-07-21T00:00:03Z", successor["job_id"]),
            )
            connection.commit()
            connection.close()

            recovery = worker_supervisor.worker_recovery.reconcile_failures(
                repo,
                registry,
                checked_at="2026-07-21T00:01:00Z",
            )

        self.assertEqual(recovery["status"], "idle")
        self.assertFalse(recovery["notification_required"])
        self.assertEqual(recovery["recovered_historical_failures_ignored"], 1)
        self.assertEqual(recovery["alerts"], [])

    def test_supervisor_publishes_one_count_triggered_review_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, _ = self._queued_worker_fixture(repo, proposal)
            self._seed_pending_feedback(
                repo, registry, 4, "2026-07-20T12:00:00Z"
            )
            first = worker_supervisor.run_supervisor(
                repo, checked_at="2026-07-20T12:31:00Z"
            )
            packet_path, handoff_path = [
                repo / path
                for path in first["knowledge_review"]["artifacts_written"]
            ]
            packet = load_document(packet_path)
            handoff = load_document(handoff_path)
            advisory = self._write_supervisor_advisory(
                repo, first["knowledge_review"]
            )
            advisory_anchor = datetime.fromisoformat(
                advisory["generated_at"].replace("Z", "+00:00")
            )
            replay = worker_supervisor.run_supervisor(
                repo, checked_at=(advisory_anchor + timedelta(hours=1)).isoformat()
            )
            connection = open_director_registry(registry)
            review_events = connection.execute(
                "SELECT COUNT(*) FROM research_knowledge_review_events"
            ).fetchone()[0]
            pending = connection.execute(
                "SELECT COUNT(*) FROM research_lesson_feedback_drafts "
                "WHERE review_status='pending_human_review'"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(first["status"], "advisory_required")
        self.assertFalse(first["notification_required"])
        self.assertEqual(
            first["knowledge_review"]["required_next_action"],
            "draft_validate_local_evidence_advisory_then_notify_once",
        )
        self.assertEqual(first["knowledge_review"]["trigger_reason"], "count_threshold")
        self.assertEqual(packet["counts"]["total"], 5)
        self.assertTrue(handoff["human_decision_required"])
        self.assertFalse(handoff["automatic_decision_authorized"])
        self.assertFalse(handoff["automatic_application_authorized"])
        self.assertFalse(handoff["automatic_lesson_promotion_authorized"])
        self.assertFalse(handoff["execution_authorized"])
        self.assertEqual(replay["status"], "idle")
        self.assertFalse(replay["notification_required"])
        self.assertEqual(
            replay["knowledge_review"]["status"], "awaiting_human_review"
        )
        self.assertEqual(
            replay["knowledge_review"]["advisory_fingerprint"],
            advisory["advisory_fingerprint"],
        )
        self.assertEqual(
            replay["knowledge_review"]["recommendation_summary"],
            {"approved": 5, "rejected": 0, "total": 5},
        )
        self.assertEqual(replay["knowledge_review"]["artifacts_written"], [])
        self.assertEqual((review_events, pending), (0, 5))

    def test_supervisor_publishes_age_trigger_without_worker_activity(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self._feedback_repo(Path(temporary))
            registry = repo / "research/registry/stage4a-director.db"
            self._seed_pending_feedback(
                repo, registry, 1, "2026-07-13T00:00:00Z"
            )
            result = worker_supervisor.run_supervisor(
                repo, checked_at="2026-07-20T00:00:00Z"
            )

        self.assertEqual(result["status"], "advisory_required")
        self.assertEqual(result["completed_jobs"], 0)
        self.assertFalse(result["notification_required"])
        self.assertEqual(
            result["knowledge_review"]["trigger_reason"], "max_wait_threshold"
        )
        self.assertEqual(len(result["knowledge_review"]["artifacts_written"]), 2)

    def test_supervisor_claims_one_review_reminder_and_stops_after_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self._feedback_repo(Path(temporary))
            registry = repo / "research/registry/stage4a-director.db"
            self._seed_pending_feedback(
                repo, registry, 5, "2026-07-20T00:00:00Z"
            )
            first = worker_supervisor.run_supervisor(
                repo,
                checked_at="2026-07-20T01:00:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-review-sla-first",
            )
            advisory = self._write_supervisor_advisory(
                repo, first["knowledge_review"]
            )
            advisory_anchor = datetime.fromisoformat(
                advisory["generated_at"].replace("Z", "+00:00")
            )
            reminder_at = advisory_anchor + timedelta(hours=72)
            while not 9 <= reminder_at.astimezone(ZoneInfo("Asia/Shanghai")).hour < 20:
                reminder_at += timedelta(hours=1)
            reminder = worker_supervisor.run_supervisor(
                repo,
                checked_at=reminder_at.isoformat(),
                trigger_source="test",
                invocation_id="supervisor-run-review-sla-reminder",
            )
            replay = worker_supervisor.run_supervisor(
                repo,
                checked_at=(reminder_at + timedelta(hours=1)).isoformat(),
                trigger_source="test",
                invocation_id="supervisor-run-review-sla-replay",
            )
            connection = open_director_registry(registry)
            connection.execute(
                "UPDATE research_lesson_feedback_drafts "
                "SET review_status='approved'"
            )
            connection.commit()
            connection.close()
            resolved = worker_supervisor.run_supervisor(
                repo,
                checked_at=(reminder_at + timedelta(hours=24)).isoformat(),
                trigger_source="test",
                invocation_id="supervisor-run-review-sla-resolved",
            )
            connection = open_director_registry(registry)
            sla_events = connection.execute(
                "SELECT COUNT(*) FROM research_review_sla_events"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(reminder["status"], "review_reminder_due")
        self.assertTrue(reminder["notification_required"])
        self.assertEqual(
            reminder["knowledge_review"]["review_sla"]["notification_level"],
            "reminder_72h",
        )
        self.assertEqual(replay["status"], "idle")
        self.assertFalse(replay["notification_required"])
        self.assertEqual(resolved["knowledge_review"]["status"], "idle")
        self.assertFalse(resolved["notification_required"])
        self.assertEqual(sla_events, 1)

    def test_supervisor_fails_closed_on_invalid_existing_advisory(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self._feedback_repo(Path(temporary))
            registry = repo / "research/registry/stage4a-director.db"
            self._seed_pending_feedback(
                repo, registry, 1, "2026-07-13T00:00:00Z"
            )
            first = worker_supervisor.run_supervisor(
                repo, checked_at="2026-07-20T00:00:00Z"
            )
            advisory_path = repo / first["knowledge_review"][
                "planned_advisory_path"
            ]
            advisory_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(jsonschema.ValidationError):
                worker_supervisor.run_supervisor(
                    repo, checked_at="2026-07-20T01:00:00Z"
                )

    def test_worker_rejects_tampered_proposal_and_records_failed_status_without_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            task_path = repo / "research/director/discovery-handoff/proposals/worker-fixture.json"
            task = json.loads(task_path.read_text(encoding="utf-8"))
            task["proposals"][0]["proposed_method"]["type"] = "unapproved_dynamic_handler"
            task_path.write_text(json.dumps(task, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "proposal binding mismatch"):
                descriptive_worker.run_once(repo, registry, "descriptive-worker-a")
            connection = open_director_registry(registry)
            status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE job_id=?", (job["job_id"],)
            ).fetchone()[0]
            results = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results"
            ).fetchone()[0]
            drafts = connection.execute(
                "SELECT COUNT(*) FROM research_lesson_feedback_drafts"
            ).fetchone()[0]
            failure_event = connection.execute(
                "SELECT reason_code FROM research_discovery_events "
                "WHERE run_id='descriptive-worker-run' AND event_type='descriptive_execution_failed'"
            ).fetchone()[0]
            connection.close()

        self.assertEqual((status, results, drafts), ("failed", 0, 0))
        self.assertEqual(failure_event, "descriptive_worker_contract_or_input_failed")
        self.assertFalse((repo / proposal["required_artifacts"][0]).exists())
        self.assertFalse((repo / proposal["required_artifacts"][1]).exists())

    def test_human_can_authorize_one_audited_retry_without_relaxing_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, job = self._queued_worker_fixture(repo, proposal)
            claimed = worker_queue.claim_next_job(
                registry,
                "failed-worker",
                stages={"descriptive_execution"},
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                claimed["job_id"],
                "failed-worker",
                "descriptive_worker_contract_or_input_failed",
            )
            event = worker_queue.retry_failed_descriptive_execution_job(
                repo,
                registry,
                job["job_id"],
                "human_user",
                "bounded_worker_fix_verified",
                "已核验处理器修复，授权原绑定任务仅重试一次。",
            )
            retried = worker_queue.claim_next_job(
                registry,
                "retry-worker",
                stages={"descriptive_execution"},
            )
            connection = open_director_registry(registry)
            retry_event_count = connection.execute(
                "SELECT COUNT(*) FROM research_discovery_events "
                "WHERE run_id=? AND event_type='descriptive_execution_retry_authorized'",
                (job["run_id"],),
            ).fetchone()[0]
            result_count = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(event["status"], "queued")
        self.assertEqual(event["maximum_total_attempts"], 2)
        self.assertEqual(retried["attempt_count"], 2)
        self.assertEqual((retry_event_count, result_count), (1, 0))
        self.assertFalse(event["candidate_created"])
        self.assertFalse(event["strategy_modified"])

    def test_exact_legacy_manifest_compatibility_authority_is_hash_bound(self):
        compatibility = descriptive_worker.load_legacy_manifest_compatibility(ROOT)

        self.assertEqual(
            set(compatibility),
            {
                "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml",
                "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml",
            },
        )
        self.assertEqual(
            compatibility[
                "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml"
            ]["manifest_sha256"],
            "e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13",
        )

    def test_exhausted_failed_job_gets_one_new_successor_and_is_not_revived(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, proposal = self._feedback_repo(Path(temporary))
            registry, failed_job = self._queued_worker_fixture(repo, proposal)
            first = worker_queue.claim_next_job(
                registry, "first-worker", stages={"descriptive_execution"}
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                first["job_id"],
                "first-worker",
                "descriptive_worker_contract_or_input_failed",
            )
            worker_queue.retry_failed_descriptive_execution_job(
                repo,
                registry,
                failed_job["job_id"],
                "human_user",
                "bounded_worker_fix_verified",
                "授权一次原任务重试。",
            )
            second = worker_queue.claim_next_job(
                registry, "second-worker", stages={"descriptive_execution"}
            )
            worker_queue.fail_descriptive_execution_job(
                registry,
                second["job_id"],
                "second-worker",
                "descriptive_worker_contract_or_input_failed",
            )
            event = worker_queue.enqueue_successor_descriptive_execution_job(
                repo,
                registry,
                failed_job["job_id"],
                "human_user",
                "exact_legacy_manifest_compatibility_approved",
                "批准精确旧 manifest 兼容规则并创建新任务。",
            )
            connection = open_director_registry(registry)
            old = connection.execute(
                "SELECT status,attempt_count FROM research_worker_jobs WHERE job_id=?",
                (failed_job["job_id"],),
            ).fetchone()
            successor = connection.execute(
                "SELECT status,round_number,attempt_count FROM research_worker_jobs WHERE job_id=?",
                (event["successor_job_id"],),
            ).fetchone()
            connection.close()

        self.assertEqual(tuple(old), ("failed", 2))
        self.assertEqual(tuple(successor), ("queued", 2, 0))
        self.assertFalse(event["failed_job_revived"])


if __name__ == "__main__":
    unittest.main()
