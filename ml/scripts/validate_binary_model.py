#!/usr/bin/env python3
"""
Validate Binary Forecaster (Up/Down Classification)

Simpler than 3-class model.
Expected accuracy: ~47-50%
"""

import sys
from pathlib import Path
from datetime import datetime
import json

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db
from src.models.binary_forecaster import BinaryForecaster

print("="*80)
print("BINARY FORECASTER VALIDATION")
print("="*80)

# Settings
SYMBOLS = ['AAPL', 'MSFT', 'SPY', 'PG', 'NVDA']
HORIZONS = [1, 5, 10, 20]  # days
HOLDOUT_START = pd.Timestamp('2026-01-15')
HOLDOUT_END = pd.Timestamp('2026-02-03')

print(f"\nSettings:")
print(f"  Symbols: {SYMBOLS}")
print(f"  Horizons: {HORIZONS}")
print(f"  Holdout: {HOLDOUT_START.date()} to {HOLDOUT_END.date()}")

all_results = []

for symbol in SYMBOLS:
    print(f"\n{'='*60}")
    print(f"Validating {symbol}")
    print(f"{'='*60}")
    
    try:
        # Load data
        df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=1000)
        if df is None or len(df) == 0:
            print(f"  ❌ No data found")
            continue
        
        df['ts'] = pd.to_datetime(df['ts'])
        df = df.sort_values('ts').reset_index(drop=True)
        print(f"  Loaded {len(df)} bars")
        
        # Test each horizon
        for horizon in tqdm(HORIZONS, desc=f"{symbol} horizons"):
            try:
                # Create fresh model for each horizon
                model = BinaryForecaster()
                
                # Get training data (before holdout_start)
                train_df = df[df['ts'] < HOLDOUT_START].copy()
                if len(train_df) < 100:
                    continue
                
                # Prepare and train
                X, y = model.prepare_training_data(train_df, horizon_days=horizon)
                if len(X) < 100:
                    continue
                
                model.train(X, y, min_samples=50)
                
                # Test on holdout period
                test_dates = df[(df['ts'] >= HOLDOUT_START) & (df['ts'] <= HOLDOUT_END)]['ts'].unique()
                
                for test_date in test_dates:
                    # Get data up to test_date
                    df_up_to_test = df[df['ts'] <= test_date].copy()
                    
                    try:
                        pred = model.predict(df_up_to_test, horizon_days=horizon)
                    except Exception:
                        continue
                    
                    # Get actual return
                    test_row = df[df['ts'] == test_date]
                    if len(test_row) == 0:
                        continue
                    
                    target_date = test_date + pd.Timedelta(days=horizon)
                    target_row = df[df['ts'] >= target_date].head(1)
                    if len(target_row) == 0:
                        continue
                    
                    test_price = test_row['close'].iloc[0]
                    target_price = target_row['close'].iloc[0]
                    actual_return = (target_price - test_price) / test_price
                    
                    actual_label = "up" if actual_return >= 0 else "down"
                    
                    all_results.append({
                        'symbol': symbol,
                        'test_date': test_date,
                        'horizon': horizon,
                        'predicted_label': pred['label'],
                        'predicted_confidence': pred['confidence'],
                        'actual_label': actual_label,
                        'actual_return': actual_return,
                        'correct': pred['label'] == actual_label,
                    })
            except Exception:
                continue
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        continue

if not all_results:
    print("\n❌ No validation results")
    sys.exit(1)

results_df = pd.DataFrame(all_results)

print(f"\n\n" + "="*80)
print("BINARY MODEL VALIDATION RESULTS")
print("="*80)

accuracy = results_df['correct'].mean()
print(f"\nTotal predictions: {len(results_df)}")
print(f"Overall accuracy: {accuracy:.1%}")
print(f"Random baseline: 50.0%")
print(f"Improvement: {accuracy - 0.50:+.1%}")

if accuracy > 0.50:
    print(f"\n✅ MODEL WORKS! Better than random!")
    print(f"   Ready for cautious deployment")
elif accuracy > 0.48:
    print(f"\n⚠️  Near random, marginal signal detected")
else:
    print(f"\n❌ Model is worse than random")

# Per-symbol
print(f"\nPer-symbol accuracy:")
for symbol in sorted(results_df['symbol'].unique()):
    symbol_df = results_df[results_df['symbol'] == symbol]
    acc = symbol_df['correct'].mean()
    print(f"  {symbol}: {acc:.1%} (n={len(symbol_df)})")

# Per-horizon
print(f"\nPer-horizon accuracy:")
for horizon in sorted(results_df['horizon'].unique()):
    horizon_df = results_df[results_df['horizon'] == horizon]
    acc = horizon_df['correct'].mean()
    print(f"  {horizon}D: {acc:.1%} (n={len(horizon_df)})")

# Save results
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
results_file = f'validation_results/binary_results_{timestamp}.csv'
results_df.to_csv(results_file, index=False)
print(f"\nResults saved to: {results_file}")

db.close()
