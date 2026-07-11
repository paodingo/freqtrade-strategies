import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_control import (  # noqa: E402
    CampaignError,
    ResearchStore,
    execute_dry_run,
    load_campaign,
    run_orchestrator,
    seed_demo_campaign,
    validate_campaign_config,
)
from research_guard import PathGuardError, check_path  # noqa: E402


def base_config(**overrides):
    config = {
        "campaign_id": "unit-campaign",
        "mode": "dry_run",
        "scope": {
            "allowed_paths": ["research/**", "reports/audits/**", "scripts/research_*.py"],
            "blocked_paths": [
                ".env",
                "secrets/**",
                "deploy/**",
                "user_data/config_live.json",
                "configs/production/**",
                "scripts/start_bot.sh",
                "scripts/refresh_data.sh",
            ],
        },
        "budget": {
            "max_experiments": 20,
            "max_total_attempts": 20,
            "max_consecutive_failures": 3,
            "max_retries_per_experiment": 1,
            "max_wall_clock_minutes": 60,
        },
        "autonomy": {
            "automatically_claim_next": True,
            "automatically_generate_hypotheses": False,
            "automatically_promote_champion": False,
            "access_sealed_holdout": False,
            "lease_seconds": 1,
        },
        "stop_conditions": ["queue_empty", "budget_exhausted"],
        "escalation_conditions": ["blocked_path"],
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config


class ResearchControlPlaneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="research-control-test-"))
        (self.tmp / "research" / "campaigns" / "active").mkdir(parents=True)
        self.campaign_path = self.tmp / "research" / "campaigns" / "active" / "unit.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_campaign(self, config):
        text = json.dumps(config, indent=2)
        self.campaign_path.write_text(text, encoding="utf-8")
        return self.campaign_path

    def make_store(self, config=None):
        config = config or base_config()
        store = ResearchStore(self.tmp)
        store.init_schema()
        store.begin()
        store.upsert_campaign(config, self.write_campaign(config), owner="test")
        store.commit()
        return store

    def add_experiment(self, store, fingerprint, payload=None, priority=1):
        payload = payload or {"simulated_outcome": "success", "artifact_path": f"research/artifacts/{fingerprint}.txt"}
        store.begin()
        result = store.add_hypothesis("unit-campaign", fingerprint, fingerprint, payload, priority)
        store.commit()
        self.assertIsNotNone(result)

    def test_campaign_yaml_validation(self):
        path = self.write_campaign(base_config())
        self.assertEqual(load_campaign(path)["campaign_id"], "unit-campaign")
        bad = base_config(mode="live")
        with self.assertRaises(ValueError):
            validate_campaign_config(bad)

    def test_legal_and_illegal_state_transitions(self):
        store = self.make_store()
        self.add_experiment(store, "state")
        store.begin()
        row = store.claim_next("unit-campaign", "owner-a", 60)
        store.transition_experiment(row["experiment_id"], "preparing", "ok")
        with self.assertRaises(CampaignError):
            store.transition_experiment(row["experiment_id"], "accepted", "illegal")
        store.rollback()
        store.close()

    def test_atomic_claim(self):
        store = self.make_store()
        self.add_experiment(store, "atomic")
        store.begin()
        first = store.claim_next("unit-campaign", "owner-a", 60)
        second = store.claim_next("unit-campaign", "owner-b", 60)
        store.commit()
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        store.close()

    def test_two_owners_cannot_claim_same_experiment(self):
        store = self.make_store()
        self.add_experiment(store, "only-one")
        store.begin()
        first = store.claim_next("unit-campaign", "owner-a", 60)
        store.commit()
        store.begin()
        second = store.claim_next("unit-campaign", "owner-b", 60)
        store.commit()
        self.assertEqual(first["experiment_id"], 1)
        self.assertIsNone(second)
        store.close()

    def test_lease_expiry_reclaim(self):
        store = self.make_store()
        self.add_experiment(store, "lease")
        store.begin()
        store.claim_next("unit-campaign", "owner-a", -1)
        reclaimed = store.reclaim_expired_leases("unit-campaign")
        status = store.conn.execute("SELECT status FROM experiments WHERE fingerprint='lease'").fetchone()[0]
        store.commit()
        self.assertEqual(reclaimed, 1)
        self.assertEqual(status, "queued")
        store.close()

    def test_restart_after_recovery(self):
        store = self.make_store()
        self.add_experiment(store, "restart")
        store.begin()
        store.claim_next("unit-campaign", "owner-a", -1)
        store.commit()
        store.close()

        store2 = ResearchStore(self.tmp)
        store2.init_schema()
        store2.begin()
        store2.reclaim_expired_leases("unit-campaign")
        claimed = store2.claim_next("unit-campaign", "owner-b", 60)
        store2.commit()
        self.assertEqual(claimed["fingerprint"], "restart")
        store2.close()

    def test_fingerprint_dedup(self):
        store = self.make_store()
        store.begin()
        first = store.add_hypothesis("unit-campaign", "dup", "dup", {"simulated_outcome": "success"})
        second = store.add_hypothesis("unit-campaign", "dup", "dup again", {"simulated_outcome": "success"})
        store.commit()
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        count = store.conn.execute("SELECT COUNT(*) FROM hypotheses WHERE fingerprint='dup'").fetchone()[0]
        self.assertEqual(count, 1)
        store.close()

    def test_single_experiment_retry_limit(self):
        config = base_config()
        path = self.write_campaign(config)
        store = ResearchStore(self.tmp)
        store.init_schema()
        store.begin()
        store.upsert_campaign(config, path, owner="test")
        store.add_hypothesis(
            "unit-campaign",
            "retry",
            "retry",
            {"simulated_outcome": "retryable_failure", "artifact_path": "research/artifacts/retry.txt"},
            1,
        )
        store.commit()
        store.close()

        run_orchestrator(self.tmp, path, owner="runner", max_steps=3)
        store = ResearchStore(self.tmp)
        status = store.conn.execute("SELECT status, retry_count FROM experiments WHERE fingerprint='retry'").fetchone()
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["retry_count"], 1)
        store.close()

    def test_campaign_total_budget_stop(self):
        config = base_config(budget={**base_config()["budget"], "max_total_attempts": 2})
        path = self.write_campaign(config)
        store = self.make_store(config)
        for index in range(3):
            self.add_experiment(store, f"budget-{index}", priority=index)
        store.close()
        report = run_orchestrator(self.tmp, path, owner="runner")
        self.assertEqual(report["campaign"]["status"], "stopped")
        self.assertEqual(report["campaign"]["last_stop_reason"], "max_total_attempts reached")
        self.assertEqual(report["campaign"]["completion_quality"], "partial")
        self.assertEqual(report["campaign"]["remaining_experiments"], 1)
        self.assertEqual(report["budget"]["attempts"], 2)

    def test_consecutive_failure_stop(self):
        config = base_config(budget={**base_config()["budget"], "max_consecutive_failures": 1})
        path = self.write_campaign(config)
        store = self.make_store(config)
        self.add_experiment(
            store,
            "permanent",
            {"simulated_outcome": "permanent_failure", "artifact_path": "research/artifacts/permanent.txt"},
        )
        store.close()
        report = run_orchestrator(self.tmp, path, owner="runner")
        self.assertEqual(report["campaign"]["last_stop_reason"], "max_consecutive_failures reached")

    def test_wall_clock_stop(self):
        config = base_config(budget={**base_config()["budget"], "max_wall_clock_minutes": 0})
        path = self.write_campaign(config)
        store = self.make_store(config)
        self.add_experiment(store, "clock")
        store.close()
        report = run_orchestrator(self.tmp, path, owner="runner")
        self.assertEqual(report["campaign"]["last_stop_reason"], "max_wall_clock_minutes reached")

    def test_blocked_path_priority(self):
        config = base_config(scope={"allowed_paths": ["scripts/**"], "blocked_paths": ["scripts/start_bot.sh"]})
        with self.assertRaises(PathGuardError):
            check_path(self.tmp, config, "scripts/start_bot.sh")

    def test_parent_directory_bypass_blocked(self):
        config = base_config()
        with self.assertRaises(PathGuardError):
            check_path(self.tmp, config, "../outside.txt")

    def test_repeated_execution_does_not_duplicate_charge_or_completion(self):
        config = base_config()
        path = self.write_campaign(config)
        store = self.make_store(config)
        self.add_experiment(store, "once")
        store.close()
        run_orchestrator(self.tmp, path, owner="runner")
        run_orchestrator(self.tmp, path, owner="runner")
        store = ResearchStore(self.tmp)
        attempts = store.conn.execute("SELECT COUNT(*) FROM budget_events WHERE event_type='attempt_started'").fetchone()[0]
        accepted = store.conn.execute("SELECT COUNT(*) FROM experiments WHERE status='accepted'").fetchone()[0]
        self.assertEqual(attempts, 1)
        self.assertEqual(accepted, 1)
        store.close()

    def test_dry_run_continuously_executes_ten_experiments(self):
        config = base_config(budget={**base_config()["budget"], "max_experiments": 10, "max_total_attempts": 10})
        path = self.write_campaign(config)
        store = self.make_store(config)
        for index in range(10):
            self.add_experiment(store, f"continuous-{index:02d}", priority=index)
        store.close()
        report = run_orchestrator(self.tmp, path, owner="runner")
        self.assertEqual(report["counts"].get("accepted"), 10)
        self.assertEqual(report["campaign"]["status"], "completed")

    def test_guard_violation_escalates_campaign(self):
        config = base_config()
        path = self.write_campaign(config)
        store = self.make_store(config)
        self.add_experiment(
            store,
            "guard",
            {"simulated_outcome": "success", "guard_paths": ["scripts/start_bot.sh"]},
        )
        store.close()
        report = run_orchestrator(self.tmp, path, owner="runner")
        self.assertEqual(report["campaign"]["status"], "escalated")
        self.assertEqual(report["counts"].get("escalated"), 1)


if __name__ == "__main__":
    unittest.main()
