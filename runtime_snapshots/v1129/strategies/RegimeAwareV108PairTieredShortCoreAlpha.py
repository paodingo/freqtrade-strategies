"""RegimeAware V10.8 pair-tiered multi-pair short-core candidate."""

import os

from RegimeAwareV107MultiPairShortCoreAlpha import RegimeAwareV107MultiPairShortCoreAlpha


class RegimeAwareV108PairTieredShortCoreAlpha(RegimeAwareV107MultiPairShortCoreAlpha):
    """Keep V10.7 signals, but gate and size entries by pair contribution tier."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v108")
    scale_in_tag_prefix = "v108"

    core_pair_stake_amount = 2500
    watch_pair_stake_amount = 1250
    blocked_pair_stake_amount = 0

    core_pairs = {
        "BTC/USDT:USDT",
        "SOL/USDT:USDT",
        "XRP/USDT:USDT",
        "DOGE/USDT:USDT",
    }
    watch_pairs = {
        "ETH/USDT:USDT",
    }
    blocked_pairs = {
        "BNB/USDT:USDT",
    }

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        pair = metadata.get("pair", "")
        tier = self._pair_tier(pair)
        result["v108_pair_tier"] = tier

        if tier == "blocked":
            blocked = result.get("enter_short", 0) == 1
            self._block_entries(result, blocked)
            result.loc[blocked, "enter_tag"] = f"v108_pair_blocked_{self._pair_token(pair)}"

        return result

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
        target = self._stake_for_pair(pair)
        if target <= 0:
            return 0.0

        _, available_balance = self._stake_balances(0.0, max_stake)
        stake = min(target, float(proposed_stake), float(max_stake), available_balance)
        if min_stake is not None and stake < float(min_stake):
            return 0.0
        return max(0.0, stake)

    @classmethod
    def _pair_tier(cls, pair: str) -> str:
        if pair in cls.blocked_pairs:
            return "blocked"
        if pair in cls.watch_pairs:
            return "watch"
        if pair in cls.core_pairs:
            return "core"
        return "watch"

    @classmethod
    def _stake_for_pair(cls, pair: str) -> float:
        tier = cls._pair_tier(pair)
        if tier == "blocked":
            return cls.blocked_pair_stake_amount
        if tier == "watch":
            return cls.watch_pair_stake_amount
        return cls.core_pair_stake_amount

    @staticmethod
    def _pair_token(pair: str) -> str:
        return str(pair).split("/")[0].lower()

