import unittest
from datetime import datetime

from strategies.risk_manager import RiskManager


class RiskManagerTest(unittest.TestCase):
    def test_initial_state(self):
        rm = RiskManager()
        now = datetime.now()
        self.assertFalse(rm.is_circuit_breaker_active(now))
        self.assertIsNone(rm.get_cooldown_remaining(now))

    def test_circuit_breaker_activates_after_losses(self):
        rm = RiskManager(max_consecutive_losses=3)
        now = datetime.now()

        rm.record_trade_result(-0.01, now)
        self.assertFalse(rm.is_circuit_breaker_active(now))

        rm.record_trade_result(-0.02, now)
        self.assertFalse(rm.is_circuit_breaker_active(now))

        rm.record_trade_result(-0.03, now)
        self.assertTrue(rm.is_circuit_breaker_active(now))

    def test_win_resets_loss_streak(self):
        rm = RiskManager(max_consecutive_losses=3)
        now = datetime.now()

        rm.record_trade_result(-0.01, now)
        rm.record_trade_result(-0.02, now)
        rm.record_trade_result(0.05, now)
        rm.record_trade_result(-0.01, now)
        self.assertFalse(rm.is_circuit_breaker_active(now))

    def test_stake_calculation(self):
        rm = RiskManager(max_positions=2, stake_pct_low=0.15, stake_pct_high=0.25)

        self.assertEqual(rm.calculate_stake_amount(10000, 0), 2000)
        self.assertEqual(rm.calculate_stake_amount(10000, 1), 2000)
        self.assertEqual(rm.calculate_stake_amount(10000, 2), 0)

    def test_hard_stop(self):
        rm = RiskManager(hard_stop_pct=-0.07)
        self.assertTrue(rm.is_hard_stop_triggered(-0.08))
        self.assertFalse(rm.is_hard_stop_triggered(-0.05))
        self.assertFalse(rm.is_hard_stop_triggered(0.01))

    def test_reset(self):
        rm = RiskManager(max_consecutive_losses=3)
        now = datetime.now()
        rm.record_trade_result(-0.01, now)
        rm.record_trade_result(-0.02, now)
        rm.record_trade_result(-0.03, now)
        self.assertTrue(rm.is_circuit_breaker_active(now))

        rm.reset()
        self.assertFalse(rm.is_circuit_breaker_active(now))


if __name__ == "__main__":
    unittest.main()
