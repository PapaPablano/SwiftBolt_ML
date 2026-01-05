#!/usr/bin/env python3
"""
Diagnose and reverse-engineer TradingView indicator parameters.
Find the exact parameters that match TradingView's calculations.
"""

import pandas as pd
import numpy as np
from itertools import product


def load_tradingview_data(filepath: str) -> pd.DataFrame:
    """Load TradingView CSV export."""
    df = pd.read_csv(filepath)
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
    return df.sort_values('time').reset_index(drop=True)


def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculate ATR with various smoothing methods."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr = pd.DataFrame({
        'hl': high - low,
        'hc': abs(high - close.shift(1)),
        'lc': abs(low - close.shift(1))
    }).max(axis=1)
    
    # Try Wilder's smoothing (EMA with alpha = 1/period)
    atr_wilder = tr.ewm(alpha=1/period, adjust=False).mean()
    
    # Try simple moving average
    atr_sma = tr.rolling(window=period).mean()
    
    return atr_wilder, atr_sma


def test_supertrend_params(df: pd.DataFrame, tv_st: pd.Series):
    """Test various SuperTrend parameters to find best match."""
    print("\n" + "="*80)
    print("SUPERTREND PARAMETER SEARCH")
    print("="*80)
    
    best_match = None
    best_error = float('inf')
    
    # Test parameter ranges
    periods = [7, 10, 14, 20]
    multipliers = [2.0, 2.5, 3.0, 3.5, 4.0]
    
    for period, mult in product(periods, multipliers):
        # Calculate ATR with Wilder's smoothing
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.DataFrame({
            'hl': high - low,
            'hc': abs(high - close.shift(1)),
            'lc': abs(low - close.shift(1))
        }).max(axis=1)
        
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        
        # Calculate bands
        hl_avg = (high + low) / 2
        upper_band = hl_avg + (mult * atr)
        lower_band = hl_avg - (mult * atr)
        
        # Calculate SuperTrend
        supertrend = pd.Series(0.0, index=df.index)
        in_uptrend = pd.Series(True, index=df.index)
        
        for i in range(1, len(df)):
            # Adjust bands
            if lower_band.iloc[i] > lower_band.iloc[i-1] or close.iloc[i-1] < lower_band.iloc[i-1]:
                final_lower = lower_band.iloc[i]
            else:
                final_lower = lower_band.iloc[i-1]
            
            if upper_band.iloc[i] < upper_band.iloc[i-1] or close.iloc[i-1] > upper_band.iloc[i-1]:
                final_upper = upper_band.iloc[i]
            else:
                final_upper = upper_band.iloc[i-1]
            
            # Determine trend
            if close.iloc[i] > final_upper:
                supertrend.iloc[i] = final_lower
                in_uptrend.iloc[i] = True
            elif close.iloc[i] < final_lower:
                supertrend.iloc[i] = final_upper
                in_uptrend.iloc[i] = False
            else:
                supertrend.iloc[i] = final_upper if in_uptrend.iloc[i-1] else final_lower
                in_uptrend.iloc[i] = in_uptrend.iloc[i-1]
        
        # Compare with TradingView
        valid_idx = ~(tv_st.isna() | supertrend.isna())
        if valid_idx.sum() > 20:
            error = abs(tv_st[valid_idx] - supertrend[valid_idx]).mean()
            
            if error < best_error:
                best_error = error
                best_match = (period, mult, error)
                
                if error < 1.0:  # Good match
                    print(f"✅ Period={period:2d}, Mult={mult:.1f} → Error=${error:.4f}")
    
    if best_match:
        print(f"\n🎯 Best match: Period={best_match[0]}, Multiplier={best_match[1]:.1f}")
        print(f"   Average error: ${best_match[2]:.4f}")
    
    return best_match


