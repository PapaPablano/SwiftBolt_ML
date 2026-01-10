#!/usr/bin/env python3
"""
Analyze TradingView exported data quality and indicator calculations.
This validates SuperTrend, KDJ, and ADX indicators from TradingView exports.
"""

import pandas as pd
import numpy as np


def load_tradingview_data(filepath: str) -> pd.DataFrame:
    """Load and parse TradingView CSV export."""
    df = pd.read_csv(filepath)
    
    # Rename columns for clarity
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
    
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    
    return df


def calculate_supertrend(df: pd.DataFrame, period: int = 10, 
                        multiplier: float = 3.0) -> pd.DataFrame:
    """Calculate SuperTrend indicator."""
    df = df.copy()
    
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
    df['calc_supertrend'] = 0.0
    df['supertrend_direction'] = 1
    
    for i in range(1, len(df)):
        # Adjust lower band
        if (df.loc[i, 'lower_band'] > df.loc[i-1, 'lower_band'] or 
            df.loc[i-1, 'close'] < df.loc[i-1, 'lower_band']):
            df.loc[i, 'lower_band'] = df.loc[i, 'lower_band']
        else:
            df.loc[i, 'lower_band'] = df.loc[i-1, 'lower_band']
        
        # Adjust upper band
        if (df.loc[i, 'upper_band'] < df.loc[i-1, 'upper_band'] or 
            df.loc[i-1, 'close'] > df.loc[i-1, 'upper_band']):
            df.loc[i, 'upper_band'] = df.loc[i, 'upper_band']
        else:
            df.loc[i, 'upper_band'] = df.loc[i-1, 'upper_band']
        
        # Determine trend
        if df.loc[i, 'close'] <= df.loc[i, 'upper_band']:
            df.loc[i, 'calc_supertrend'] = df.loc[i, 'upper_band']
            df.loc[i, 'supertrend_direction'] = -1
        else:
            df.loc[i, 'calc_supertrend'] = df.loc[i, 'lower_band']
            df.loc[i, 'supertrend_direction'] = 1
    
    return df


