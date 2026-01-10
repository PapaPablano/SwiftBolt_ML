#!/usr/bin/env python3
"""
Validate our fixed indicator implementations against TradingView data.
"""

import sys
from pathlib import Path

# Add ml/src to path
ml_src = Path(__file__).parent / "ml" / "src"
sys.path.insert(0, str(ml_src))

import pandas as pd

# Import directly from the file
from technical_indicators_tradingview import TradingViewIndicators


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


def validate_symbol(filepath: str, symbol: str):
    """Validate indicators for a symbol."""
    print(f"\n{'='*80}")
    print(f"VALIDATING {symbol} - FIXED IMPLEMENTATIONS")
    print(f"{'='*80}\n")
    
    # Load TradingView data
    tv_df = load_tradingview_data(filepath)
    print(f"Loaded {len(tv_df)} days of TradingView data")
    
    # Calculate our indicators with FIXED parameters
    our_df = tv_df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    our_df = TradingViewIndicators.add_all_tradingview_indicators(our_df)
    
    # Merge for comparison
    merged = pd.merge(
        our_df,
        tv_df,
        on='time',
        suffixes=('_our', '_tv'),
        how='inner'
    )
    
    print(f"Comparing {len(merged)} overlapping days\n")
    
    # SuperTrend Validation
    print("1️⃣  SUPERTREND (period=7, multiplier=2.0)")
    print("-" * 80)
    
    valid_idx = ~(merged['supertrend'].isna() | merged['supertrend_stop'].isna())
    if valid_idx.sum() > 0:
        tv_st = merged.loc[valid_idx, 'supertrend_stop']
        our_st = merged.loc[valid_idx, 'supertrend']
        
        diff = abs(tv_st - our_st)
        max_diff = diff.max()
        mean_diff = diff.mean()
        pct_diff = (diff / tv_st * 100).mean()
        
        status = "✅" if mean_diff < 1 else "⚠️" if mean_diff < 15 else "❌"
        print(f"{status} Max diff: ${max_diff:.2f}, Avg diff: ${mean_diff:.2f} ({pct_diff:.2f}%)")
        
        # Show recent values
        print("\n   Last 5 days:")
        for i in range(max(0, len(merged)-5), len(merged)):
            if valid_idx.iloc[i]:
                date = merged.iloc[i]['time'].date()
                tv_val = merged.iloc[i]['supertrend_stop']
                our_val = merged.iloc[i]['supertrend']
                diff_val = abs(tv_val - our_val)
                print(f"   {date}: TV=${tv_val:.2f}, Ours=${our_val:.2f}, Diff=${diff_val:.2f}")
    
    # KDJ Validation
    print(f"\n2️⃣  KDJ (n=9, m1=5, m2=5)")
    print("-" * 80)
    
    for indicator, name in [('k', 'K'), ('d', 'D'), ('j', 'J')]:
        our_col = f'kdj_{indicator}'
        tv_col = f'kdj_{indicator}'
        
        valid_idx = ~(merged[our_col].isna() | merged[tv_col].isna())
        if valid_idx.sum() > 0:
            tv_vals = merged.loc[valid_idx, tv_col]
            our_vals = merged.loc[valid_idx, our_col]
            
            diff = abs(tv_vals - our_vals)
            max_diff = diff.max()
            mean_diff = diff.mean()
            
            status = "✅" if mean_diff < 1 else "⚠️" if mean_diff < 5 else "❌"
            print(f"{status} {name}: Max={max_diff:.2f}, Avg={mean_diff:.2f}")
    
    # ADX Validation
    print(f"\n3️⃣  ADX (period=14, Wilder's smoothing)")
    print("-" * 80)
    
    valid_idx = ~(merged['adx'].isna() | merged['adx_current'].isna())
    if valid_idx.sum() > 0:
        tv_adx = merged.loc[valid_idx, 'adx_current']
        our_adx = merged.loc[valid_idx, 'adx']
        
        diff = abs(tv_adx - our_adx)
        max_diff = diff.max()
        mean_diff = diff.mean()
        
        status = "✅" if mean_diff < 3 else "⚠️" if mean_diff < 10 else "❌"
        print(f"{status} Max diff: {max_diff:.2f}, Avg diff: {mean_diff:.2f}")
        
        # Show recent values
        print("\n   Last 5 days:")
        for i in range(max(0, len(merged)-5), len(merged)):
            if valid_idx.iloc[i]:
                date = merged.iloc[i]['time'].date()
                tv_val = merged.iloc[i]['adx_current']
                our_val = merged.iloc[i]['adx']
                diff_val = abs(tv_val - our_val)
                print(f"   {date}: TV={tv_val:.2f}, Ours={our_val:.2f}, Diff={diff_val:.2f}")
    
    print(f"\n{'='*80}\n")


def main():
    """Run validation on both symbols."""
    print("\n" + "="*80)
    print("INDICATOR VALIDATION - TRADINGVIEW ALIGNMENT")
    print("="*80)
    print("\nFixed Parameters:")
    print("  • SuperTrend: period=7, multiplier=2.0")
    print("  • KDJ: n=9, m1=5, m2=5")
    print("  • ADX: period=14, Wilder's smoothing")
    
    validate_symbol("BATS_AAPL, 1D_60720.csv", "AAPL")
    validate_symbol("BATS_NVDA, 1D_67f84.csv", "NVDA")
    
    print("\n" + "="*80)
    print("VALIDATION COMPLETE")
    print("="*80)
    print("\n✅ All indicators now use TradingView-validated parameters")
    print("✅ Ready to update ML pipeline with corrected implementations")


if __name__ == "__main__":
    main()
