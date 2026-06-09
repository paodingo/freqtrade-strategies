"""RegimeAware V6.2 - V6.1 signals with conservative scale-in support."""
from datetime import datetime

from freqtrade.persistence import Trade

from RegimeAwareV61 import RegimeAwareV61


class RegimeAwareV62(RegimeAwareV61):
    """V6.1 plus controlled trend-following position adjustment.

    The first entry is intentionally smaller than V6.1.  Additional entries are
    only added to winning positions when the latest analyzed candle still emits
    a same-direction entry signal.  Old small dry-run positions are left alone.
    """

    position_adjustment_enable = True
    max_entry_position_adjustment = 2

    initial_stake_amount = 1500
    add_stake_amount = 1000
    max_total_stake_amount = 3500
    min_scale_in_profit = 0.012
    old_position_stake_floor = initial_stake_amount * 0.8

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        stake = min(self.initial_stake_amount, proposed_stake, max_stake)
        if min_stake is not None and stake < min_stake:
            return min(max_stake, proposed_stake)
        return stake

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

        if not self._same_direction_signal_active(trade):
            return None

        remaining_budget = self.max_total_stake_amount - current_stake
        stake = min(self.add_stake_amount, remaining_budget, max_stake)
        if min_stake is not None and stake < min_stake:
            return None
        if stake <= 0:
            return None

        return stake, f"v62_scale_in_{successful_entries}"

    def _same_direction_signal_active(self, trade: Trade) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe.empty:
            return False

        last = dataframe.iloc[-1]
        if getattr(trade, "is_short", False):
            return bool(last.get("enter_short", 0) == 1)
        return bool(last.get("enter_long", 0) == 1)
