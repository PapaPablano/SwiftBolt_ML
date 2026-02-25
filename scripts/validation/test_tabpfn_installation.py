"""
Quick test to verify TabPFN forecaster installation and basic functionality.

Usage:
    python test_tabpfn_installation.py

If you get a segmentation fault on macOS/Apple Silicon after the model downloads,
run with single-threaded OpenMP/MKL to reduce the chance of native library crashes:
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python test_tabpfn_installation.py
"""
import os
import sys
from pathlib import Path

# Reduce segfault risk on macOS/Apple Silicon (TabPFN/PyTorch native code)
# Must be set before importing numpy/torch/tabpfn
if "OMP_NUM_THREADS" not in os.environ:
    os.environ["OMP_NUM_THREADS"] = "1"
if "MKL_NUM_THREADS" not in os.environ:
    os.environ["MKL_NUM_THREADS"] = "1"

# Add ml directory to path
sys.path.insert(0, str(Path(__file__).parent / "ml"))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.models.tabpfn_forecaster import TabPFNForecaster, is_tabpfn_available


def create_synthetic_ohlc(n_bars: int = 252) -> pd.DataFrame:
    """Create synthetic OHLC data for testing."""
    np.random.seed(42)

    # Generate price series with trend + noise
    dates = pd.date_range(end=datetime.now(), periods=n_bars, freq='D')

    # Simulate a random walk with slight upward bias
    returns = np.random.normal(0.001, 0.02, n_bars)
    prices = 100 * np.exp(np.cumsum(returns))

    # Generate OHLCV
    df = pd.DataFrame({
        'ts': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, n_bars)),
        'high': prices * (1 + np.random.uniform(0.00, 0.02, n_bars)),
        'low': prices * (1 + np.random.uniform(-0.02, 0.00, n_bars)),
        'close': prices,
        'volume': np.random.randint(1_000_000, 10_000_000, n_bars),
    })

    return df


def test_tabpfn_basic():
    """Test basic TabPFN functionality."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic TabPFN Functionality")
    print("=" * 80)

    # Check if TabPFN is available
    print("\n1. Checking TabPFN availability...")
    if is_tabpfn_available():
        print("   ✓ TabPFN is available")
    else:
        print("   ✗ TabPFN not available")
        return False

    # Create synthetic data
    print("\n2. Creating synthetic OHLC data...")
    df = create_synthetic_ohlc(n_bars=252)
    print(f"   ✓ Created {len(df)} bars")
    print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # Initialize forecaster
    print("\n3. Initializing TabPFN forecaster...")
    try:
        forecaster = TabPFNForecaster(device='cpu', n_estimators=8)
        print("   ✓ Forecaster initialized")
    except Exception as e:
        print(f"   ✗ Failed to initialize: {e}")
        return False

    # Prepare training data
    print("\n4. Preparing training data...")
    try:
        X, y = forecaster.prepare_training_data(df, horizon_days=1)
        print(f"   ✓ Training data prepared: {len(X)} samples, {len(X.columns)} features")
        print(f"   Return stats: mean={y.mean():.4f}, std={y.std():.4f}")
    except Exception as e:
        print(f"   ✗ Failed to prepare data: {e}")
        return False

    # Train model
    print("\n5. Training TabPFN model...")
    try:
        start_time = datetime.now()
        forecaster.train(X, y)
        train_time = (datetime.now() - start_time).total_seconds()
        print(f"   ✓ Model trained in {train_time:.2f}s")
        print(f"   Training stats: {forecaster.training_stats}")
    except Exception as e:
        print(f"   ✗ Failed to train: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Make prediction
    print("\n6. Making prediction...")
    try:
        prediction = forecaster.predict(df, horizon_days=1)
        print(f"   ✓ Prediction: {prediction['label']} (confidence: {prediction['confidence']:.1%})")
        print(f"   Forecast return: {prediction.get('forecast_return', 0):.2%}")
        if 'intervals' in prediction:
            intervals = prediction['intervals']
            print(f"   Prediction interval: [{intervals['q10']:.4f}, {intervals['q90']:.4f}]")
            print(f"   Interval width: {intervals['width']:.4f}")
    except Exception as e:
        print(f"   ✗ Failed to predict: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✓ All tests passed!")
    print("=" * 80)
    return True


def test_tabpfn_multiple_horizons():
    """Test TabPFN with multiple horizons."""
    print("\n" + "=" * 80)
    print("TEST 2: Multiple Horizons")
    print("=" * 80)

    df = create_synthetic_ohlc(n_bars=252)
    horizons = [1, 5, 10, 20]

    print(f"\nTesting {len(horizons)} horizons: {horizons}")

    results = []
    for horizon in horizons:
        try:
            print(f"\n  Testing horizon: {horizon}D")
            forecaster = TabPFNForecaster(device='cpu', n_estimators=8)
            forecaster.fit(df, horizon_days=horizon)
            prediction = forecaster.predict(df, horizon_days=horizon)

            results.append({
                'horizon': f'{horizon}D',
                'direction': prediction['label'],
                'confidence': prediction['confidence'],
                'forecast_return': prediction.get('forecast_return', 0),
            })

            print(f"    ✓ {prediction['label']:8} ({prediction['confidence']:.1%})")

        except Exception as e:
            print(f"    ✗ Failed: {e}")
            continue

    if results:
        print(f"\n  ✓ Successfully tested {len(results)}/{len(horizons)} horizons")
        print("\n  Results summary:")
        for r in results:
            print(f"    {r['horizon']:4} {r['direction']:8} {r['confidence']:>6.1%} {r['forecast_return']:>+7.2%}")
        return True
    else:
        print(f"\n  ✗ All horizon tests failed")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("TABPFN FORECASTER INSTALLATION TEST")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Run tests
    test1_passed = test_tabpfn_basic()
    test2_passed = test_tabpfn_multiple_horizons()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"  Basic functionality:     {'✓ PASS' if test1_passed else '✗ FAIL'}")
    print(f"  Multiple horizons:       {'✓ PASS' if test2_passed else '✗ FAIL'}")
    print("=" * 80)

    if test1_passed and test2_passed:
        print("\n✓ TabPFN forecaster is ready to use!")
        print("\nNext steps:")
        print("  1. Apply database migration: supabase/migrations/20260131180000_add_model_type_to_ml_forecasts.sql")
        print("  2. Run unified forecast: python -m src.unified_forecast_job --symbol AAPL --model-type tabpfn")
        print("  3. Compare models: python experiments/tabpfn_vs_xgboost.py --symbols AAPL,MSFT --generate")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == '__main__':
    exit(main())
