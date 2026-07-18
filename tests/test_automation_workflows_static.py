import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AutomationWorkflowsStaticTest(unittest.TestCase):
    def test_exploration_is_scheduled_bounded_and_cannot_self_promote(self):
        content = (ROOT / ".github/workflows/research-exploration.yml").read_text(encoding="utf-8")
        self.assertIn("schedule:", content)
        self.assertIn("research_director.py", content)
        self.assertIn('"max_validation_accesses":0', content)
        self.assertIn('execution_authorized"] is False', content)

    def test_test_and_deploy_gate_are_connected(self):
        content = (ROOT / ".github/workflows/operational-release.yml").read_text(encoding="utf-8")
        self.assertIn("needs: quality-gate", content)
        self.assertIn("npm run verify", content)
        self.assertIn("tests.test_check_trades", content)
        self.assertIn("Freqtrade strategy import smoke", content)


if __name__ == "__main__":
    unittest.main()
