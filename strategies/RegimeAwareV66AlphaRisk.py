"""RegimeAware V6.6 with an offline Binance alpha-risk entry filter."""

import os

from RegimeAwareV66 import RegimeAwareV66
from alpha_risk_filter import apply_alpha_filter, load_alpha_risk_samples


class RegimeAwareV66AlphaRisk(RegimeAwareV66):
    """Backtest-only V6.6 variant that gates entries with stored alpha-risk samples."""

    alpha_risk_db_file = os.getenv("ALPHA_RISK_DB_FILE", "/freqtrade/project/user_data/monitor_history.sqlite")
    alpha_filter_mode = os.getenv("ALPHA_FILTER_MODE", "directional")
    alpha_filter_max_age_minutes = int(os.getenv("ALPHA_FILTER_MAX_AGE_MINUTES", "60"))

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe = super().populate_entry_trend(dataframe, metadata)
        samples = load_alpha_risk_samples(self.alpha_risk_db_file)
        return apply_alpha_filter(
            dataframe,
            samples,
            mode=self.alpha_filter_mode,
            max_age_minutes=self.alpha_filter_max_age_minutes,
        )
