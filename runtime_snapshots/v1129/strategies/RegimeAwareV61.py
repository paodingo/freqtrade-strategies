"""RegimeAware V6.1 strategy."""
from freqtrade.strategy import IStrategy

from regime_aware_base import RegimeAwareBaseMixin


class RegimeAwareV61(RegimeAwareBaseMixin, IStrategy):
    """V6.1 keeps trend entries only and adds Freqtrade protections."""

    enable_ranging_entries = False

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 1,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 72,
                "trade_limit": 5,
                "stop_duration_candles": 6,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 168,
                "trade_limit": 20,
                "stop_duration_candles": 12,
                "max_allowed_drawdown": 0.08,
            },
        ]

