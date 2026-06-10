"""RegimeAware V6.6.2 alpha variant with higher capital utilization."""

from RegimeAwareV661AlphaRisk import RegimeAwareV661AlphaRisk


class RegimeAwareV662AlphaRisk(RegimeAwareV661AlphaRisk):
    """V6.6.1 behavior with a larger but still capped position budget."""

    initial_stake_amount = 3000
    add_stake_amount = 1500
    max_total_stake_amount = 6000
    old_position_stake_floor = initial_stake_amount * 0.8

    max_scale_in_account_loss_pct = 0.03
    scale_in_tag_prefix = "v662"
