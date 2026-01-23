#!/usr/bin/env python3
"""Debug script to test backtest strategy directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.data.supabase_db import SupabaseDatabase
from src.strategies.supertrend_ai import SuperTrendAI
from src.backtesting.backtest_engine import BacktestEngine
import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize
db = SupabaseDatabase()

# Fetch data
print("Fetching data for AAPL...")
df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=1000)
print(f"Fetched {len(df)} bars")

# Filter to date range
start_date = "2025-01-22"
end_date = "2026-01-22"
df['ts'] = pd.to_datetime(df['ts'])
if df['ts'].dt.tz is not None:
    df['ts'] = df['ts'].dt.tz_localize(None)

start = pd.Timestamp(start_date)
if start.tz is not None:
    start = start.tz_localize(None)
end = pd.Timestamp(end_date)
if end.tz is not None:
    end = end.tz_localize(None)

df = df[(df['ts'] >= start) & (df['ts'] <= end)].copy()
df = df.rename(columns={'ts': 'date'})
df = df.sort_values('date').reset_index(drop=True)

print(f"Filtered to {len(df)} bars from {start_date} to {end_date}")

# Calculate SuperTrend AI
print("\nCalculating SuperTrend AI...")
supertrend = SuperTrendAI(
    df=df,
    atr_length=10,
    min_mult=1.0,
    max_mult=5.0,
    step=0.5
)
result_df, info = supertrend.calculate()

print(f"SuperTrend AI calculated:")
print(f"  Target factor: {info['target_factor']:.2f}")
print(f"  Total signals: {info['total_signals']}")
print(f"  Buy signals: {info['buy_signals']}")
print(f"  Sell signals: {info['sell_signals']}")

# Check signal column
print(f"\nSignal column check:")
print(f"  Column 'supertrend_signal' exists: {'supertrend_signal' in result_df.columns}")
print(f"  Column 'signal' exists: {'signal' in result_df.columns}")
print(f"  Non-zero signals: {(result_df['supertrend_signal'] != 0).sum()}")
print(f"  Buy signals (==1): {(result_df['supertrend_signal'] == 1).sum()}")
print(f"  Sell signals (==-1): {(result_df['supertrend_signal'] == -1).sum()}")

# Check date column
print(f"\nDate column check:")
print(f"  Column 'date' exists: {'date' in result_df.columns}")
print(f"  Column 'ts' exists: {'ts' in result_df.columns}")
print(f"  Date range: {result_df['date'].min()} to {result_df['date'].max()}")

# Test strategy function
print("\n" + "="*70)
print("Testing strategy function...")
print("="*70)

def create_strategy(result_df, df):
    def strategy(data):
        signals = []
        date = data['date']
        
        # Normalize date
        if hasattr(date, 'tz') and date.tz is not None:
            date_naive = date.tz_localize(None)
        else:
            date_naive = pd.Timestamp(date)
        
        # Find matching row
        date_col = None
        for col in ['date', 'ts', 'timestamp']:
            if col in result_df.columns:
                date_col = col
                break
        
        if date_col:
            result_dates = pd.to_datetime(result_df[date_col])
            if result_dates.dt.tz is not None:
                result_dates = result_dates.dt.tz_localize(None)
            matching = result_df[result_dates == date_naive]
        else:
            matching = pd.DataFrame()
        
        if not matching.empty:
            row = matching.iloc[0]
            signal = row.get('supertrend_signal', row.get('signal', 0))
            
            if signal == 1 and data.get('cash', 0) >= 1000:
                close_price = data['ohlc'].get('close', data.get('close', 0))
                if close_price > 0:
                    signals.append({
                        'symbol': data.get('symbol', 'STOCK'),
                        'action': 'BUY',
                        'quantity': max(1, int(data['cash'] / close_price * 0.95)),
                        'price': close_price,
                        'strategy_name': 'SuperTrend AI'
                    })
            elif signal == -1:
                positions = data.get('positions', [])
                for pos in positions:
                    close_price = data['ohlc'].get('close', data.get('close', 0))
                    if close_price > 0:
                        signals.append({
                            'symbol': pos.get('symbol', 'STOCK'),
                            'action': 'SELL',
                            'quantity': pos.get('quantity', 0),
                            'price': close_price,
                            'strategy_name': 'SuperTrend AI'
                        })
        else:
            print(f"  No match for date: {date_naive}")
        
        return signals
    
    return strategy

strategy_func = create_strategy(result_df, df)

# Test a few dates
print("\nTesting strategy on first 5 dates:")
for i in range(min(5, len(df))):
    row = df.iloc[i]
    test_data = {
        'date': row['date'],
        'ohlc': row,
        'cash': 10000,
        'positions': [],
        'symbol': 'AAPL'
    }
    signals = strategy_func(test_data)
    if signals:
        print(f"  {row['date']}: {len(signals)} signals")
    else:
        print(f"  {row['date']}: No signals")

# Now test full backtest
print("\n" + "="*70)
print("Running full backtest...")
print("="*70)

engine = BacktestEngine(initial_capital=10000)
engine.load_historical_data(ohlc_data=df, options_data=None)

try:
    results = engine.run(strategy=strategy_func, start_date=start, end_date=end)
    print(f"\n✅ Backtest succeeded!")
    print(f"Total Trades: {results['metrics']['totalTrades']}")
    print(f"Total Return: {results['totalReturn']:.2%}")
    print(f"Sharpe Ratio: {results['metrics']['sharpeRatio']:.2f}")
except Exception as e:
    print(f"❌ Backtest failed: {e}")
    import traceback
    traceback.print_exc()
