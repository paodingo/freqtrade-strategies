"""RegimeAware V6.3 - V6.2 with account-risk-budgeted scale-ins."""
from datetime import datetime
import math

from freqtrade.persistence import Trade

from RegimeAwareV62 import RegimeAwareV62


class RegimeAwareV63(RegimeAwareV62):
    """V6.3 keeps V6.2 signals but sizes scale-ins by max account loss."""

    max_scale_in_account_loss_pct = 0.015
    max_scale_in_atr_pct = 0.03
    scale_in_tag_prefix = "v63"

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None | tuple[float | None, str | None]:
        current_stake = float(getattr(trade, "stake_amount", 0) or 0)
        if current_stake < self.old_position_stake_floor:
            return None

        successful_entries = int(getattr(trade, "nr_of_successful_entries", 1) or 1)
        if successful_entries >= self.max_entry_position_adjustment + 1:
            return None

        required_profit = self.min_scale_in_profit * successful_entries
        if current_profit < required_profit:
            return None

        if self._recent_entry_too_close(trade, current_time):
            return None

        stoploss_distance = self._stoploss_distance(trade, current_rate)
        if stoploss_distance is not None and stoploss_distance < self.min_scale_in_stoploss_buffer:
            return None

        if self._safety_price_too_close(
            getattr(trade, "liquidation_price", None),
            current_rate,
            self.min_scale_in_liquidation_buffer,
        ):
            return None

        last_candle = self._last_analyzed_candle(trade)
        if last_candle is None:
            return None

        if not self._same_direction_signal_active_from_candle(trade, last_candle):
            return None

        if self._volatility_too_high(last_candle, current_rate):
            return None

        stake = self._risk_limited_scale_in_stake(
            current_stake=current_stake,
            stoploss_distance=stoploss_distance,
            max_stake=max_stake,
        )
        if min_stake is not None and stake < min_stake:
            return None
        if stake <= 0:
            return None

        return stake, f"{self.scale_in_tag_prefix}_scale_in_{successful_entries}"

    def _last_analyzed_candle(self, trade: Trade):
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe.empty:
            return None
        return dataframe.iloc[-1]

    @staticmethod
    def _same_direction_signal_active_from_candle(trade: Trade, last) -> bool:
        if getattr(trade, "is_short", False):
            return bool(last.get("enter_short", 0) == 1)
        return bool(last.get("enter_long", 0) == 1)

    def _risk_limited_scale_in_stake(
        self,
        *,
        current_stake: float,
        stoploss_distance: float | None,
        max_stake: float,
    ) -> float:
        distance = stoploss_distance if stoploss_distance and stoploss_distance > 0 else abs(float(self.stoploss))
        if distance <= 0:
            return 0.0

        total_balance, available_balance = self._stake_balances(current_stake, max_stake)
        max_account_loss = total_balance * self.max_scale_in_account_loss_pct
        current_loss_at_stop = current_stake * distance
        remaining_loss_budget = max_account_loss - current_loss_at_stop
        if remaining_loss_budget <= 0:
            return 0.0

        risk_limited_stake = remaining_loss_budget / distance
        remaining_position_budget = self.max_total_stake_amount - current_stake
        stake = min(
            self.add_stake_amount,
            remaining_position_budget,
            max_stake,
            available_balance,
            risk_limited_stake,
        )
        return max(0.0, stake)

    def _stake_balances(self, current_stake: float, max_stake: float) -> tuple[float, float]:
        wallet_total = self._wallet_value("get_total_stake_amount")
        wallet_available = self._wallet_value("get_available_stake_amount")

        configured_total = self.config.get("dry_run_wallet") if isinstance(getattr(self, "config", None), dict) else None
        total_balance = self._first_positive(wallet_total, configured_total, current_stake + max_stake, self.max_total_stake_amount)
        available_balance = self._first_positive(wallet_available, max_stake, 0.0)
        return total_balance, available_balance

    def _wallet_value(self, method_name: str) -> float | None:
        wallets = getattr(self, "wallets", None)
        method = getattr(wallets, method_name, None)
        if not callable(method):
            return None
        try:
            return self._finite_positive(method())
        except Exception:
            return None

    @staticmethod
    def _finite_positive(value: float | None) -> float | None:
        if value is None:
            return None
        number = float(value)
        if math.isfinite(number) and number > 0:
            return number
        return None

    def _first_positive(self, *values: float | None) -> float:
        for value in values:
            finite = self._finite_positive(value)
            if finite is not None:
                return finite
        return 0.0

    def _stoploss_distance(self, trade: Trade, current_rate: float) -> float | None:
        stop_loss_abs = getattr(trade, "stop_loss_abs", None)
        if stop_loss_abs is None or current_rate <= 0:
            return abs(float(self.stoploss))
        return abs(float(stop_loss_abs) - float(current_rate)) / float(current_rate)

    def _volatility_too_high(self, last, current_rate: float) -> bool:
        close = self._finite_positive(last.get("close", current_rate))
        atr = self._finite_positive(last.get("atr", None))
        if close is None or atr is None:
            return True
        return atr / close > self.max_scale_in_atr_pct
