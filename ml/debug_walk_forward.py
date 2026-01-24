#!/usr/bin/env python3
"""Debug script to test prepare_training_data directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.data.supabase_db import SupabaseDatabase
from src.models.baseline_forecaster import BaselineForecaster
import pandas as pd
import logging

# Only show warnings and above for HTTP libraries
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize
db = SupabaseDatabase()
forecaster = BaselineForecaster()

# Fetch data
print("Fetching data for AAPL...")
df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=1000)
print(f"Fetched {len(df)} bars")
print(f"Date range: {df['ts'].min()} to {df['ts'].max()}")

# Simulate a training window (first 126 bars)
train_window = 126
train_df = df.iloc[:train_window].copy()
print(f"\nTraining window: {len(train_df)} bars")

# Test prepare_training_data
print("\nTesting prepare_training_data...")
try:
    X, y = forecaster.prepare_training_data(train_df, horizon_days=1)
    print(f"✅ Generated {len(X)} samples")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    if len(y) > 0:
        print(f"Label distribution: {y.value_counts().to_dict()}")
    else:
        print("❌ No samples generated!")
        
        # Debug: check forward returns
        forward_returns = train_df["close"].pct_change(periods=1).shift(-1)
        print(f"\nForward returns stats:")
        print(f"  Total: {len(forward_returns)}")
        print(f"  Non-NaN: {forward_returns.notna().sum()}")
        print(f"  NaN: {forward_returns.isna().sum()}")
        print(f"  Range with data (50 to {len(train_df)-1}): {forward_returns.iloc[50:len(train_df)-1].notna().sum()} valid")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
