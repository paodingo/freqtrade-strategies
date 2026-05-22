"""Risk management: circuit breaker, position sizing, hard stop checks."""
from datetime import datetime, timedelta
from typing import Optional


class RiskManager:
    def __init__(
        self,
        max_consecutive_losses: int = 3,
        cooldown_hours: int = 24,
        hard_stop_pct: float = -0.07,
        max_positions: int = 2,
        stake_pct_low: float = 0.15,
        stake_pct_high: float = 0.25,
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_hours = cooldown_hours
        self.hard_stop_pct = hard_stop_pct
        self.max_positions = max_positions
        self.stake_pct_low = stake_pct_low
        self.stake_pct_high = stake_pct_high
        self._cooldown_until: Optional[datetime] = None
        self._loss_streak: int = 0

    def is_circuit_breaker_active(self) -> bool:
        """Check if trading is currently halted by circuit breaker."""
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            return True
        return False

    def record_trade_result(self, profit_ratio: float, close_time: datetime):
        """Update loss streak tracking after a trade closes."""
        if profit_ratio < 0:
            self._loss_streak += 1
        else:
            self._loss_streak = 0

        if self._loss_streak >= self.max_consecutive_losses:
            self._cooldown_until = datetime.now() + timedelta(
                hours=self.cooldown_hours
            )
            self._loss_streak = 0

    def get_cooldown_remaining(self) -> Optional[timedelta]:
        """Time remaining in cooldown, or None if not in cooldown."""
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            return self._cooldown_until - datetime.now()
        return None

    def calculate_stake_amount(
        self, total_capital: float, current_positions: int
    ) -> float:
        """Determine stake amount for next trade."""
        if current_positions >= self.max_positions:
            return 0.0
        stake_pct = (self.stake_pct_low + self.stake_pct_high) / 2
        return total_capital * stake_pct

    def is_hard_stop_triggered(self, trade_profit_pct: float) -> bool:
        return trade_profit_pct < self.hard_stop_pct

    def reset(self) -> None:
        self._cooldown_until = None
        self._loss_streak = 0
