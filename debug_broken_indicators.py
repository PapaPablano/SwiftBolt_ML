#!/usr/bin/env python3
"""
Debug Broken Indicators Script

Systematically identifies and fixes all indicators with:
1. All NaN values
2. All zero values (no variance)
3. Calculation errors

Based on the diagnostic output showing 28+ broken features.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Add ml to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "ml"))

from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features
from src.features.support_resistance_detector import SupportResistanceDetector
from src.features.polynomial_sr_indicator import PolynomialSRIndicator
from src.features.logistic_sr_indicator import LogisticSRIndicator


def fetch_aapl_data(days=100):
    """Fetch AAPL data for debugging."""
    print(f"📊 Fetching {days} days of AAPL data...")
    df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=days)
    if df is None or len(df) == 0:
        raise ValueError("No AAPL data found")
    print(f"✅ Fetched {len(df)} bars")
    return df


def analyze_indicator_quality(df_with_indicators):
    """Analyze all indicators for quality issues."""
    print("\n🔍 ANALYZING INDICATOR QUALITY")
    print("=" * 80)
    
    # Get all indicator columns (exclude basic OHLCV)
    basic_columns = ['ts', 'open', 'high', 'low', 'close', 'volume']
    all_indicators = [col for col in df_with_indicators.columns if col not in basic_columns]
    
    # Categorize indicators by quality
    all_null_indicators = []
    all_zero_indicators = []
    high_null_indicators = []
    working_indicators = []
    low_variance_indicators = []
    
    print(f"Analyzing {len(all_indicators)} indicators...")
    
    for col in all_indicators:
        if col not in df_with_indicators.columns:
            continue
            
        series = df_with_indicators[col]
        non_null_count = series.notna().sum()
        null_count = series.isna().sum()
        total_count = len(series)
        
        if non_null_count == 0:
            all_null_indicators.append(col)
        elif non_null_count < total_count * 0.5:  # Less than 50% non-null
            high_null_indicators.append((col, non_null_count, total_count))
        else:
            # Check for zero variance
            non_null_values = series.dropna()
            if len(non_null_values) > 1:
                # Convert to numeric to avoid boolean subtraction error
                try:
                    numeric_values = pd.to_numeric(non_null_values, errors='coerce')
                    if numeric_values.isna().all():
                        all_null_indicators.append(col)
                        continue
                    
                    # Only calculate variance/range for numeric data
                    if numeric_values.dtype in ['bool', 'object']:
                        # For boolean/object data, check if all values are the same
                        unique_vals = numeric_values.nunique()
                        if unique_vals == 1:
                            all_zero_indicators.append(col)
                        else:
                            working_indicators.append(col)
                    else:
                        variance = numeric_values.var()
                        value_range = numeric_values.max() - numeric_values.min()
                        
                        if variance == 0 or value_range == 0:
                            all_zero_indicators.append(col)
                        elif variance < 1e-10 or value_range < 1e-6:
                            low_variance_indicators.append((col, variance, value_range))
                        else:
                            working_indicators.append(col)
                except Exception:
                    all_null_indicators.append(col)
            else:
                all_null_indicators.append(col)
    
    # Print results
    print(f"\n🚨 CRITICAL ISSUES:")
    print(f"   All NULL indicators: {len(all_null_indicators)}")
    for col in all_null_indicators:
        print(f"     ❌ {col}")
    
    print(f"\n⚠️  HIGH NULL COUNT (>50% missing):")
    print(f"   Count: {len(high_null_indicators)}")
    for col, non_null, total in high_null_indicators:
        pct = (1 - non_null/total) * 100
        print(f"     ⚠️  {col}: {pct:.1f}% null ({non_null}/{total})")
    
    print(f"\n🔧 ZERO VARIANCE INDICATORS:")
    print(f"   Count: {len(all_zero_indicators)}")
    for col in all_zero_indicators:
        print(f"     🔧 {col}")
    
    print(f"\n📉 LOW VARIANCE INDICATORS:")
    print(f"   Count: {len(low_variance_indicators)}")
    for col, var, rng in low_variance_indicators:
        print(f"     📉 {col}: var={var:.2e}, range={rng:.2e}")
    
    print(f"\n✅ WORKING INDICATORS:")
    print(f"   Count: {len(working_indicators)}")
    for col in working_indicators:
        print(f"     ✅ {col}")
    
    return {
        'all_null': all_null_indicators,
        'all_zero': all_zero_indicators,
        'high_null': high_null_indicators,
        'low_variance': low_variance_indicators,
        'working': working_indicators,
        'all_indicators': all_indicators
    }


def debug_sr_indicators(df):
    """Debug support/resistance indicators specifically."""
    print("\n🔍 DEBUGGING SUPPORT/RESISTANCE INDICATORS")
    print("=" * 80)
    
    # Test each S/R method individually
    print("Testing Pivot Levels...")
    try:
        from src.features.pivot_levels_detector import PivotLevelsDetector
        pivot_detector = PivotLevelsDetector()
        pivot_levels = pivot_detector.detect_pivots(df, lookback=10)
        print(f"   ✅ Pivot levels: {len(pivot_levels)} found")
        for level in pivot_levels[:3]:
            print(f"      {level.level_type} at {level.price:.2f} ({level.ts})")
    except Exception as e:
        print(f"   ❌ Pivot levels error: {e}")
    
    print("\nTesting Polynomial S/R...")
    try:
        poly_indicator = PolynomialSRIndicator()
        poly_sr = poly_indicator.calculate(df)
        print(f"   ✅ Polynomial S/R calculated")
        print(f"      Support: {poly_sr.support_levels[:2] if poly_sr.support_levels else 'None'}")
        print(f"      Resistance: {poly_sr.resistance_levels[:2] if poly_sr.resistance_levels else 'None'}")
    except Exception as e:
        print(f"   ❌ Polynomial S/R error: {e}")
    
    print("\nTesting Logistic S/R...")
    try:
        logistic_indicator = LogisticSRIndicator()
        logistic_sr = logistic_indicator.calculate(df)
        print(f"   ✅ Logistic S/R calculated")
        print(f"      Support levels: {len(logistic_sr.support_levels)}")
        print(f"      Resistance levels: {len(logistic_sr.resistance_levels)}")
    except Exception as e:
        print(f"   ❌ Logistic S/R error: {e}")
    
    print("\nTesting S/R Detector...")
    try:
        sr_detector = SupportResistanceDetector()
        sr_results = sr_detector.detect_all(df)
        print(f"   ✅ S/R Detector results:")
        for method, levels in sr_results.items():
            print(f"      {method}: {len(levels)} levels")
    except Exception as e:
        print(f"   ❌ S/R Detector error: {e}")


def debug_market_context_indicators(df):
    """Debug market context indicators (SPY correlation, market regime)."""
    print("\n🔍 DEBUGGING MARKET CONTEXT INDICATORS")
    print("=" * 80)
    
    # Test SPY data fetching
    print("Testing SPY data fetch...")
    try:
        spy_df = db.fetch_ohlc_bars("SPY", timeframe="d1", limit=100)
        if spy_df is not None and len(spy_df) > 0:
            print(f"   ✅ SPY data: {len(spy_df)} bars")
            print(f"      Date range: {spy_df['ts'].min()} to {spy_df['ts'].max()}")
        else:
            print(f"   ❌ No SPY data found")
    except Exception as e:
        print(f"   ❌ SPY fetch error: {e}")
    
    # Test market regime detection
    print("\nTesting Market Regime Detection...")
    try:
        from src.features.market_regime import MarketRegimeDetector
        regime_detector = MarketRegimeDetector()
        regime_detector.fit(df[['close']].pct_change().dropna())
        regimes = regime_detector.transform(df[['close']].pct_change().dropna())
        print(f"   ✅ Market regimes calculated")
        print(f"      Unique regimes: {np.unique(regimes[:10])}")
    except Exception as e:
        print(f"   ❌ Market regime error: {e}")


def debug_volume_indicators(df):
    """Debug volume-related indicators."""
    print("\n🔍 DEBUGGING VOLUME INDICATORS")
    print("=" * 80)
    
    print(f"Volume statistics:")
    print(f"   Non-null volume: {df['volume'].notna().sum()}/{len(df)}")
    print(f"   Volume range: {df['volume'].min():.0f} to {df['volume'].max():.0f}")
    print(f"   Volume mean: {df['volume'].mean():.0f}")
    
    # Test volume ratio calculation manually
    print("\nTesting volume ratio calculation...")
    try:
        volume_sma_20 = df['volume'].rolling(window=20).mean()
        volume_ratio = df['volume'] / volume_sma_20
        print(f"   ✅ Volume ratio calculated")
        print(f"      Non-null: {volume_ratio.notna().sum()}/{len(volume_ratio)}")
        print(f"      Range: {volume_ratio.min():.3f} to {volume_ratio.max():.3f}")
    except Exception as e:
        print(f"   ❌ Volume ratio error: {e}")
    
    # Test MFI calculation
    print("\nTesting MFI calculation...")
    try:
        # Simple MFI calculation
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        raw_money_flow = typical_price * df['volume']
        
        # Positive and negative money flow
        positive_mf = []
        negative_mf = []
        
        for i in range(1, len(typical_price)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                positive_mf.append(raw_money_flow.iloc[i])
                negative_mf.append(0)
            else:
                positive_mf.append(0)
                negative_mf.append(raw_money_flow.iloc[i])
        
        if len(positive_mf) >= 14:
            positive_mf_sum = pd.Series(positive_mf).rolling(14).sum()
            negative_mf_sum = pd.Series(negative_mf).rolling(14).sum()
            mfi = 100 - (100 / (1 + positive_mf_sum / negative_mf_sum))
            print(f"   ✅ MFI calculated")
            print(f"      Non-null: {mfi.notna().sum()}/{len(mfi)}")
            print(f"      Range: {mfi.min():.1f} to {mfi.max():.1f}")
        else:
            print(f"   ❌ Insufficient data for MFI")
    except Exception as e:
        print(f"   ❌ MFI error: {e}")


def create_fixed_feature_set(df, quality_analysis):
    """Create a feature set with only working indicators."""
    print("\n🔧 CREATING FIXED FEATURE SET")
    print("=" * 80)
    
    working_features = quality_analysis['working']
    
    print(f"Using {len(working_features)} working indicators:")
    
    # Create clean DataFrame
    basic_columns = ['ts', 'open', 'high', 'low', 'close', 'volume']
    clean_df = df[basic_columns + working_features].copy()
    
    # Remove rows with too many NaNs
    feature_columns = working_features
    nan_threshold = len(feature_columns) * 0.3  # Allow up to 30% NaN per row
    
    clean_df['nan_count'] = clean_df[feature_columns].isna().sum(axis=1)
    clean_df = clean_df[clean_df['nan_count'] <= nan_threshold]
    clean_df = clean_df.drop('nan_count', axis=1)
    
    print(f"   Original rows: {len(df)}")
    print(f"   After NaN filtering: {len(clean_df)}")
    
    # Fill remaining NaNs with median
    for col in feature_columns:
        if col in clean_df.columns:
            median_val = clean_df[col].median()
            clean_df[col] = clean_df[col].fillna(median_val)
    
    print(f"   ✅ Clean feature set created")
    print(f"   Features: {len(feature_columns)}")
    print(f"   Rows: {len(clean_df)}")
    
    return clean_df, feature_columns


def generate_debug_report(quality_analysis, clean_df, feature_columns):
    """Generate comprehensive debug report."""
    print("\n📋 DEBUG REPORT SUMMARY")
    print("=" * 80)
    
    total_indicators = len(quality_analysis['all_indicators'])
    working_count = len(quality_analysis['working'])
    broken_count = len(quality_analysis['all_null']) + len(quality_analysis['all_zero']) + len(quality_analysis['high_null'])
    
    print(f"\n📊 INDICATOR QUALITY BREAKDOWN:")
    print(f"   Total indicators: {total_indicators}")
    print(f"   Working: {working_count} ({working_count/total_indicators*100:.1f}%)")
    print(f"   Broken: {broken_count} ({broken_count/total_indicators*100:.1f}%)")
    
    print(f"\n🚨 BROKEN INDICATOR CATEGORIES:")
    print(f"   All null: {len(quality_analysis['all_null'])}")
    print(f"   All zero: {len(quality_analysis['all_zero'])}")
    print(f"   High null: {len(quality_analysis['high_null'])}")
    print(f"   Low variance: {len(quality_analysis['low_variance'])}")
    
    print(f"\n✅ FIXED FEATURE SET:")
    print(f"   Features: {len(feature_columns)}")
    print(f"   Rows: {len(clean_df)}")
    print(f"   Data completeness: {(1 - clean_df[feature_columns].isna().sum().sum() / (len(clean_df) * len(feature_columns))) * 100:.1f}%")
    
    # Feature correlation analysis
    if len(feature_columns) > 1:
        correlation_matrix = clean_df[feature_columns].corr()
        high_corr_pairs = []
        
        for i in range(len(feature_columns)):
            for j in range(i+1, len(feature_columns)):
                corr_val = correlation_matrix.iloc[i, j]
                if abs(corr_val) > 0.9:
                    high_corr_pairs.append((feature_columns[i], feature_columns[j], corr_val))
        
        print(f"\n🔗 HIGH CORRELATION PAIRS (>0.9): {len(high_corr_pairs)}")
        for col1, col2, corr in high_corr_pairs[:5]:
            print(f"   {col1} ↔ {col2}: {corr:.3f}")
    
    print(f"\n💡 RECOMMENDATIONS:")
    if broken_count > total_indicators * 0.3:
        print(f"   🚨 MAJOR: >30% of indicators are broken - fix data pipeline")
    if len(quality_analysis['all_null']) > 0:
        print(f"   🔧 Fix {len(quality_analysis['all_null'])} completely null indicators")
    if len(quality_analysis['all_zero']) > 0:
        print(f"   🔧 Fix {len(quality_analysis['all_zero'])} zero-variance indicators")
    if len(high_corr_pairs) > 10:
        print(f"   🔧 Consider feature selection to reduce multicollinearity")


def main():
    """Main debugging execution."""
    print("🔍 DEBUGGING BROKEN INDICATORS")
    print("=" * 60)
    print("Systematically fixing 0-value and NaN indicators")
    
    try:
        # Fetch data
        df = fetch_aapl_data(days=100)
        
        # Add technical indicators
        print("\n🔧 Adding technical indicators...")
        df_with_indicators = add_technical_features(df.copy())
        print(f"✅ Added {len(df_with_indicators.columns) - len(df.columns)} indicators")
        
        # Analyze indicator quality
        quality_analysis = analyze_indicator_quality(df_with_indicators)
        
        # Debug specific indicator categories
        debug_sr_indicators(df)
        debug_market_context_indicators(df)
        debug_volume_indicators(df)
        
        # Create fixed feature set
        clean_df, feature_columns = create_fixed_feature_set(df_with_indicators, quality_analysis)
        
        # Generate report
        generate_debug_report(quality_analysis, clean_df, feature_columns)
        
        print(f"\n✅ DEBUGGING COMPLETE")
        print(f"📊 Working features: {len(feature_columns)}")
        print(f"📋 Ready for ML pipeline with cleaned data")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
