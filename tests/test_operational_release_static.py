import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OperationalReleaseStaticTest(unittest.TestCase):
    def test_installer_is_dry_run_only_and_has_rollback(self):
        content = (ROOT / "deploy/install_dry_run_release.sh").read_text(encoding="utf-8")
        self.assertIn("dry_run_only", content)
        self.assertIn("rollback", content)
        self.assertIn("runtime-deployment-manifest.json", content)
        self.assertIn("dashboard smoke check failed", content)
        self.assertIn("BOT_V1130_SHADOW_DB_FILE=", content)
        self.assertIn("freqtrade-data-reliability.service", content)
        self.assertIn("freqtrade-data-reliability.timer", content)
        self.assertIn("systemctl enable --now", content)
        self.assertIn("SYSTEMD_BACKUP", content)
        self.assertLess(content.index("TRADE_MONITOR_STATE_FILE="), content.index("cat \"$cron_next\""))
        self.assertNotIn("live.sqlite", content)

    def test_reliability_timer_is_bounded_and_does_not_manage_bots(self):
        service = (ROOT / "deploy/freqtrade-data-reliability.service").read_text(encoding="utf-8")
        timer = (ROOT / "deploy/freqtrade-data-reliability.timer").read_text(encoding="utf-8")
        self.assertIn("data_reliability_controller.py --repair", service)
        self.assertIn("OnUnitActiveSec=5min", timer)
        self.assertIn("Persistent=true", timer)
        self.assertNotIn("docker", service.lower())

    def test_release_workflow_deploys_only_from_master_after_gate(self):
        content = (ROOT / ".github/workflows/operational-release.yml").read_text(encoding="utf-8")
        self.assertIn("needs: quality-gate", content)
        self.assertIn("refs/heads/master", content)
        self.assertIn("cloud-dry-run", content)
        self.assertIn("tar -xOf", content)
        self.assertIn("/tmp/install_dry_run_release.sh", content)
        self.assertNotIn("workflow_run", content)


if __name__ == "__main__":
    unittest.main()
