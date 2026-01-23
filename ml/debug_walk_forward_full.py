#!/usr/bin/env python3
"""Debug script to test walk-forward optimization directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.data.supabase_db import SupabaseDatabase
from src.models.baseline_forecaster import BaselineForecaster
from src.backtesting.walk_forward_tester import WalkForwardBacktester
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize
db = SupabaseDatabase()
forecaster = BaselineForecaster()

# Fetch data
print("Fetching data for AAPL...")
df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=1000)
print(f"Fetched {len(df)} bars")

# Create walk-forward backtester
backtester = WalkForwardBacktester(
    train_window=126,
    test_window=10,
    step_size=2,
)

print(f"\nWalk-forward config:")
print(f"  Train window: {backtester.train_window}")
print(f"  Test window: {backtester.test_window}")
print(f"  Step size: {backtester.step_size}")
print(f"  Data length: {len(df)}")

# Test first window manually
print("\n" + "="*70)
print("Testing first window manually...")
print("="*70)

train_df = df.iloc[0:126].copy()
print(f"First window train_df: {len(train_df)} bars")

X, y = forecaster.prepare_training_data(train_df, horizon_days=1)
print(f"Generated {len(X)} samples")

if len(X) >= 20:
    try:
        forecaster.train(X, y, min_samples=20)
        print("✅ Training succeeded!")
    except Exception as e:
        print(f"❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"❌ Not enough samples: {len(X)} < 20")

# Now test full walk-forward
print("\n" + "="*70)
print("Testing full walk-forward optimization...")
print("="*70)

try:
    metrics = backtester.backtest(df, forecaster, horizons=["1D"])
    print(f"✅ Walk-forward succeeded!")
    print(f"Metrics: {metrics}")
except Exception as e:
    print(f"❌ Walk-forward failed: {e}")
    import traceback
    traceback.print_exc()
