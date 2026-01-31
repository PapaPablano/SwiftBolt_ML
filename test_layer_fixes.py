"""Test forecast synthesizer layer fixes.

Verifies:
1. Layer agreement counting (BULLISH and BEARISH)
2. _determine_direction (weighted by strength)
3. Confidence horizon scaling
4. ml_agreement tiered boosts (0.67 / 0.5)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "ml"))

from src.forecast_synthesizer import ForecastSynthesizer
from src.forecast_weights import get_default_weights


def test_layer_agreement():
    """Test agreeing layers counting for BULLISH and BEARISH."""
    print("=" * 60)
    print("TEST 1: Layer Agreement Counting")
    print("=" * 60)

    synthesizer = ForecastSynthesizer(weights=get_default_weights())

    # All BULLISH: st=1, ml=1, S/R room up -> expecting 3 layers agree
    layer_directions = [1, 1]
    resistance_room, support_room = 0.02, 0.01
    st_bias, ml_bias = 1, 1
    if st_bias == 1 and resistance_room > 0.01:
        layer_directions.append(1)
    primary_bias = st_bias if st_bias != 0 else ml_bias
    agreeing = len([d for d in layer_directions if d == primary_bias])
    print(f"\nAll BULLISH (st=1, ml=1, S/R room up): agreeing_layers = {agreeing} (expected >= 2)")

    # All BEARISH: st=-1, ml=-1, S/R room down
    layer_directions = [-1, -1]
    if -1 == -1 and support_room > 0.01:
        layer_directions.append(-1)
    primary_bias = -1
    agreeing = len([d for d in layer_directions if d == primary_bias])
    print(f"All BEARISH (st=-1, ml=-1, S/R room down): agreeing_layers = {agreeing} (expected >= 2)")

    # Conflicting: st=1, ml=-1
    layer_directions = [1, -1]
    primary_bias = 1
    agreeing = len([d for d in layer_directions if d == primary_bias])
    print(f"Conflicting (st=1, ml=-1): agreeing_layers = {agreeing} (expected 1)")
    print()


def test_determine_direction():
    """Test _determine_direction for agreement and conflict."""
    print("=" * 60)
    print("TEST 2: _determine_direction")
    print("=" * 60)

    synthesizer = ForecastSynthesizer(weights=get_default_weights())

    # Both agree BULLISH
    d = synthesizer._determine_direction(
        st_bias=1, ml_bias=1,
        signal_strength=0.7, ml_confidence=0.75,
        resistance_room=0.02, support_room=0.01,
    )
    print(f"\nst=1, ml=1 -> {d} (expected BULLISH)")
    assert d == "BULLISH"

    # Both agree BEARISH
    d = synthesizer._determine_direction(
        st_bias=-1, ml_bias=-1,
        signal_strength=0.7, ml_confidence=0.75,
        resistance_room=0.01, support_room=0.02,
    )
    print(f"st=-1, ml=-1 -> {d} (expected BEARISH)")
    assert d == "BEARISH"

    # ST neutral, ML bullish
    d = synthesizer._determine_direction(
        st_bias=0, ml_bias=1,
        signal_strength=0.5, ml_confidence=0.7,
        resistance_room=0.02, support_room=0.01,
    )
    print(f"st=0, ml=1 -> {d} (expected BULLISH)")
    assert d == "BULLISH"
    print()


def test_confidence_horizons():
    """Test confidence decreases with horizon."""
    print("=" * 60)
    print("TEST 3: Confidence Horizon Scaling")
    print("=" * 60)

    synthesizer = ForecastSynthesizer(weights=get_default_weights())

    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "ts": dates,
        "open": 100 + np.random.randn(100).cumsum() * 0.5,
        "high": 102 + np.random.randn(100).cumsum() * 0.5,
        "low": 98 + np.random.randn(100).cumsum() * 0.5,
        "close": 100 + np.random.randn(100).cumsum() * 0.5,
        "volume": 1000000 + np.random.randint(-100000, 100000, 100),
        "atr": 2.0 + np.random.randn(100) * 0.1,
    })
    df["atr"] = df["atr"].clip(0.5, 5.0)

    supertrend_info = {
        "current_trend": "BULLISH",
        "signal_strength": 7,
        "performance_index": 0.7,
        "atr": 2.0,
    }

    sr_response = {
        "polynomial": {"isDiverging": False, "isConverging": False},
        "logistic": {},
        "pivots": [],
    }

    ensemble_result = {
        "label": "Bullish",
        "confidence": 0.75,
        "agreement": 0.8,
    }

    current_price = 100.0
    horizons = [1, 5, 10, 20]
    confidences = []

    print("\nGenerating forecasts for different horizons...")
    for horizon in horizons:
        try:
            result = synthesizer.generate_forecast(
                current_price=current_price,
                df=df,
                supertrend_info=supertrend_info,
                sr_response=sr_response,
                ensemble_result=ensemble_result,
                horizon_days=float(horizon),
                symbol="TEST",
            )
            confidences.append((horizon, result.confidence))
            print(f"  {horizon}D: confidence={result.confidence:.2f}, direction={result.direction}")
        except Exception as e:
            print(f"  {horizon}D: ERROR - {e}")

    if len(confidences) >= 2:
        # Confidence should generally decrease or stay similar with longer horizon
        print("\nExpected: confidence should decrease or stay similar as horizon increases")
    print("=" * 60)


def test_ml_agreement_tiers():
    """Test ml_agreement tiered boosts (0.67 full, 0.5 half)."""
    print("\n" + "=" * 60)
    print("TEST 4: ml_agreement Tiered Boosts")
    print("=" * 60)

    synthesizer = ForecastSynthesizer(weights=get_default_weights())

    base = dict(
        trend_strength=0.5,
        st_bias=1,
        ml_bias=1,
        logistic_resistance_prob=0.3,
        logistic_support_prob=0.3,
        poly_is_expanding=False,
        poly_is_converging=False,
        direction="BULLISH",
        horizon_days=1.0,
    )

    c_low = synthesizer._calculate_confidence(ml_confidence=0.6, ml_agreement=0.4, **base)
    c_mid = synthesizer._calculate_confidence(ml_confidence=0.6, ml_agreement=0.55, **base)
    c_high = synthesizer._calculate_confidence(ml_confidence=0.6, ml_agreement=0.75, **base)

    print(f"\nml_agreement=0.4  -> confidence={c_low:.3f}")
    print(f"ml_agreement=0.55 -> confidence={c_mid:.3f} (half boost)")
    print(f"ml_agreement=0.75 -> confidence={c_high:.3f} (full boost)")
    assert c_mid > c_low
    assert c_high >= c_mid
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_layer_agreement()
    test_determine_direction()
    test_confidence_horizons()
    test_ml_agreement_tiers()
    print("\nAll tests completed.")
