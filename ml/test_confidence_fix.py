"""Test confidence calculation fixes.

Verifies:
1. ml_agreement type (float 0-1)
2. Horizon penalty (longer horizons = lower confidence)
3. Adaptive thresholds (horizon-aware)
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from src.forecast_synthesizer import ForecastSynthesizer
from src.forecast_weights import get_default_weights


def test_confidence_horizon_penalty():
    """Verify confidence decreases with longer horizons."""
    weights = get_default_weights()
    synthesizer = ForecastSynthesizer(weights=weights)

    # Same inputs, different horizons - 20D should have lower confidence than 1D
    params = dict(
        trend_strength=0.5,
        ml_confidence=0.6,
        ml_agreement=0.8,
        st_bias=1,
        ml_bias=1,
        logistic_resistance_prob=0.3,
        logistic_support_prob=0.3,
        poly_is_expanding=True,
        poly_is_converging=False,
        direction="BULLISH",
    )

    conf_1d = synthesizer._calculate_confidence(**params, horizon_days=1.0)
    conf_5d = synthesizer._calculate_confidence(**params, horizon_days=5.0)
    conf_20d = synthesizer._calculate_confidence(**params, horizon_days=20.0)

    print("Confidence by horizon (same inputs):")
    print(f"  1D:  {conf_1d:.3f}")
    print(f"  5D:  {conf_5d:.3f}")
    print(f"  20D: {conf_20d:.3f}")

    assert conf_20d < conf_1d, "20D confidence should be lower than 1D"
    assert conf_5d <= conf_1d, "5D confidence should be <= 1D"
    print("✓ Horizon penalty working: longer horizons have lower confidence")


def test_ml_agreement_float():
    """Verify ml_agreement as float triggers strong_agreement boost."""
    weights = get_default_weights()
    synthesizer = ForecastSynthesizer(weights=weights)

    params = dict(
        trend_strength=0.4,
        ml_confidence=0.55,
        st_bias=0,
        ml_bias=0,
        logistic_resistance_prob=0.5,
        logistic_support_prob=0.5,
        poly_is_expanding=False,
        poly_is_converging=False,
        direction="NEUTRAL",
        horizon_days=1.0,
    )

    conf_low_agreement = synthesizer._calculate_confidence(
        **params, ml_agreement=0.2
    )
    conf_high_agreement = synthesizer._calculate_confidence(
        **params, ml_agreement=0.8
    )

    print("\nConfidence by ml_agreement (0.2 vs 0.8):")
    print(f"  ml_agreement=0.2: {conf_low_agreement:.3f}")
    print(f"  ml_agreement=0.8: {conf_high_agreement:.3f}")

    assert conf_high_agreement > conf_low_agreement, (
        "Higher ml_agreement should boost confidence"
    )
    print("✓ ml_agreement (float) correctly affects confidence")


def test_adaptive_thresholds():
    """Verify compute_thresholds_horizon scales by horizon."""
    from src.features.adaptive_thresholds import AdaptiveThresholds

    # Create minimal df with atr
    import pandas as pd

    np.random.seed(42)
    n = 100
    close = 100 * np.cumprod(1 + np.random.randn(n) * 0.01)
    atr = np.abs(np.random.randn(n)) * 2
    df = pd.DataFrame({"close": close, "atr_14": atr})

    bear_1, bull_1 = AdaptiveThresholds.compute_thresholds_horizon(
        df, horizon_days=1
    )
    bear_20, bull_20 = AdaptiveThresholds.compute_thresholds_horizon(
        df, horizon_days=20
    )

    print("\nAdaptive thresholds by horizon:")
    print(f"  1D:  bearish={bear_1:.4f}, bullish={bull_1:.4f}")
    print(f"  20D: bearish={bear_20:.4f}, bullish={bull_20:.4f}")

    assert abs(bear_20) > abs(bear_1), "20D bearish threshold should be wider"
    assert bull_20 > bull_1, "20D bullish threshold should be wider"
    print("✓ Horizon-aware thresholds: 20D wider than 1D")


if __name__ == "__main__":
    print("Testing confidence calculation fixes...\n")
    test_confidence_horizon_penalty()
    test_ml_agreement_float()
    test_adaptive_thresholds()
    print("\n✓ All tests passed")
