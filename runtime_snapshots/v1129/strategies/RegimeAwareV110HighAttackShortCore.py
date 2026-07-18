"""RegimeAware V11.0: high-attack race baseline with capped exposure."""

import os

from RegimeAwareV1082PairTieredShortCoreAlpha import RegimeAwareV1082PairTieredShortCoreAlpha


class RegimeAwareV110HighAttackShortCore(RegimeAwareV1082PairTieredShortCoreAlpha):
    """Keep the V10.8.2 short core while declaring V11 high-attack constraints."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v110")
    scale_in_tag_prefix = "v110"

    high_attack_target_net_profit_pct = 15
    max_portfolio_stake_amount = 10000
    core_pair_stake_amount = 2500
    watch_pair_stake_amount = 1250
    experimental_pair_stake_amount = 500
    blocked_pair_stake_amount = 0

    v11_core_pairs = {
        "BTC/USDT:USDT",
        "SOL/USDT:USDT",
        "XRP/USDT:USDT",
        "DOGE/USDT:USDT",
    }
    v11_watch_pairs = {
        "ETH/USDT:USDT",
        "BNB/USDT:USDT",
    }
    v11_experimental_pairs = set()
    v11_disabled_pairs = set()

    core_pairs = v11_core_pairs
    watch_pairs = v11_watch_pairs
    blocked_pairs = v11_disabled_pairs

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        pair = metadata.get("pair", "")
        tier = self._effective_pair_tier(pair)
        weakness = self._recent_weakness_for_pair(pair)
        result["v11_pair_tier"] = tier
        result["v11_recent_weakness"] = weakness
        result["v11_strategy_arm"] = result.get("v11_strategy_arm", "short_core")

        disabled = (result.get("enter_short", 0) == 1) & (tier == "disabled")
        if disabled.any():
            self._block_entries(result, disabled)
            result.loc[disabled, "enter_tag"] = f"v11_pair_disabled_{self._pair_token(pair)}"
        return result

    @classmethod
    def _pair_tier(cls, pair: str) -> str:
        if pair in cls.v11_disabled_pairs:
            return "disabled"
        if pair in cls.v11_core_pairs:
            return "core"
        if pair in cls.v11_watch_pairs:
            return "watch"
        if pair in cls.v11_experimental_pairs:
            return "experimental"
        return "disabled"

    @classmethod
    def _effective_pair_tier(cls, pair: str) -> str:
        weakness = cls._recent_weakness_for_pair(pair)
        if weakness == "disabled":
            return "disabled"
        if weakness == "watch" and cls._pair_tier(pair) == "core":
            return "watch"
        return cls._pair_tier(pair)

    @classmethod
    def _stake_for_pair(cls, pair: str) -> float:
        tier = cls._effective_pair_tier(pair)
        if tier == "disabled":
            return cls.blocked_pair_stake_amount
        if tier == "experimental":
            return cls.experimental_pair_stake_amount
        if tier == "watch":
            return cls.watch_pair_stake_amount
        return cls.core_pair_stake_amount

    @classmethod
    def _recent_weakness_for_pair(cls, pair: str) -> str:
        if cls._pair_in_env(pair, "V11_RECENT_DISABLED_PAIRS"):
            return "disabled"
        if cls._pair_in_env(pair, "V11_RECENT_WATCH_PAIRS"):
            return "watch"
        return "neutral"

    @classmethod
    def _pair_in_env(cls, pair: str, env_name: str) -> bool:
        raw = os.getenv(env_name, "")
        if not raw.strip():
            return False

        token = cls._pair_token(pair)
        values = {item.strip().lower() for item in raw.replace(";", ",").split(",") if item.strip()}
        return pair.lower() in values or token in values

