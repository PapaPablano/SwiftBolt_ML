#!/usr/bin/env python
"""
Debug ensemble training failures by symbol.

Identifies why ensemble.train() is failing for specific symbols,
causing fallback to 40% confidence predictions.
"""

import os
import sys
from argparse import ArgumentParser
import logging

from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# Set up logging to see all warnings
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

from config.settings import settings
from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features
from src.models.baseline_forecaster import BaselineForecaster
from src.models.enhanced_ensemble_integration import get_production_ensemble


def debug_ensemble_training(symbol: str, horizon: str = "1D"):
    """Debug ensemble training for a single symbol."""
    print(f"\n{'='*70}")
    print(f"DEBUGGING ENSEMBLE TRAINING: {symbol} / {horizon}")
    print(f"{'='*70}")

    # Get symbol ID
    symbol_id = db.get_symbol_id(symbol)
    if not symbol_id:
        print(f"❌ Symbol not found: {symbol}")
        return False

    print(f"✅ Symbol ID: {symbol_id}")

    # Fetch OHLC data
    print(f"\n1️⃣  Fetching OHLC data ({horizon})...")
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=500)

    if df.empty:
        print(f"❌ No OHLC data found")
        return False

    print(f"✅ Fetched {len(df)} bars")

    # Add technical features
    print(f"\n2️⃣  Adding technical features...")
    try:
        df = add_technical_features(df)
        print(f"✅ Features added. Columns: {len(df.columns)}")

        # Check for NaN/Inf in features
        nan_count = df.isna().sum().sum()
        inf_count = df.isin([float('inf'), float('-inf')]).sum().sum()
        print(f"   NaN values: {nan_count}")
        print(f"   Inf values: {inf_count}")

        if nan_count > 0 or inf_count > 0:
            print(f"   ⚠️  WARNING: Data quality issues detected")
    except Exception as e:
        print(f"❌ Feature addition failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Prepare training data
    print(f"\n3️⃣  Preparing training data...")
    try:
        baseline_prep = BaselineForecaster()

        # Determine horizon days
        horizon_days = {
            "1D": 1,
            "5D": 5,
            "10D": 10,
            "20D": 20,
        }.get(horizon, 1)

        X_train, y_train = baseline_prep.prepare_training_data(df, horizon_days=horizon_days)

        print(f"✅ Training data prepared")
        print(f"   X shape: {X_train.shape}")
        print(f"   y shape: {y_train.shape}")
        print(f"   Min training bars required: {settings.min_bars_for_training}")
        print(f"   Have sufficient data: {len(X_train) >= settings.min_bars_for_training}")

        if len(X_train) == 0:
            print(f"❌ No training samples generated!")
            return False

        if len(X_train) < settings.min_bars_for_training:
            print(f"⚠️  Insufficient training data: {len(X_train)} < {settings.min_bars_for_training}")

    except Exception as e:
        print(f"❌ Training data prep failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Try ensemble training
    print(f"\n4️⃣  Attempting ensemble training...")
    try:
        print(f"   Getting production ensemble...")
        ensemble = get_production_ensemble(
            horizon=horizon,
            symbol_id=symbol_id,
        )
        print(f"   ✅ Ensemble created")

        # Calculate alignment indices (same as in unified_forecast_job.py)
        min_offset = 50 if len(df) >= 100 else (26 if len(df) >= 60 else 14)
        start_idx = max(min_offset, 14)
        end_idx = len(df) - max(1, int(horizon_days))
        ohlc_train = df.iloc[start_idx:end_idx].copy()

        print(f"   Training with indices: [{start_idx}:{end_idx}]")
        print(f"   OHLC training data shape: {ohlc_train.shape}")

        print(f"\n   Calling ensemble.train()...")
        ensemble.train(
            features_df=X_train,
            labels_series=y_train,
            ohlc_df=ohlc_train,
        )
        print(f"   ✅ Ensemble training successful!")

        print(f"\n   Getting prediction...")
        ml_pred = ensemble.predict(
            features_df=X_train.tail(1),
            ohlc_df=df,
        )
        print(f"   ✅ Ensemble prediction successful!")
        print(f"   Label: {ml_pred.get('label', 'unknown')}")
        print(f"   Confidence: {ml_pred.get('confidence', 0):.0%}")
        print(f"   N models: {ml_pred.get('n_models', 0)}")

        return True

    except Exception as e:
        print(f"❌ Ensemble training failed: {e}")
        import traceback
        traceback.print_exc()

        print(f"\n   Falling back to BaselineForecaster...")
        try:
            baseline_forecaster = BaselineForecaster()
            baseline_forecaster.fit(df, horizon_days=horizon_days)
            ml_pred = baseline_forecaster.predict(df, horizon_days=horizon_days)
            print(f"   ✅ Baseline prediction: {ml_pred.get('label', 'unknown')} ({ml_pred.get('confidence', 0):.0%})")
            return False  # Return False because ensemble failed (even though baseline worked)
        except Exception as e2:
            print(f"   ❌ Even baseline failed: {e2}")
            return False


def main():
    parser = ArgumentParser(description="Debug ensemble training failures")
    parser.add_argument("--symbol", type=str, default="AMD", help="Symbol to debug")
    parser.add_argument("--horizon", type=str, default="1D", help="Horizon (1D, 5D, 10D, 20D)")
    parser.add_argument("--all-intraday", action="store_true", help="Test all intraday_symbols")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("ENSEMBLE TRAINING DEBUG")
    print("="*70)

    if args.all_intraday:
        symbols = settings.intraday_symbols
        print(f"\nTesting all intraday symbols: {symbols}")

        results = {}
        for symbol in symbols:
            success = debug_ensemble_training(symbol, args.horizon)
            results[symbol] = "✅ PASS" if success else "❌ FAIL"

        print(f"\n\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        for symbol, status in results.items():
            print(f"{symbol}: {status}")
    else:
        debug_ensemble_training(args.symbol, args.horizon)

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    sys.exit(main())
