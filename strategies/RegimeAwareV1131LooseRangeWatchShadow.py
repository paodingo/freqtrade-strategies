"""V11.31 loose-range watch long-only dry-run shadow strategy."""

from datetime import timedelta
import os

from pandas import DataFrame

from RegimeAwareV66AlphaRisk import RegimeAwareV66AlphaRisk


class RegimeAwareV1131LooseRangeWatchShadow(RegimeAwareV66AlphaRisk):
    """
    Isolated loose-range watch lane derived from the V11.30 observation work.

    The class intentionally avoids 1h features because Task 103 found recent
    1h futures OHLCV stale. It clears inherited entries and emits only the
    V11.31 shadow tag.
    """

    can_short = False
    timeframe = "15m"
    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    minimal_roi = {
        "0": 0.012,
        "60": 0.008,
        "120": 0.004,
        "240": 0,
    }
    stoploss = -0.02

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1131_loose_range_watch_shadow")
    scale_in_tag_prefix = "v1131"

    shadow_entry_tag = "v1131_loose_range_watch_long"
    shadow_stake_amount = 250
    shadow_allowed_pairs = {
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
        "DOGE/USDT:USDT",
        "LINK/USDT:USDT",
        "XRP/USDT:USDT",
        "BCH/USDT:USDT",
    }

    shadow_min_15m_return = 0.004
    shadow_min_15m_range = 0.008
    shadow_min_rsi = 35
    shadow_max_rsi = 62
    shadow_min_volume_ratio = 0.8
    shadow_take_profit = 0.008
    shadow_overbought_rsi = 68
    shadow_time_exit_minutes = 120

    raw_required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "volume_mean",
        "rsi",
    ]
    alpha_required_columns = [
        "alpha_filter_block_short",
        "alpha_risk_flags",
    ]

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = dataframe.copy()
        pair = metadata.get("pair", "")
        self._reset_v1131_entries(dataframe)

        raw_missing = self._missing_columns(dataframe, self.raw_required_columns)
        if raw_missing:
            dataframe["v1131_loose_range_gate"] = "blocked_missing_columns:" + ",".join(raw_missing)
            return dataframe

        dataframe = super().populate_entry_trend(dataframe, metadata)
        self._reset_v1131_entries(dataframe)

        if pair not in self.shadow_allowed_pairs:
            dataframe["v1131_loose_range_gate"] = "blocked_pair_not_allowlisted"
            return dataframe

        alpha_missing = self._missing_columns(dataframe, self.alpha_required_columns)
        if alpha_missing:
            dataframe["v1131_loose_range_gate"] = "blocked_missing_columns:" + ",".join(alpha_missing)
            return dataframe

        candidate = self._loose_range_watch_candidate(dataframe)
        alpha_short_blocked = dataframe["alpha_filter_block_short"].fillna(True).astype(bool)
        taker_sell_pressure = dataframe["alpha_risk_flags"].map(self._has_taker_sell_pressure)

        dataframe.loc[candidate & taker_sell_pressure, "v1131_loose_range_gate"] = "blocked_taker_sell_pressure"
        dataframe.loc[candidate & alpha_short_blocked & ~taker_sell_pressure, "v1131_loose_range_gate"] = "blocked_alpha_short"

        enabled = candidate & ~alpha_short_blocked & ~taker_sell_pressure
        dataframe.loc[enabled, "enter_long"] = 1
        dataframe.loc[enabled, "enter_tag"] = self.shadow_entry_tag
        dataframe.loc[enabled, "v1131_loose_range_gate"] = "enabled_loose_range_watch_long"

        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if side == "long" and entry_tag == self.shadow_entry_tag:
            return self._capped_stake(self.shadow_stake_amount, proposed_stake, min_stake, max_stake)

        return super().custom_stake_amount(
            pair=pair,
            current_time=current_time,
            current_rate=current_rate,
            proposed_stake=proposed_stake,
            min_stake=min_stake,
            max_stake=max_stake,
            leverage=leverage,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        if getattr(trade, "enter_tag", None) == self.shadow_entry_tag:
            if current_profit >= self.shadow_take_profit:
                return "v1131_loose_range_take_profit"

            last = self._last_analyzed_candle(pair)
            if last is not None and self._finite_float(last.get("rsi")) is not None:
                if self._finite_float(last.get("rsi")) > self.shadow_overbought_rsi:
                    return "v1131_loose_range_rsi_exit"

            if current_time - trade.open_date_utc >= timedelta(minutes=self.shadow_time_exit_minutes):
                return "v1131_loose_range_time_exit"
            return None

        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    def _loose_range_watch_candidate(self, dataframe: DataFrame):
        candle_return = (dataframe["close"] - dataframe["open"]) / dataframe["open"].where(dataframe["open"] != 0)
        candle_range = (dataframe["high"] - dataframe["low"]) / dataframe["close"].where(dataframe["close"] != 0)
        volume_ok = dataframe["volume"] > dataframe["volume_mean"] * self.shadow_min_volume_ratio

        return (
            (candle_return > self.shadow_min_15m_return)
            & (candle_range >= self.shadow_min_15m_range)
            & (dataframe["rsi"] >= self.shadow_min_rsi)
            & (dataframe["rsi"] <= self.shadow_max_rsi)
            & volume_ok
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _reset_v1131_entries(dataframe: DataFrame) -> None:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        dataframe["v1131_loose_range_gate"] = "not_candidate"

    @staticmethod
    def _missing_columns(dataframe: DataFrame, columns: list[str]) -> list[str]:
        return [column for column in columns if column not in dataframe.columns]

    @staticmethod
    def _has_taker_sell_pressure(raw_flags) -> bool:
        flags = {flag for flag in str(raw_flags or "").split(",") if flag}
        return "takerSellPressure" in flags

    @staticmethod
    def _capped_stake(target_stake: float, proposed_stake: float, min_stake: float | None, max_stake: float) -> float:
        stake = min(target_stake, proposed_stake, max_stake)
        if min_stake is not None and stake < min_stake:
            return min(max_stake, proposed_stake)
        return stake

    def _last_analyzed_candle(self, pair: str):
        if not getattr(self, "dp", None):
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        return dataframe.iloc[-1]
