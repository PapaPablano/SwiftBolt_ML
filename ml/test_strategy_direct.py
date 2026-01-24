#!/usr/bin/env python3
"""Test strategy function directly with a known signal date."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.data.supabase_db import SupabaseDatabase
from src.strategies.supertrend_ai import SuperTrendAI
from scripts.run_backtest import create_supertrend_ai_strategy
import pandas as pd

# Fetch and prepare data
db = SupabaseDatabase()
df = db.fetch_ohlc_bars('AAPL', timeframe='d1', limit=300)
df['ts'] = pd.to_datetime(df['ts'])
if df['ts'].dt.tz is not None:
    df['ts'] = df['ts'].dt.tz_localize(None)

start = pd.Timestamp('2025-01-22')
end = pd.Timestamp('2026-01-22')
df = df[(df['ts'] >= start) & (df['ts'] <= end)].copy()
df = df.rename(columns={'ts': 'date'})
df = df.sort_values('date').reset_index(drop=True)

# Create strategy
strategy_func = create_supertrend_ai_strategy(df, {
    'atr_length': 10,
    'min_mult': 1.0,
    'max_mult': 5.0
})

# Find a date with a buy signal by checking SuperTrend directly
supertrend = SuperTrendAI(df=df, atr_length=10, min_mult=1.0, max_mult=5.0, step=0.5)
result_df, info = supertrend.calculate()

buy_signals = result_df[result_df['supertrend_signal'] == 1]
if len(buy_signals) > 0:
    signal_date = buy_signals.iloc[0]['date']
    signal_idx = buy_signals.index[0]
    print(f"Testing with buy signal date: {signal_date}")
    
    # Create strategy data as backtest engine would
    row = df.iloc[signal_idx]
    strategy_data = {
        'date': row['date'],
        'ohlc': row,
        'close': row['close'],
        'positions': [],
        'cash': 10000,
        'portfolio_value': 10000,
        'symbol': 'AAPL'
    }
    
    # Call strategy
    signals = strategy_func(strategy_data)
    print(f"Strategy returned {len(signals)} signals")
    if signals:
        for sig in signals:
            print(f"  {sig}")
    else:
        print("  No signals generated!")
        print(f"  Date passed: {strategy_data['date']}")
        print(f"  Cash: {strategy_data['cash']}")
else:
    print("No buy signals found in data")
