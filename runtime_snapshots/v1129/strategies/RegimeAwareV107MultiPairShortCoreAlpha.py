"""RegimeAware V10.7 multi-pair short-core candidate."""

import os

from RegimeAwareV103ProfitRunnerShortCoreAlpha import RegimeAwareV103ProfitRunnerShortCoreAlpha


class RegimeAwareV107MultiPairShortCoreAlpha(RegimeAwareV103ProfitRunnerShortCoreAlpha):
    """Run the V10.3 short core across a small liquid futures basket."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v107")
    scale_in_tag_prefix = "v107"


