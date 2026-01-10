#!/usr/bin/env python3
"""
Compare TradingView exported data with our ML system data quality.
Validates SuperTrend, KDJ, and ADX indicator calculations.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

# Add ml/src to path
sys.path.insert(0, str(Path(__file__).parent / "ml" / "src"))

from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv("ml/.env")

def load_tradingview_data(filepath: str) -> pd.DataFrame:
    """Load and parse TradingView CSV export."""
    df = pd.read_csv(filepath)
    
    # Parse the column names - TradingView exports have multiple columns with same name
    # Columns: time, open, high, low, close, Basis, Upper, Lower, Volume, 
    #          Trailing Stop, Trailing Stop AMA, Plot, Plot, Plot, Zero line,
    #          RSI Cloud Lead, RSI Cloud Base, RSI Overbought, Signal RSI Overbought,
    #          RSI Oversold, Signal RSI Oversold, Baseline, Cloud Flip Bullish,
    #          Cloud Flip Bearish, RSI, ADX Current Timeframe, ADX Different Timeframe
    
    # Rename for clarity
    df.columns = [
        'time', 'open', 'high', 'low', 'close',
        'bb_basis', 'bb_upper', 'bb_lower', 'volume',
        'supertrend_stop', 'supertrend_ama',
        'kdj_k', 'kdj_d', 'kdj_j', 'kdj_zero',
        'rsi_cloud_lead', 'rsi_cloud_base',
        'rsi_overbought', 'signal_rsi_overbought',
        'rsi_oversold', 'signal_rsi_oversold',
        'baseline', 'cloud_flip_bullish', 'cloud_flip_bearish',
        'rsi', 'adx_current', 'adx_different'
    ]
    
    # Convert time to datetime
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    
    return df

def fetch_our_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch our OHLCV and indicator data from Supabase."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing Supabase credentials in .env")
    
    supabase = create_client(supabase_url, supabase_key)
    
    # Fetch OHLCV data
    response = supabase.table("ohlcv_daily") \
        .select("*") \
        .eq("symbol", symbol) \
        .gte("date", start_date) \
        .lte("date", end_date) \
        .order("date") \
        .execute()
    
    if not response.data:
        print(f"No data found for {symbol}")
        return pd.DataFrame()
    
    df = pd.DataFrame(response.data)
    df['date'] = pd.to_datetime(df['date'])
    
    return df

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Calculate SuperTrend indicator."""
    # Calculate ATR
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(window=period).mean()
    
    # Calculate basic bands
    hl_avg = (df['high'] + df['low']) / 2
    df['upper_band'] = hl_avg + (multiplier * df['atr'])
    df['lower_band'] = hl_avg - (multiplier * df['atr'])
    
    # Initialize SuperTrend
    df['supertrend'] = 0.0
    df['supertrend_direction'] = 1  # 1 = uptrend, -1 = downtrend
    
    for i in range(1, len(df)):
        # Adjust bands based on previous values
        if df.loc[i, 'lower_band'] > df.loc[i-1, 'lower_band'] or df.loc[i-1, 'close'] < df.loc[i-1, 'lower_band']:
            df.loc[i, 'lower_band'] = df.loc[i, 'lower_band']
        else:
            df.loc[i, 'lower_band'] = df.loc[i-1, 'lower_band']
            
        if df.loc[i, 'upper_band'] < df.loc[i-1, 'upper_band'] or df.loc[i-1, 'close'] > df.loc[i-1, 'upper_band']:
            df.loc[i, 'upper_band'] = df.loc[i, 'upper_band']
        else:
            df.loc[i, 'upper_band'] = df.loc[i-1, 'upper_band']
        
        # Determine trend
        if df.loc[i, 'close'] <= df.loc[i, 'upper_band']:
            df.loc[i, 'supertrend'] = df.loc[i, 'upper_band']
            df.loc[i, 'supertrend_direction'] = -1
        else:
            df.loc[i, 'supertrend'] = df.loc[i, 'lower_band']
            df.loc[i, 'supertrend_direction'] = 1
    
    return df

