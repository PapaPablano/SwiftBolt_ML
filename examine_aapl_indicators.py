#!/usr/bin/env python3
"""
Examination Script: AAPL Indicators vs ML Features Pipeline

This script demonstrates how AAPL data flows through your indicator pipeline
into ML features and finally to Supabase storage.

Shows:
1. Raw OHLC data fetch
2. Technical indicator calculation (60+ indicators)
3. Support/Resistance detection (3-method approach)
4. Feature engineering for ML
5. Supabase storage format
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "ml"))

from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features
from src.features.support_resistance_detector import SupportResistanceDetector
from src.strategies.supertrend_ai import SuperTrendAI

def fetch_aapl_recent_data():
    """Fetch most recent AAPL data for examination."""
    print("=" * 80)
    print("1. FETCHING RAW AAPL DATA")
    print("=" * 80)
    
    # Fetch daily data (most recent 10 bars to ensure we have 5 clean bars)
    try:
        df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=10)
        if df is None or len(df) == 0:
            print("❌ No AAPL data found in Supabase")
            return None
            
        print(f"✅ Fetched {len(df)} bars of AAPL daily data")
        print(f"Date range: {df['ts'].min()} to {df['ts'].max()}")
        
        # Show last 5 bars of raw OHLCV data
        print("\n📊 LAST 5 BARS - RAW OHLCV DATA:")
        print("-" * 60)
        recent_5 = df.tail(5)[['ts', 'open', 'high', 'low', 'close', 'volume']]
        for idx, row in recent_5.iterrows():
            print(f"{row['ts']}: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} V={row['volume']:,}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error fetching AAPL data: {e}")
        return None

def examine_technical_indicators(df):
    """Examine technical indicator calculation."""
    print("\n" + "=" * 80)
    print("2. TECHNICAL INDICATORS CALCULATION")
    print("=" * 80)
    
    try:
        # Add all technical indicators
        df_with_indicators = add_technical_features(df.copy())
        
        print(f"✅ Added {len(df_with_indicators.columns) - len(df.columns)} technical indicators")
        print(f"Total columns: {len(df_with_indicators.columns)}")
        
        # Show ALL indicators for last 3 bars (for debugging)
        print("\n📈 ALL INDICATORS - LAST 3 BARS:")
        print("-" * 80)
        
        # Get all indicator columns (exclude basic OHLCV)
        basic_columns = ['ts', 'open', 'high', 'low', 'close', 'volume']
        all_indicators = [col for col in df_with_indicators.columns if col not in basic_columns]
        
        print(f"Total indicators found: {len(all_indicators)}")
        print(f"Indicator columns: {', '.join(all_indicators[:10])}..." if len(all_indicators) > 10 else f"Indicator columns: {', '.join(all_indicators)}")
        
        # Show last 3 bars with all indicators
        recent_indicators = df_with_indicators.tail(3)[['ts', 'close'] + all_indicators]
        
        for idx, row in recent_indicators.iterrows():
            print(f"\n{row['ts']}:")
            print(f"  Price: ${row['close']:.2f}")
            
            # Show all indicator values
            for col in all_indicators:
                if col in row and pd.notna(row[col]):
                    # Format based on value type
                    val = row[col]
                    if abs(val) < 0.01:
                        print(f"  {col:<25}: {val:.6f}")
                    elif abs(val) < 1:
                        print(f"  {col:<25}: {val:.4f}")
                    elif abs(val) < 100:
                        print(f"  {col:<25}: {val:.2f}")
                    else:
                        print(f"  {col:<25}: {val:.1f}")
                elif col in row:
                    print(f"  {col:<25}: NaN")
        
        # Show indicator statistics for debugging
        print(f"\n📊 INDICATOR STATISTICS (for debugging):")
        print("-" * 80)
        
        for col in all_indicators:
            if col in df_with_indicators.columns:
                series = df_with_indicators[col]
                non_null_count = series.notna().sum()
                null_count = series.isna().sum()
                
                if non_null_count > 0:
                    min_val = series.min()
                    max_val = series.max()
                    mean_val = series.mean()
                    std_val = series.std()
                    
                    print(f"  {col:<25}: Count={non_null_count:3d}, Null={null_count:3d}, "
                          f"Range=[{min_val:.4f}, {max_val:.4f}], Mean={mean_val:.4f}, Std={std_val:.4f}")
                else:
                    print(f"  {col:<25}: ❌ ALL NULL VALUES")
        
        return df_with_indicators
        
    except Exception as e:
        print(f"❌ Error calculating technical indicators: {e}")
        return None

def examine_support_resistance(df):
    """Examine S/R detection methods."""
    print("\n" + "=" * 80)
    print("3. SUPPORT/RESISTANCE DETECTION")
    print("=" * 80)
    
    try:
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        
        print("✅ S/R Levels Detected:")
        print(f"  Nearest Support: ${sr_levels.get('nearest_support', 'N/A'):.2f}")
        print(f"  Nearest Resistance: ${sr_levels.get('nearest_resistance', 'N/A'):.2f}")
        print(f"  Support Distance: {sr_levels.get('support_distance_pct', 0):.2%}")
        print(f"  Resistance Distance: {sr_levels.get('resistance_distance_pct', 0):.2%}")
        
        # Show pivot levels
        pivot_levels = sr_levels.get('pivot_levels', {})
        if pivot_levels:
            print("\n🎯 PIVOT LEVELS (Multi-timeframe):")
            print("-" * 40)
            for period, level in pivot_levels.items():
                if isinstance(level, dict):
                    high = level.get('high')
                    low = level.get('low')
                    high_status = level.get('high_status', 'unknown')
                    low_status = level.get('low_status', 'unknown')
                    print(f"  {period}: High=${high:.2f} ({high_status}) | Low=${low:.2f} ({low_status})")
        
        # Show polynomial S/R
        polynomial = sr_levels.get('polynomial', {})
        if polynomial:
            print("\n📐 POLYNOMIAL S/R:")
            print("-" * 30)
            print(f"  Support: ${polynomial.get('support', 'N/A'):.2f}")
            print(f"  Resistance: ${polynomial.get('resistance', 'N/A'):.2f}")
            print(f"  Support Trend: {polynomial.get('supportTrend', 'unknown')}")
            print(f"  Resistance Trend: {polynomial.get('resistanceTrend', 'unknown')}")
            print(f"  Is Diverging: {polynomial.get('isDiverging', False)}")
        
        # Show logistic S/R
        logistic = sr_levels.get('logistic', {})
        if logistic:
            print("\n🤖 LOGISTIC S/R (ML-based):")
            print("-" * 35)
            support_levels = logistic.get('supportLevels', [])
            resistance_levels = logistic.get('resistanceLevels', [])
            
            if support_levels:
                print("  Support Levels:")
                for i, level in enumerate(support_levels[:3]):  # Show top 3
                    prob = level.get('probability', 0)
                    price = level.get('level', 0)
                    print(f"    ${price:.2f} (prob: {prob:.1%})")
            
            if resistance_levels:
                print("  Resistance Levels:")
                for i, level in enumerate(resistance_levels[:3]):  # Show top 3
                    prob = level.get('probability', 0)
                    price = level.get('level', 0)
                    print(f"    ${price:.2f} (prob: {prob:.1%})")
        
        return sr_levels
        
    except Exception as e:
        print(f"❌ Error in S/R detection: {e}")
        return None

def examine_supertrend_ai(df):
    """Examine SuperTrend AI implementation."""
    print("\n" + "=" * 80)
    print("4. SUPERTREND AI ANALYSIS")
    print("=" * 80)
    
    try:
        # Initialize SuperTrend AI
        st_ai = SuperTrendAI(
            df,
            atr_length=10,
            min_mult=1.0,
            max_mult=5.0,
            step=0.5,
            perf_alpha=10,
            from_cluster="Best"
        )
        
        df_st, st_info = st_ai.calculate()
        
        print("✅ SuperTrend AI Results:")
        print(f"  Selected Factor: {st_info['target_factor']:.2f}")
        print(f"  Performance Index: {st_info['performance_index']:.3f}")
        print(f"  Signal Strength: {st_info['signal_strength']}/10")
        print(f"  Current Trend: {st_info['current_trend']}")
        
        # Show last 5 bars of SuperTrend data
        print("\n📊 SUPERTREND AI - LAST 5 BARS:")
        print("-" * 60)
        recent_st = df_st.tail(5)[['ts', 'close', 'supertrend', 'supertrend_trend', 'signal_confidence']]
        
        for idx, row in recent_st.iterrows():
            trend = "BULL" if row.get('supertrend_trend', 0) == 1 else "BEAR"
            print(f"{row['ts']}:")
            print(f"  Close: ${row['close']:.2f}")
            print(f"  SuperTrend: ${row['supertrend']:.2f}")
            print(f"  Trend: {trend}")
            print(f"  Confidence: {row['signal_confidence']:.0f}/10")
        
        return st_info
        
    except Exception as e:
        print(f"❌ Error in SuperTrend AI: {e}")
        return None

def examine_ml_feature_structure(df_with_indicators):
    """Examine how features are structured for ML."""
    print("\n" + "=" * 80)
    print("5. ML FEATURE STRUCTURE")
    print("=" * 80)
    
    try:
        # Get symbol ID
        symbol_id = db.get_symbol_id("AAPL")
        print(f"✅ AAPL Symbol ID: {symbol_id}")
        
        # Show feature categories
        feature_categories = {
            "Price Action": ['close', 'returns_1d', 'returns_5d', 'returns_20d'],
            "Momentum": ['rsi_14', 'macd', 'macd_signal', 'macd_hist', 'williams_r', 'cci'],
            "Trend": ['adx', 'sma_20', 'sma_50', 'ema_12', 'ema_26', 'bb_upper', 'bb_lower'],
            "Volume": ['volume_ratio', 'mfi_14', 'obv'],
            "Volatility": ['atr_14', 'atr_normalized', 'volatility_20d'],
            "SuperTrend AI": ['supertrend_value', 'supertrend_factor', 'signal_confidence', 
                           'supertrend_performance_index', 'supertrend_confidence_norm'],
            "Market Context": ['price_vs_sma20', 'price_vs_sma50']
        }
        
        print("\n📋 FEATURE CATEGORIES (Last Bar):")
        print("-" * 50)
        
        last_bar = df_with_indicators.iloc[-1]
        
        for category, features in feature_categories.items():
            available_features = [f for f in features if f in df_with_indicators.columns]
            if available_features:
                print(f"\n{category}:")
                for feature in available_features:
                    value = last_bar[feature]
                    if pd.isna(value):
                        print(f"  {feature}: NaN")
                    elif isinstance(value, float):
                        if abs(value) < 0.01:
                            print(f"  {feature}: {value:.4f}")
                        elif abs(value) < 1:
                            print(f"  {feature}: {value:.2f}")
                        else:
                            print(f"  {feature}: {value:.1f}")
                    else:
                        print(f"  {feature}: {value}")
        
        # Show feature statistics
        print(f"\n📊 FEATURE STATISTICS:")
        print("-" * 30)
        print(f"  Total Features: {len(df_with_indicators.columns)}")
        print(f"  Non-NaN Features (last bar): {df_with_indicators.iloc[-1].notna().sum()}")
        
        return df_with_indicators
        
    except Exception as e:
        print(f"❌ Error examining ML features: {e}")
        return None

def examine_supabase_storage():
    """Examine how data is stored in Supabase."""
    print("\n" + "=" * 80)
    print("6. SUPABASE STORAGE FORMAT")
    print("=" * 80)
    
    try:
        # Check ohlc_bars_v2 table structure
        print("🗄️  OHLC_BARS_V2 TABLE STRUCTURE:")
        print("-" * 40)
        
        # Fetch recent AAPL data from v2 table
        symbol_id = db.get_symbol_id("AAPL")
        response = db.client.table("ohlc_bars_v2")\
            .select("*")\
            .eq("symbol_id", symbol_id)\
            .eq("timeframe", "d1")\
            .eq("provider", "alpaca")\
            .order("ts", desc=True)\
            .limit(5)\
            .execute()
        
        if response.data:
            print("Recent AAPL data in ohlc_bars_v2:")
            for row in response.data:
                print(f"  {row['ts']}: Close=${row['close']:.2f}, Provider={row['provider']}")
        
        # Check indicator snapshots
        print("\n📊 INDICATOR SNAPSHOTS:")
        print("-" * 30)
        
        snapshot_response = db.client.table("indicator_snapshots")\
            .select("*")\
            .eq("symbol_id", symbol_id)\
            .eq("timeframe", "d1")\
            .order("ts", desc=True)\
            .limit(3)\
            .execute()
        
        if snapshot_response.data:
            print("Recent indicator snapshots:")
            for row in snapshot_response.data:
                print(f"  {row['ts']}: RSI={row.get('rsi_14', 'N/A')}, MACD={row.get('macd', 'N/A')}")
        
        # Check ML forecasts
        print("\n🤖 ML FORECASTS:")
        print("-" * 20)
        
        forecast_response = db.client.table("ml_forecasts")\
            .select("*")\
            .eq("symbol_id", symbol_id)\
            .order("created_at", desc=True)\
            .limit(3)\
            .execute()
        
        if forecast_response.data:
            print("Recent ML forecasts:")
            for row in forecast_response.data:
                print(f"  {row['created_at']}: {row['direction']} -> ${row['target_price']:.2f} (conf={row['confidence']:.0%})")
        else:
            print("  No ML forecasts found")
        
        # Check intraday forecasts
        print("\n⚡ INTRADAY FORECASTS:")
        print("-" * 25)
        
        intraday_response = db.client.table("intraday_forecasts")\
            .select("*")\
            .eq("symbol_id", symbol_id)\
            .order("created_at", desc=True)\
            .limit(3)\
            .execute()
        
        if intraday_response.data:
            print("Recent intraday forecasts:")
            for row in intraday_response.data:
                print(f"  {row['created_at']}: {row['horizon']} {row['overall_label']} -> ${row['target_price']:.2f}")
        else:
            print("  No intraday forecasts found")
        
    except Exception as e:
        print(f"❌ Error examining Supabase storage: {e}")

def main():
    """Main examination function."""
    print("🔍 AAPL INDICATORS & ML FEATURES PIPELINE EXAMINATION")
    print("=" * 80)
    print("This script shows how AAPL data flows through your pipeline:")
    print("Raw Data → Technical Indicators → S/R Detection → ML Features → Supabase")
    print("=" * 80)
    
    # Step 1: Fetch raw data
    df = fetch_aapl_recent_data()
    if df is None:
        print("❌ Cannot proceed without AAPL data")
        return
    
    # Step 2: Calculate technical indicators
    df_with_indicators = examine_technical_indicators(df)
    if df_with_indicators is None:
        print("❌ Cannot proceed without technical indicators")
        return
    
    # Step 3: Examine S/R detection
    sr_levels = examine_support_resistance(df)
    
    # Step 4: Examine SuperTrend AI
    st_info = examine_supertrend_ai(df)
    
    # Step 5: Examine ML feature structure
    examine_ml_feature_structure(df_with_indicators)
    
    # Step 6: Examine Supabase storage
    examine_supabase_storage()
    
    print("\n" + "=" * 80)
    print("✅ EXAMINATION COMPLETE")
    print("=" * 80)
    print("Summary:")
    print(f"  • Raw bars: {len(df)}")
    print(f"  • Technical indicators: {len(df_with_indicators.columns) - len(df.columns)}")
    print(f"  • S/R methods: 3 (Pivot, Polynomial, Logistic)")
    print(f"  • SuperTrend AI: {'✅' if st_info else '❌'}")
    print(f"  • Data stored in: ohlc_bars_v2, indicator_snapshots, ml_forecasts, intraday_forecasts")

if __name__ == "__main__":
    main()
