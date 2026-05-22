from datetime import datetime, timedelta
from strategies.risk_manager import RiskManager


def test_initial_state():
    rm = RiskManager()
    assert not rm.is_circuit_breaker_active()
    assert rm.get_cooldown_remaining() is None


def test_circuit_breaker_activates_after_losses():
    rm = RiskManager(max_consecutive_losses=3)
    now = datetime.now()

    rm.record_trade_result(-0.01, now)
    assert not rm.is_circuit_breaker_active()

    rm.record_trade_result(-0.02, now)
    assert not rm.is_circuit_breaker_active()

    rm.record_trade_result(-0.03, now)
    assert rm.is_circuit_breaker_active()


def test_win_resets_loss_streak():
    rm = RiskManager(max_consecutive_losses=3)
    now = datetime.now()

    rm.record_trade_result(-0.01, now)
    rm.record_trade_result(-0.02, now)
    rm.record_trade_result(0.05, now)  # Win resets streak
    rm.record_trade_result(-0.01, now)
    assert not rm.is_circuit_breaker_active()


def test_stake_calculation():
    rm = RiskManager(max_positions=2, stake_pct_low=0.15, stake_pct_high=0.25)

    # 0 positions: can trade
    stake = rm.calculate_stake_amount(10000, 0)
    assert stake == 2000  # (15%+25%)/2 = 20% of 10000

    # 1 position: can still trade
    stake = rm.calculate_stake_amount(10000, 1)
    assert stake == 2000

    # 2 positions: at max, no more entries
    stake = rm.calculate_stake_amount(10000, 2)
    assert stake == 0


def test_hard_stop():
    rm = RiskManager(hard_stop_pct=-0.07)
    assert rm.is_hard_stop_triggered(-0.08)
    assert not rm.is_hard_stop_triggered(-0.05)
    assert not rm.is_hard_stop_triggered(0.01)


def test_reset():
    rm = RiskManager(max_consecutive_losses=3)
    now = datetime.now()
    rm.record_trade_result(-0.01, now)
    rm.record_trade_result(-0.02, now)
    rm.record_trade_result(-0.03, now)
    assert rm.is_circuit_breaker_active()

    rm.reset()
    assert not rm.is_circuit_breaker_active()