def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """Calculate KDJ indicator."""
    # Calculate RSV (Raw Stochastic Value)
    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()
    df['rsv'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    
    # Calculate K, D, J
    df['kdj_k'] = df['rsv'].ewm(span=m1, adjust=False).mean()
    df['kdj_d'] = df['kdj_k'].ewm(span=m2, adjust=False).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    
    return df

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ADX indicator."""
    # Calculate directional movement
    df['high_diff'] = df['high'].diff()
    df['low_diff'] = -df['low'].diff()
    
    df['plus_dm'] = np.where(
        (df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0),
        df['high_diff'],
        0
    )
    df['minus_dm'] = np.where(
        (df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0),
        df['low_diff'],
        0
    )
    
    # Calculate ATR
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    
    # Smooth the values
    df['atr_smooth'] = df['tr'].rolling(window=period).mean()
    df['plus_di'] = 100 * (df['plus_dm'].rolling(window=period).mean() / df['atr_smooth'])
    df['minus_di'] = 100 * (df['minus_dm'].rolling(window=period).mean() / df['atr_smooth'])
    
    # Calculate DX and ADX
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].rolling(window=period).mean()
    
    return df

def compare_indicators(tv_df: pd.DataFrame, our_df: pd.DataFrame, symbol: str):
    """Compare TradingView indicators with our calculations."""
    print(f"\n{'='*80}")
    print(f"DATA QUALITY COMPARISON: {symbol}")
    print(f"{'='*80}\n")
    
    # Merge on date
    tv_df['date'] = tv_df['time'].dt.date
    our_df['date'] = our_df['date'].dt.date
    
    merged = pd.merge(
        tv_df,
        our_df,
        on='date',
        suffixes=('_tv', '_our'),
        how='inner'
    )
    
    if len(merged) == 0:
        print(f"❌ No overlapping dates found for {symbol}")
        return
    
    print(f"📊 Comparing {len(merged)} days of data")
    print(f"Date range: {merged['date'].min()} to {merged['date'].max()}\n")
    
    # 1. OHLCV Comparison
    print("1️⃣  OHLCV DATA VALIDATION")
    print("-" * 80)
    
    ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
    ohlcv_match = True
    
    for col in ohlcv_cols:
        tv_col = f"{col}_tv" if f"{col}_tv" in merged.columns else col
        our_col = f"{col}_our" if f"{col}_our" in merged.columns else col
        
        if tv_col in merged.columns and our_col in merged.columns:
            diff = abs(merged[tv_col] - merged[our_col])
            max_diff = diff.max()
            mean_diff = diff.mean()
            pct_diff = (diff / merged[tv_col] * 100).mean()
            
            status = "✅" if pct_diff < 0.1 else "⚠️" if pct_diff < 1 else "❌"
            print(f"{status} {col.upper():8} - Max diff: ${max_diff:.4f}, Avg diff: ${mean_diff:.4f} ({pct_diff:.3f}%)")
            
            if pct_diff >= 0.1:
                ohlcv_match = False
    
    print(f"\n{'✅ OHLCV data matches TradingView' if ohlcv_match else '⚠️  OHLCV data has discrepancies'}\n")
    
    # 2. SuperTrend Comparison
    print("2️⃣  SUPERTREND INDICATOR")
    print("-" * 80)
    
    if 'supertrend_stop' in merged.columns:
        # Calculate our SuperTrend
        calc_df = merged[['date', 'open_tv', 'high_tv', 'low_tv', 'close_tv', 'volume_tv']].copy()
        calc_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        calc_df = calculate_supertrend(calc_df)
        
        # Compare
        tv_st = merged['supertrend_stop'].values
        our_st = calc_df['supertrend'].values
        
        valid_idx = ~(np.isnan(tv_st) | np.isnan(our_st))
        if valid_idx.sum() > 0:
            diff = abs(tv_st[valid_idx] - our_st[valid_idx])
            max_diff = diff.max()
            mean_diff = diff.mean()
            pct_diff = (diff / tv_st[valid_idx] * 100).mean()
            
            status = "✅" if pct_diff < 1 else "⚠️" if pct_diff < 5 else "❌"
            print(f"{status} SuperTrend - Max diff: ${max_diff:.4f}, Avg diff: ${mean_diff:.4f} ({pct_diff:.3f}%)")
            
            # Show sample values
            print(f"\n   Sample comparison (last 5 days):")
            for i in range(max(0, len(merged)-5), len(merged)):
                if valid_idx[i]:
                    print(f"   {merged.iloc[i]['date']}: TV=${tv_st[i]:.2f}, Calc=${our_st[i]:.2f}, Diff=${abs(tv_st[i]-our_st[i]):.2f}")
    
    print()
    
    # 3. KDJ Comparison
    print("3️⃣  KDJ INDICATOR")
    print("-" * 80)
    
    if all(col in merged.columns for col in ['kdj_k', 'kdj_d', 'kdj_j']):
        # Calculate our KDJ
        calc_df = merged[['date', 'open_tv', 'high_tv', 'low_tv', 'close_tv', 'volume_tv']].copy()
        calc_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        calc_df = calculate_kdj(calc_df)
        
        for indicator in ['k', 'd', 'j']:
            tv_col = f'kdj_{indicator}'
            calc_col = f'kdj_{indicator}'
            
            tv_vals = merged[tv_col].values
            our_vals = calc_df[calc_col].values
            
            valid_idx = ~(np.isnan(tv_vals) | np.isnan(our_vals))
            if valid_idx.sum() > 0:
                diff = abs(tv_vals[valid_idx] - our_vals[valid_idx])
                max_diff = diff.max()
                mean_diff = diff.mean()
                
                status = "✅" if mean_diff < 2 else "⚠️" if mean_diff < 5 else "❌"
                print(f"{status} KDJ-{indicator.upper()} - Max diff: {max_diff:.2f}, Avg diff: {mean_diff:.2f}")
    
    print()
    
    # 4. ADX Comparison
    print("4️⃣  ADX INDICATOR")
    print("-" * 80)
    
    if 'adx_current' in merged.columns:
        # Calculate our ADX
        calc_df = merged[['date', 'open_tv', 'high_tv', 'low_tv', 'close_tv', 'volume_tv']].copy()
        calc_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        calc_df = calculate_adx(calc_df)
        
        tv_adx = merged['adx_current'].values
        our_adx = calc_df['adx'].values
        
        valid_idx = ~(np.isnan(tv_adx) | np.isnan(our_adx))
        if valid_idx.sum() > 0:
            diff = abs(tv_adx[valid_idx] - our_adx[valid_idx])
            max_diff = diff.max()
            mean_diff = diff.mean()
            
            status = "✅" if mean_diff < 2 else "⚠️" if mean_diff < 5 else "❌"
            print(f"{status} ADX - Max diff: {max_diff:.2f}, Avg diff: {mean_diff:.2f}")
            
            # Show sample values
            print(f"\n   Sample comparison (last 5 days):")
            for i in range(max(0, len(merged)-5), len(merged)):
                if valid_idx[i]:
                    print(f"   {merged.iloc[i]['date']}: TV={tv_adx[i]:.2f}, Calc={our_adx[i]:.2f}, Diff={abs(tv_adx[i]-our_adx[i]):.2f}")
    
    print()
    
    # 5. Data Quality Summary
    print("5️⃣  DATA QUALITY SUMMARY")
    print("-" * 80)
    
    # Check for NaN values
    tv_nan_pct = (merged[['close_tv', 'supertrend_stop', 'kdj_k', 'adx_current']].isna().sum() / len(merged) * 100)
    print(f"TradingView NaN%: Close={tv_nan_pct['close_tv']:.1f}%, ST={tv_nan_pct['supertrend_stop']:.1f}%, KDJ={tv_nan_pct['kdj_k']:.1f}%, ADX={tv_nan_pct['adx_current']:.1f}%")
    
    if 'close_our' in merged.columns:
        our_nan_pct = (merged['close_our'].isna().sum() / len(merged) * 100)
        print(f"Our Data NaN%: Close={our_nan_pct:.1f}%")
    
    print(f"\n{'='*80}\n")

def main():
    """Main comparison function."""
    # Load TradingView data
    print("Loading TradingView exports...")
    aapl_tv = load_tradingview_data("BATS_AAPL, 1D_60720.csv")
    nvda_tv = load_tradingview_data("BATS_NVDA, 1D_67f84.csv")
    
    print(f"✅ Loaded AAPL: {len(aapl_tv)} days ({aapl_tv['time'].min()} to {aapl_tv['time'].max()})")
    print(f"✅ Loaded NVDA: {len(nvda_tv)} days ({nvda_tv['time'].min()} to {nvda_tv['time'].max()})")
    
    # Fetch our data
    print("\nFetching our data from Supabase...")
    aapl_our = fetch_our_data("AAPL", "2024-10-01", "2025-04-30")
    nvda_our = fetch_our_data("NVDA", "2024-10-01", "2025-04-30")
    
    if not aapl_our.empty:
        print(f"✅ Loaded our AAPL: {len(aapl_our)} days")
    if not nvda_our.empty:
        print(f"✅ Loaded our NVDA: {len(nvda_our)} days")
    
    # Compare
    if not aapl_our.empty:
        compare_indicators(aapl_tv, aapl_our, "AAPL")
    
    if not nvda_our.empty:
        compare_indicators(nvda_tv, nvda_our, "NVDA")

if __name__ == "__main__":
    main()
