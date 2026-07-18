"""RegimeAware V10.8.2: BNB and ETH as half-size watch pairs."""

import os

from RegimeAwareV108PairTieredShortCoreAlpha import RegimeAwareV108PairTieredShortCoreAlpha


class RegimeAwareV1082PairTieredShortCoreAlpha(RegimeAwareV108PairTieredShortCoreAlpha):
    """Variant scan: allow BNB, but only as a half-size watch pair."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1082")
    scale_in_tag_prefix = "v1082"

    watch_pairs = {
        "ETH/USDT:USDT",
        "BNB/USDT:USDT",
    }
    blocked_pairs = set()