def calculate_kdj(df: pd.DataFrame, n: int = 9, 
                 m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """Calculate KDJ indicator."""
    df = df.copy()
    
    # Calculate RSV
    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()
    df['rsv'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    
    # Calculate K, D, J
    df['calc_kdj_k'] = df['rsv'].ewm(span=m1, adjust=False).mean()
    df['calc_kdj_d'] = df['calc_kdj_k'].ewm(span=m2, adjust=False).mean()
    df['calc_kdj_j'] = 3 * df['calc_kdj_k'] - 2 * df['calc_kdj_d']
    
    return df


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ADX indicator."""
    df = df.copy()
    
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
    df['plus_di'] = 100 * (df['plus_dm'].rolling(window=period).mean() / 
                           df['atr_smooth'])
    df['minus_di'] = 100 * (df['minus_dm'].rolling(window=period).mean() / 
                            df['atr_smooth'])
    
    # Calculate DX and ADX
    df['dx'] = (100 * abs(df['plus_di'] - df['minus_di']) / 
                (df['plus_di'] + df['minus_di']))
    df['calc_adx'] = df['dx'].rolling(window=period).mean()
    
    return df


def analyze_data_quality(df: pd.DataFrame, symbol: str):
    """Analyze data quality and indicator calculations."""
    print(f"\n{'='*80}")
    print(f"DATA QUALITY ANALYSIS: {symbol}")
    print(f"{'='*80}\n")
    
    print(f"📊 Dataset: {len(df)} days")
    print(f"📅 Date range: {df['time'].min()} to {df['time'].max()}\n")
    
    # 1. OHLCV Data Quality
    print("1️⃣  OHLCV DATA QUALITY")
    print("-" * 80)
    
    ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in ohlcv_cols:
        nan_count = df[col].isna().sum()
        nan_pct = (nan_count / len(df)) * 100
        status = "✅" if nan_pct == 0 else "⚠️" if nan_pct < 1 else "❌"
        print(f"{status} {col.upper():8} - NaN: {nan_count:3d} ({nan_pct:5.2f}%)")
    
    # Check for price anomalies
    df['daily_return'] = df['close'].pct_change()
    extreme_moves = (abs(df['daily_return']) > 0.20).sum()
    print(f"\n   Extreme moves (>20%): {extreme_moves}")
    
    # 2. SuperTrend Analysis
    print(f"\n2️⃣  SUPERTREND INDICATOR")
    print("-" * 80)
    
    df_with_st = calculate_supertrend(df)
    
    nan_count = df['supertrend_stop'].isna().sum()
    print(f"TradingView SuperTrend NaN: {nan_count} ({nan_count/len(df)*100:.1f}%)")
    
    # Compare our calculation with TradingView
    valid_idx = ~(df['supertrend_stop'].isna() | 
                  df_with_st['calc_supertrend'].isna())
    
    if valid_idx.sum() > 0:
        tv_st = df.loc[valid_idx, 'supertrend_stop'].values
        calc_st = df_with_st.loc[valid_idx, 'calc_supertrend'].values
        
        diff = abs(tv_st - calc_st)
        max_diff = diff.max()
        mean_diff = diff.mean()
        pct_diff = (diff / tv_st * 100).mean()
        
        status = "✅" if pct_diff < 1 else "⚠️" if pct_diff < 5 else "❌"
        print(f"{status} Calculation match - Max: ${max_diff:.2f}, "
              f"Avg: ${mean_diff:.2f} ({pct_diff:.2f}%)")
        
        # Show recent values
        print(f"\n   Recent values (last 5 days):")
        for i in range(max(0, len(df)-5), len(df)):
            if valid_idx.iloc[i]:
                tv_val = df.iloc[i]['supertrend_stop']
                calc_val = df_with_st.iloc[i]['calc_supertrend']
                diff_val = abs(tv_val - calc_val)
                print(f"   {df.iloc[i]['time'].date()}: "
                      f"TV=${tv_val:.2f}, Calc=${calc_val:.2f}, "
                      f"Diff=${diff_val:.2f}")
    
    # 3. KDJ Analysis
    print(f"\n3️⃣  KDJ INDICATOR")
    print("-" * 80)
    
    df_with_kdj = calculate_kdj(df)
    
    for indicator in ['k', 'd', 'j']:
        tv_col = f'kdj_{indicator}'
        calc_col = f'calc_kdj_{indicator}'
        
        nan_count = df[tv_col].isna().sum()
        print(f"KDJ-{indicator.upper()} NaN: {nan_count} ({nan_count/len(df)*100:.1f}%)")
        
        valid_idx = ~(df[tv_col].isna() | df_with_kdj[calc_col].isna())
        
        if valid_idx.sum() > 0:
            tv_vals = df.loc[valid_idx, tv_col].values
            calc_vals = df_with_kdj.loc[valid_idx, calc_col].values
            
            diff = abs(tv_vals - calc_vals)
            max_diff = diff.max()
            mean_diff = diff.mean()
            
            status = "✅" if mean_diff < 2 else "⚠️" if mean_diff < 5 else "❌"
            print(f"  {status} Match - Max: {max_diff:.2f}, Avg: {mean_diff:.2f}")
    
    # 4. ADX Analysis
    print(f"\n4️⃣  ADX INDICATOR")
    print("-" * 80)
    
    df_with_adx = calculate_adx(df)
    
    nan_count = df['adx_current'].isna().sum()
    print(f"TradingView ADX NaN: {nan_count} ({nan_count/len(df)*100:.1f}%)")
    
    valid_idx = ~(df['adx_current'].isna() | df_with_adx['calc_adx'].isna())
    
    if valid_idx.sum() > 0:
        tv_adx = df.loc[valid_idx, 'adx_current'].values
        calc_adx = df_with_adx.loc[valid_idx, 'calc_adx'].values
        
        diff = abs(tv_adx - calc_adx)
        max_diff = diff.max()
        mean_diff = diff.mean()
        
        status = "✅" if mean_diff < 2 else "⚠️" if mean_diff < 5 else "❌"
        print(f"{status} Calculation match - Max: {max_diff:.2f}, "
              f"Avg: {mean_diff:.2f}")
        
        # Show recent values
        print(f"\n   Recent values (last 5 days):")
        for i in range(max(0, len(df)-5), len(df)):
            if valid_idx.iloc[i]:
                tv_val = df.iloc[i]['adx_current']
                calc_val = df_with_adx.iloc[i]['calc_adx']
                diff_val = abs(tv_val - calc_val)
                print(f"   {df.iloc[i]['time'].date()}: "
                      f"TV={tv_val:.2f}, Calc={calc_val:.2f}, "
                      f"Diff={diff_val:.2f}")
    
    # 5. Summary Statistics
    print(f"\n5️⃣  SUMMARY STATISTICS")
    print("-" * 80)
    
    print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print(f"Avg daily volume: {df['volume'].mean()/1e6:.1f}M")
    print(f"Volatility (std of returns): {df['daily_return'].std()*100:.2f}%")
    
    # Trend analysis
    uptrend_days = (df['close'] > df['supertrend_stop']).sum()
    print(f"\nTrend: {uptrend_days}/{len(df)} days above SuperTrend "
          f"({uptrend_days/len(df)*100:.1f}% bullish)")
    
    # ADX strength
    strong_trend = (df['adx_current'] > 25).sum()
    print(f"Strong trend (ADX>25): {strong_trend}/{len(df)} days "
          f"({strong_trend/len(df)*100:.1f}%)")
    
    print(f"\n{'='*80}\n")


def main():
    """Main analysis function."""
    print("Loading TradingView exports...")
    
    aapl = load_tradingview_data("BATS_AAPL, 1D_60720.csv")
    nvda = load_tradingview_data("BATS_NVDA, 1D_67f84.csv")
    
    print(f"✅ Loaded AAPL: {len(aapl)} days")
    print(f"✅ Loaded NVDA: {len(nvda)} days")
    
    # Analyze both symbols
    analyze_data_quality(aapl, "AAPL")
    analyze_data_quality(nvda, "NVDA")
    
    # Cross-comparison
    print(f"\n{'='*80}")
    print("CROSS-SYMBOL COMPARISON")
    print(f"{'='*80}\n")
    
    print("Correlation Analysis:")
    print(f"Price correlation: {aapl['close'].corr(nvda['close']):.3f}")
    print(f"ADX correlation: {aapl['adx_current'].corr(nvda['adx_current']):.3f}")
    print(f"Volume correlation: {aapl['volume'].corr(nvda['volume']):.3f}")
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
