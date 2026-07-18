"""RegimeAware V6.6 with an offline Binance alpha-risk entry filter."""

import os

from RegimeAwareV66 import RegimeAwareV66
from alpha_risk_filter import apply_alpha_filter, load_alpha_risk_samples
from trade_supervisor_filter import apply_trade_supervisor_filter, load_trade_supervisor_decisions


class RegimeAwareV66AlphaRisk(RegimeAwareV66):
    """Backtest-only V6.6 variant that gates entries with stored alpha-risk samples."""

    alpha_risk_db_file = os.getenv("ALPHA_RISK_DB_FILE", "/freqtrade/project/user_data/monitor_history.sqlite")
    alpha_filter_mode = os.getenv("ALPHA_FILTER_MODE", "directional")
    alpha_filter_max_age_minutes = int(os.getenv("ALPHA_FILTER_MAX_AGE_MINUTES", "60"))
    trade_supervisor_enabled = os.getenv("TRADE_SUPERVISOR_ENABLED", "0") == "1"
    trade_supervisor_db_file = os.getenv("TRADE_SUPERVISOR_DB_FILE", alpha_risk_db_file)
    trade_supervisor_filter_mode = os.getenv("TRADE_SUPERVISOR_FILTER_MODE", "latest")
    trade_supervisor_max_age_minutes = int(os.getenv("TRADE_SUPERVISOR_MAX_AGE_MINUTES", "20"))
    trade_supervisor_fail_closed = os.getenv("TRADE_SUPERVISOR_FAIL_CLOSED", "1") != "0"
    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v66")
    trade_supervisor_soft_allowed_tags = os.getenv("TRADE_SUPERVISOR_SOFT_ALLOWED_TAGS", "")

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe = super().populate_entry_trend(dataframe, metadata)
        samples = load_alpha_risk_samples(self.alpha_risk_db_file)
        dataframe = apply_alpha_filter(
            dataframe,
            samples,
            mode=self.alpha_filter_mode,
            max_age_minutes=self.alpha_filter_max_age_minutes,
        )
        if not self.trade_supervisor_enabled:
            return dataframe

        supervisor_samples = load_trade_supervisor_decisions(self.trade_supervisor_db_file)
        return apply_trade_supervisor_filter(
            dataframe,
            supervisor_samples,
            bot_key=self.trade_supervisor_bot_key,
            mode=self.trade_supervisor_filter_mode,
            max_age_minutes=self.trade_supervisor_max_age_minutes,
            fail_closed=self.trade_supervisor_fail_closed,
            soft_allowed_tags=self.trade_supervisor_soft_allowed_tags,
        )

