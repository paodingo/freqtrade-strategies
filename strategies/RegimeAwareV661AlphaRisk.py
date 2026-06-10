"""RegimeAware V6.6.1 with alpha-level risk filtering and tighter shorts."""

import os

from RegimeAwareV66 import RegimeAwareV66
from RegimeAwareV66AlphaRisk import RegimeAwareV66AlphaRisk
from alpha_risk_filter import LONG_HOSTILE_FLAGS


class RegimeAwareV661AlphaRisk(RegimeAwareV66AlphaRisk):
    """V6.6 Alpha level plus stronger trend-short quality and faster invalidation."""

    alpha_filter_mode = os.getenv("ALPHA_FILTER_MODE", "level")

    @staticmethod
    def _populate_trending_entries(dataframe) -> None:
        RegimeAwareV66._populate_trending_entries(dataframe)

        short_mask = (
            (dataframe.get("enter_short", 0) == 1)
            & (dataframe.get("enter_tag", "") == "trending_short")
        )
        strong_downtrend = (
            (dataframe["adx_4h"] >= 30)
            & (dataframe["minus_di_4h"] > dataframe["plus_di_4h"] * 1.12)
            & (dataframe["ema21_4h"] < dataframe["ema55_4h"])
            & (dataframe["close_4h"] < dataframe["ema21_4h"])
        )
        not_late_chase = (
            (dataframe["rsi"] > 32)
            & (dataframe["bb_percent"] > 0.05)
            & (dataframe["close"] > dataframe["ema21"] * 0.965)
        )
        no_fast_bounce = (
            (dataframe["close"] <= dataframe["ema21"] * 1.003)
            & (dataframe["rsi"] < 53)
        )

        reject = short_mask & ~(strong_downtrend & not_late_chase & no_fast_bounce)
        dataframe.loc[reject, "enter_short"] = 0

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        if getattr(trade, "is_short", False) and "trending_short" in (trade.enter_tag or ""):
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if not dataframe.empty:
                last = dataframe.iloc[-1]
                if self._short_bounce_invalidated(last, current_profit):
                    return "v661_short_bounce_exit"
                if self._alpha_warns_against_short(last, current_profit):
                    return "v661_alpha_short_exit"

        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    @classmethod
    def _short_bounce_invalidated(cls, last, current_profit: float) -> bool:
        if current_profit >= 0:
            return False

        close = cls._finite_float(last.get("close"))
        ema21 = cls._finite_float(last.get("ema21"))
        ema55 = cls._finite_float(last.get("ema55"))
        rsi = cls._finite_float(last.get("rsi"))
        if close is None or ema21 is None or ema55 is None or rsi is None:
            return False

        return (
            (close > ema21 and rsi >= 55)
            or close > ema55 * 1.002
        )

    @classmethod
    def _alpha_warns_against_short(cls, last, current_profit: float) -> bool:
        if current_profit > -0.002:
            return False

        flags = {flag for flag in str(last.get("alpha_risk_flags") or "").split(",") if flag}
        return bool(flags & LONG_HOSTILE_FLAGS)
