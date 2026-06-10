import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "format_trade_alert.py"


class FormatTradeAlertTest(unittest.TestCase):
    def test_new_open_message_is_human_readable_and_deduplicated(self):
        event = {
            "type": "new_open",
            "label": "V6.2",
            "open": 1,
            "total": 1,
            "closed": 0,
            "profit_all_coin": "1.20611885",
            "latest_trade_date": "2026-06-09 12:41:15",
            "trade": {
                "pair": "BTC/USDT:USDT",
                "is_short": True,
                "enter_tag": "trending_short",
                "open_rate": "62517.5",
                "current_rate": "62402.6",
                "stake_amount": "1437.9025",
                "profit_abs": "1.20611885",
            },
        }

        message = self.run_formatter(event)

        self.assertIn("[V6.2] 新开仓", message)
        self.assertIn("方向：做空 BTC/USDT:USDT", message)
        self.assertIn("信号：趋势做空", message)
        self.assertIn("开仓价：62,517.50", message)
        self.assertIn("现价：62,402.60", message)
        self.assertIn("投入：1,437.90 USDT", message)
        self.assertIn("浮盈：+1.21 USDT", message)
        self.assertIn("统计：持仓 1 / 累计 1 / 已平 0", message)
        self.assertNotIn("signal=", message)
        self.assertNotIn("profit_all_coin=", message)

    def test_closed_message_states_whether_realized_trade_profit_won_or_lost(self):
        event = {
            "type": "closed",
            "label": "V6.5",
            "closed_delta": 1,
            "open": 0,
            "total": 2,
            "closed": 2,
            "profit_all_coin": "31.23",
            "closed_profit_delta": "8.71",
            "latest_trade_date": "2026-06-10 15:00:08",
        }

        message = self.run_formatter(event)

        self.assertIn("本次盈利：+8.71 USDT", message)
        self.assertIn("累计收益：+31.23 USDT", message)

    def test_closed_message_states_whether_realized_trade_loss_lost(self):
        event = {
            "type": "closed",
            "label": "V6.5",
            "closed_delta": 1,
            "open": 0,
            "total": 3,
            "closed": 3,
            "profit_all_coin": "24.20",
            "closed_profit_delta": "-7.03",
            "latest_trade_date": "2026-06-10 16:15:02",
        }

        message = self.run_formatter(event)

        self.assertIn("本次亏损：-7.03 USDT", message)
        self.assertIn("累计收益：+24.20 USDT", message)

    def run_formatter(self, event):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout


if __name__ == "__main__":
    unittest.main()
