"""Historical V6 RegimeAware strategy."""
from freqtrade.strategy import IStrategy

from regime_aware_base import RegimeAwareBaseMixin


class RegimeAwareV6(RegimeAwareBaseMixin, IStrategy):
    """V6 keeps both trend and ranging entries for historical comparisons."""

    enable_ranging_entries = True
