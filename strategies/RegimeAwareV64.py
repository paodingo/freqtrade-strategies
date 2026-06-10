"""RegimeAware V6.4 - aggressive V6.3 challenger with risk-budgeted scale-ins."""

from RegimeAwareV63 import RegimeAwareV63


class RegimeAwareV64(RegimeAwareV63):
    """V6.4 keeps V6.3 safety checks but uses a more offensive risk budget."""

    timeframe = "15m"

    initial_stake_amount = 2500
    add_stake_amount = 1500
    max_total_stake_amount = 5000
    min_scale_in_profit = 0.008
    min_scale_in_minutes = 30
    old_position_stake_floor = initial_stake_amount * 0.8

    max_scale_in_account_loss_pct = 0.025
    max_scale_in_atr_pct = 0.04
    scale_in_tag_prefix = "v64"
