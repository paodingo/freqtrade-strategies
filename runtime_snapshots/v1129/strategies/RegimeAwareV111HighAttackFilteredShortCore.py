"""RegimeAware V11.1: disable negative-contribution pairs from V10.9."""

import os

from RegimeAwareV110HighAttackShortCore import RegimeAwareV110HighAttackShortCore


class RegimeAwareV111HighAttackFilteredShortCore(RegimeAwareV110HighAttackShortCore):
    """Keep the short core, add only proven/low-drag density pairs."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v111")
    scale_in_tag_prefix = "v111"

    v11_core_pairs = {
        "BTC/USDT:USDT",
        "SOL/USDT:USDT",
        "XRP/USDT:USDT",
        "DOGE/USDT:USDT",
        "LTC/USDT:USDT",
    }
    v11_watch_pairs = {
        "ADA/USDT:USDT",
        "ETH/USDT:USDT",
    }
    v11_experimental_pairs = set()
    negative_contribution_disabled_pairs = {
        "BNB/USDT:USDT",
        "BCH/USDT:USDT",
        "TRX/USDT:USDT",
        "LINK/USDT:USDT",
        "AVAX/USDT:USDT",
    }
    v11_disabled_pairs = negative_contribution_disabled_pairs

    core_pairs = v11_core_pairs
    watch_pairs = v11_watch_pairs
    blocked_pairs = v11_disabled_pairs

