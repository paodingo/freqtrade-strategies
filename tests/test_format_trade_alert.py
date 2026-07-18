import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "format_trade_alert.py"


class FormatTradeAlertTest(unittest.TestCase):
    def run_formatter(self, event):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout

    def test_new_open_includes_pair_direction_and_entry_reason(self):
        message = self.run_formatter({
            "type": "new_open",
            "label": "V11.29 current",
            "open": 1,
            "total": 3,
            "closed": 2,
            "trade": {
                "pair": "BTC/USDT:USDT",
                "is_short": True,
                "enter_tag": "v102_trending_short_core",
                "open_rate": "62517.5",
                "stake_amount": "250",
                "leverage": "3",
                "open_date": "2026-07-18 12:41:15",
            },
        })

        self.assertIn("[V11.29 current] 新开仓", message)
        self.assertIn("交易：做空 BTC/USDT:USDT", message)
        self.assertIn("入场理由：趋势空单核心信号（v102_trending_short_core）", message)
        self.assertIn("开仓价：62,517.50", message)
        self.assertIn("统计：持仓 1 / 累计 3 / 已平 2", message)

    def test_closed_includes_exact_exit_reason_and_realized_result(self):
        message = self.run_formatter({
            "type": "closed",
            "label": "V11.30 crash-rebound shadow",
            "open": 0,
            "total": 8,
            "closed": 8,
            "trade": {
                "pair": "ETH/USDT:USDT",
                "is_short": False,
                "enter_tag": "v1130_crash_rebound_long",
                "exit_reason": "v1130_rebound_time_exit",
                "open_rate": "3100",
                "close_rate": "3131",
                "profit_abs": "8.71",
                "profit_ratio": "0.01",
                "trade_duration": 120,
                "close_date": "2026-07-18 15:00:08",
            },
        })

        self.assertIn("入场理由：V11.30 暴跌反弹做多（v1130_crash_rebound_long）", message)
        self.assertIn("退出理由：V11.30 反弹持仓超时退出（v1130_rebound_time_exit）", message)
        self.assertIn("实际盈亏：+8.71 USDT（+1.00%）", message)


if __name__ == "__main__":
    unittest.main()