def test_kdj_params(df: pd.DataFrame, tv_k: pd.Series, tv_d: pd.Series, tv_j: pd.Series):
    """Test various KDJ parameters to find best match."""
    print("\n" + "="*80)
    print("KDJ PARAMETER SEARCH")
    print("="*80)
    
    best_match = None
    best_error = float('inf')
    
    # Test parameter ranges
    n_values = [5, 9, 14, 20]
    m1_values = [3, 5, 9]
    m2_values = [3, 5, 9]
    
    for n, m1, m2 in product(n_values, m1_values, m2_values):
        # Calculate RSV
        low_min = df['low'].rolling(window=n).min()
        high_max = df['high'].rolling(window=n).max()
        rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
        
        # Calculate K, D, J with EMA
        k = rsv.ewm(span=m1, adjust=False).mean()
        d = k.ewm(span=m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        # Compare with TradingView
        valid_idx = ~(tv_k.isna() | k.isna())
        if valid_idx.sum() > 20:
            k_error = abs(tv_k[valid_idx] - k[valid_idx]).mean()
            d_error = abs(tv_d[valid_idx] - d[valid_idx]).mean()
            j_error = abs(tv_j[valid_idx] - j[valid_idx]).mean()
            total_error = k_error + d_error + j_error
            
            if total_error < best_error:
                best_error = total_error
                best_match = (n, m1, m2, k_error, d_error, j_error)
                
                if total_error < 10.0:  # Good match
                    print(f"✅ n={n:2d}, m1={m1}, m2={m2} → K_err={k_error:.2f}, D_err={d_error:.2f}, J_err={j_error:.2f}")
    
    if best_match:
        print(f"\n🎯 Best match: n={best_match[0]}, m1={best_match[1]}, m2={best_match[2]}")
        print(f"   K error: {best_match[3]:.2f}")
        print(f"   D error: {best_match[4]:.2f}")
        print(f"   J error: {best_match[5]:.2f}")
    
    return best_match


def test_adx_params(df: pd.DataFrame, tv_adx: pd.Series):
    """Test various ADX parameters to find best match."""
    print("\n" + "="*80)
    print("ADX PARAMETER SEARCH")
    print("="*80)
    
    best_match = None
    best_error = float('inf')
    
    # Test parameter ranges
    periods = [7, 10, 14, 20, 25]
    
    for period in periods:
        # Calculate directional movement
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        plus_dm = pd.Series(0.0, index=df.index)
        minus_dm = pd.Series(0.0, index=df.index)
        
        plus_dm[(high_diff > low_diff) & (high_diff > 0)] = high_diff
        minus_dm[(low_diff > high_diff) & (low_diff > 0)] = low_diff
        
        # Calculate True Range
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.DataFrame({
            'hl': high - low,
            'hc': abs(high - close.shift(1)),
            'lc': abs(low - close.shift(1))
        }).max(axis=1)
        
        # Try Wilder's smoothing
        atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di_smooth = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth
        minus_di_smooth = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth
        
        dx = 100 * abs(plus_di_smooth - minus_di_smooth) / (plus_di_smooth + minus_di_smooth)
        adx_wilder = dx.ewm(alpha=1/period, adjust=False).mean()
        
        # Try SMA smoothing
        atr_sma = tr.rolling(window=period).mean()
        plus_di_sma = 100 * plus_dm.rolling(window=period).mean() / atr_sma
        minus_di_sma = 100 * minus_dm.rolling(window=period).mean() / atr_sma
        
        dx_sma = 100 * abs(plus_di_sma - minus_di_sma) / (plus_di_sma + minus_di_sma)
        adx_sma = dx_sma.rolling(window=period).mean()
        
        # Compare both methods
        for method, adx_calc in [('Wilder', adx_wilder), ('SMA', adx_sma)]:
            valid_idx = ~(tv_adx.isna() | adx_calc.isna())
            if valid_idx.sum() > 20:
                error = abs(tv_adx[valid_idx] - adx_calc[valid_idx]).mean()
                
                if error < best_error:
                    best_error = error
                    best_match = (period, method, error)
                    
                    if error < 3.0:  # Good match
                        print(f"✅ Period={period:2d}, Method={method:6s} → Error={error:.2f}")
    
    if best_match:
        print(f"\n🎯 Best match: Period={best_match[0]}, Method={best_match[1]}")
        print(f"   Average error: {best_match[2]:.2f}")
    
    return best_match


def main():
    """Run diagnostic on both symbols."""
    print("Loading TradingView data...")
    aapl = load_tradingview_data("BATS_AAPL, 1D_60720.csv")
    nvda = load_tradingview_data("BATS_NVDA, 1D_67f84.csv")
    
    print(f"✅ AAPL: {len(aapl)} days")
    print(f"✅ NVDA: {len(nvda)} days")
    
    # Diagnose AAPL
    print("\n" + "="*80)
    print("DIAGNOSING AAPL")
    print("="*80)
    
    aapl_st = test_supertrend_params(aapl, aapl['supertrend_stop'])
    aapl_kdj = test_kdj_params(aapl, aapl['kdj_k'], aapl['kdj_d'], aapl['kdj_j'])
    aapl_adx = test_adx_params(aapl, aapl['adx_current'])
    
    # Diagnose NVDA
    print("\n" + "="*80)
    print("DIAGNOSING NVDA")
    print("="*80)
    
    nvda_st = test_supertrend_params(nvda, nvda['supertrend_stop'])
    nvda_kdj = test_kdj_params(nvda, nvda['kdj_k'], nvda['kdj_d'], nvda['kdj_j'])
    nvda_adx = test_adx_params(nvda, nvda['adx_current'])
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)
    
    if aapl_st and nvda_st:
        if aapl_st[0] == nvda_st[0] and aapl_st[1] == nvda_st[1]:
            print(f"\n✅ SuperTrend: Period={aapl_st[0]}, Multiplier={aapl_st[1]:.1f}")
        else:
            print(f"\n⚠️  SuperTrend parameters differ between symbols")
            print(f"   AAPL: Period={aapl_st[0]}, Multiplier={aapl_st[1]:.1f}")
            print(f"   NVDA: Period={nvda_st[0]}, Multiplier={nvda_st[1]:.1f}")
    
    if aapl_kdj and nvda_kdj:
        if aapl_kdj[:3] == nvda_kdj[:3]:
            print(f"\n✅ KDJ: n={aapl_kdj[0]}, m1={aapl_kdj[1]}, m2={aapl_kdj[2]}")
        else:
            print(f"\n⚠️  KDJ parameters differ between symbols")
            print(f"   AAPL: n={aapl_kdj[0]}, m1={aapl_kdj[1]}, m2={aapl_kdj[2]}")
            print(f"   NVDA: n={nvda_kdj[0]}, m1={nvda_kdj[1]}, m2={nvda_kdj[2]}")
    
    if aapl_adx and nvda_adx:
        if aapl_adx[0] == nvda_adx[0] and aapl_adx[1] == nvda_adx[1]:
            print(f"\n✅ ADX: Period={aapl_adx[0]}, Method={aapl_adx[1]}")
        else:
            print(f"\n⚠️  ADX parameters differ between symbols")
            print(f"   AAPL: Period={aapl_adx[0]}, Method={aapl_adx[1]}")
            print(f"   NVDA: Period={nvda_adx[0]}, Method={nvda_adx[1]}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
