import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "harness" / "release-checkpoint-v1.json"
SCHEMA_PATH = ROOT / "harness" / "release-checkpoint-v1.schema.json"


class ReleaseCheckpointContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_contract_identity_and_closed_shape(self):
        self.assertEqual(
            self.policy["schema_version"],
            "harness-release-checkpoint-v1",
        )
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(
            set(self.schema["required"]),
            set(self.policy),
        )

    def test_completed_tested_module_must_publish_without_accumulation(self):
        self.assertEqual(
            self.policy["trigger"],
            {"module_complete": True, "required_tests_passed": True},
        )
        self.assertEqual(
            self.policy["required_actions"],
            [
                "freeze_exact_scope",
                "create_logical_commit",
                "push_feature_branch",
                "open_draft_pull_request",
            ],
        )
        self.assertEqual(
            self.policy["accumulation_policy"]["max_completed_unpushed_modules"],
            0,
        )

    def test_deployment_remains_a_separate_evidence_gate(self):
        gate = self.policy["deployment_gate"]
        self.assertTrue(gate["separate_from_publish"])
        self.assertFalse(gate["automatic"])
        self.assertEqual(
            set(gate["required_evidence"]),
            {
                "target_health",
                "exact_deploy_scope",
                "rollback_point",
                "post_deploy_smoke",
            },
        )

    def test_blocked_publish_is_evidenced_and_not_complete(self):
        blocked = self.policy["blocked_release"]
        self.assertTrue(blocked["requires_evidence"])
        self.assertFalse(blocked["counts_as_complete"])


if __name__ == "__main__":
    unittest.main()
