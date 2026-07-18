"""RegimeAware V10.3 profit-runner version of the reliable short core."""

import os

from RegimeAwareV102ReliableShortCoreAlpha import RegimeAwareV102ReliableShortCoreAlpha


class RegimeAwareV103ProfitRunnerShortCoreAlpha(RegimeAwareV102ReliableShortCoreAlpha):
    """Use V10.2 entry quality, but require larger wins before taking profit."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v103")
    scale_in_tag_prefix = "v103"

    minimal_roi = {
        "0": 0.012,
        "45": 0.008,
        "120": 0.004,
        "360": 0.0015,
    }


