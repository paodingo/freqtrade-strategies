"""Historical V6 RegimeAware strategy."""
from freqtrade.strategy import IStrategy

from regime_aware_base import RegimeAwareBaseMixin


class RegimeAware_C3D1_E0003(RegimeAwareBaseMixin, IStrategy):
    """V6 keeps both trend and ranging entries for historical comparisons."""

    candidate_identity_metadata = {
        "generator_version": "stage3b1-candidate-generator-v1",
        "legacy_base_name": "RegimeAwareV6",
        "semantic_role": "identity_only_candidate",
    }

    enable_ranging_entries = True
