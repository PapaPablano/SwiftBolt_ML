"""Comprehensive test of adaptive thresholds across all components."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "ml"))

import numpy as np
import pandas as pd

from src.forecast_synthesizer import ForecastSynthesizer
from src.forecast_weights import get_default_weights
from src.models.adaptive_targets import create_adaptive_targets
from src.models.enhanced_ensemble_integration import get_production_ensemble

try:
    from src.data.supabase_db import db
except Exception:
    db = None


def test_threshold_scaling():
    """Test adaptive thresholds scale with horizon."""
    print("=" * 60)
    print("TEST 1: Threshold Scaling")
    print("=" * 60)

    # Create synthetic data with 2% ATR
    dates = pd.date_range("2024-01-01", periods=500, freq="D")
    df = pd.DataFrame(
        {
            "ts": dates,
            "open": 100.0,
            "high": 102.0,
            "low": 98.0,
            "close": 100.0 + np.random.randn(500) * 0.5,
            "volume": 1000000,
            "atr": 2.0,  # Fixed 2% ATR
        }
    )

    expected_thresholds = {
        1: 2.0,
        5: 4.47,
        10: 6.32,
        20: 8.94,
    }

    for horizon, expected in expected_thresholds.items():
        labels, bear, bull = create_adaptive_targets(df, horizon_days=horizon)
        actual = abs(bear) * 100  # Convert to percentage

        tolerance = 0.3  # ±0.3%
        passed = abs(actual - expected) < tolerance

        print(
            f"\n{horizon}D: Expected ±{expected:.2f}%, Got ±{actual:.2f}% {'✅' if passed else '❌'}"
        )

        # Check label distribution
        dist = labels.value_counts(normalize=True)
        print(f"  Labels: {dist.to_dict()}")


def test_production_ensemble():
    """Test production ensemble with adaptive thresholds."""
    print("\n" + "=" * 60)
    print("TEST 2: Production Ensemble Integration")
    print("=" * 60)

    if db is None:
        print("⏭️  Skipped (supabase_db not available)")
        return

    # Fetch real data
    try:
        df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=500)
        if df.empty:
            print("❌ No data from database")
            return

        print(f"✅ Loaded {len(df)} bars for AAPL")

        # Test each horizon
        for horizon in [1, 5, 10, 20]:
            labels, bear, bull = create_adaptive_targets(df, horizon_days=horizon)

            print(f"\n{horizon}D Forecast:")
            print(f"  Thresholds: bear<{bear:.2%}, bull>{bull:.2%}")
            print(f"  Label distribution:")
            for label, pct in labels.value_counts(normalize=True).items():
                print(f"    {label}: {pct:.1%}")

    except Exception as e:
        print(f"❌ Test failed: {e}")


def test_full_forecast_pipeline():
    """Test complete forecast generation with adaptive thresholds."""
    print("\n" + "=" * 60)
    print("TEST 3: Full Forecast Pipeline")
    print("=" * 60)

    if db is None:
        print("⏭️  Skipped (supabase_db not available)")
        return

    try:
        # Get data
        df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=500)
        current_price = df["close"].iloc[-1]

        print(f"Current AAPL price: ${current_price:.2f}")

        # Generate forecasts for all horizons
        for horizon in [1, 5, 10, 20]:
            # Create adaptive labels
            labels, bear_thresh, bull_thresh = create_adaptive_targets(
                df,
                horizon_days=horizon,
            )

            # Count label distribution
            label_counts = labels.value_counts()
            total = len(labels)

            print(f"\n{horizon}D Horizon:")
            print(f"  Adaptive thresholds: {bear_thresh:.2%} / {bull_thresh:.2%}")
            print(f"  Training samples: {total}")
            print(
                f"    Bearish: {label_counts.get('bearish', 0)} ({label_counts.get('bearish', 0)/total:.1%})"
            )
            print(
                f"    Neutral: {label_counts.get('neutral', 0)} ({label_counts.get('neutral', 0)/total:.1%})"
            )
            print(
                f"    Bullish: {label_counts.get('bullish', 0)} ({label_counts.get('bullish', 0)/total:.1%})"
            )

            # Check if distribution is reasonable
            neutral_pct = label_counts.get("neutral", 0) / total
            if neutral_pct > 0.90:
                print(
                    f"  ⚠️  WARNING: {neutral_pct:.1%} neutral (thresholds may be too wide)"
                )
            elif neutral_pct < 0.40:
                print(
                    f"  ⚠️  WARNING: {neutral_pct:.1%} neutral (thresholds may be too narrow)"
                )
            else:
                print(f"  ✅ Good distribution ({neutral_pct:.1%} neutral)")

    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_threshold_scaling()
    test_production_ensemble()
    test_full_forecast_pipeline()

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)
