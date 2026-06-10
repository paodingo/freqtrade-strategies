import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notify_trades.sh"


class NotifyTradesScriptTest(unittest.TestCase):
    def test_trade_notifications_can_fan_out_through_openclaw_channels(self):
        content = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("OPENCLAW_NOTIFY_TARGETS", content)
        self.assertIn("send_openclaw_targets", content)
        self.assertIn("openclaw message send", content)
        self.assertIn("OPENCLAW_TIMEOUT_SECONDS", content)
        self.assertIn("--channel", content)
        self.assertIn("--account", content)
        self.assertIn("--target", content)
        self.assertIn("--delivery", content)
        self.assertIn("openclaw-weixin:account:target", content)


if __name__ == "__main__":
    unittest.main()
