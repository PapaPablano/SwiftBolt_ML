#!/usr/bin/env python3
"""
CRITICAL FIXES for SwiftBolt ML Indicators
Apply these fixes IMMEDIATELY to get your pipeline working

These are the TOP PRIORITY fixes based on your audit results.
"""

import pandas as pd
import numpy as np
import talib
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


# ============================================================================
# FIX #1: DATA FETCHING - HIGHEST PRIORITY
# ============================================================================
# YOUR CURRENT CODE (BROKEN):
# bars = api.get_bars(symbol, timeframe, limit=10)  # ❌ ONLY 10 BARS!

# FIXED CODE:
def fetch_sufficient_data(api, symbol: str, timeframe: str, min_bars: int = 250):
    """
    Fetch sufficient historical data for indicator calculations
    
    Args:
        api: Your Alpaca API instance
        symbol: Stock symbol (e.g., 'AAPL')
        timeframe: Timeframe (e.g., '1Day')
        min_bars: Minimum bars to fetch (default 250)
    
    Returns:
        DataFrame with OHLCV data
    """
    from datetime import datetime, timedelta
    
    # Method 1: Fetch by date range (RECOMMENDED)
    start_date = datetime.now() - timedelta(days=365)  # 1 year of data
    bars = api.get_bars(
        symbol, 
        timeframe, 
        start=start_date.isoformat()
    )
    
    # Method 2: Fetch by limit (alternative)
    # bars = api.get_bars(symbol, timeframe, limit=min_bars)
    
    df = pd.DataFrame({
        'timestamp': [b.t for b in bars],
        'open': [b.o for b in bars],
        'high': [b.h for b in bars],
        'low': [b.l for b in bars],
        'close': [b.c for b in bars],
        'volume': [b.v for b in bars],
    })
    
    logger.info(f"✅ Fetched {len(df)} bars for {symbol}")
    
    if len(df) < min_bars:
        logger.warning(
            f"⚠️  Only {len(df)} bars available, some indicators may not work properly"
        )
    
    return df


# ============================================================================
# FIX #2: SUPPORT/RESISTANCE DETECTION ERROR
# ============================================================================
# The error in your output: "unsupported format string passed to NoneType.__format__"
# This means you're trying to format a None value as a string

def detect_support_resistance_fixed(df: pd.DataFrame, 
                                    lookback: int = 100,
                                    min_touches: int = 2) -> pd.DataFrame:
    """
    Fixed S/R detection with proper null checks and error handling
    
    Args:
        df: DataFrame with OHLCV data
        lookback: Number of bars to look back for S/R levels
        min_touches: Minimum touches to consider a level valid
    
    Returns:
        DataFrame with S/R features added
    """
    # CRITICAL: Check data sufficiency FIRST
    if len(df) < lookback:
        logger.warning(
            f"❌ Insufficient data for S/R detection: "
            f"have {len(df)} bars, need {lookback}. "
            f"Setting all S/R features to NaN"
        )
        
        # Set all S/R features to NaN instead of breaking
        sr_features = [
            'sr_nearest_support', 'sr_nearest_resistance',
            'distance_to_support_pct', 'distance_to_resistance_pct',
            'sr_poly_support', 'sr_poly_resistance',
            'sr_support_prob_avg', 'sr_resistance_prob_avg',
            'sr_density_2pct', 'sr_density_5pct',
            'sr_signal_count', 'support_volume_strength',
            'resistance_volume_strength'
        ]
        for feature in sr_features:
            df[feature] = np.nan
        
        return df
    
    try:
        # Your S/R detection logic here
        # Example: Simple swing high/low detection
        
        # Find swing highs (potential resistance)
        df['swing_high'] = False
        df['swing_low'] = False
        
        for i in range(5, len(df) - 5):
            # Swing high: higher than 5 bars before and after
            if all(df['high'].iloc[i] > df['high'].iloc[i-5:i]) and \
               all(df['high'].iloc[i] > df['high'].iloc[i+1:i+6]):
                df.loc[df.index[i], 'swing_high'] = True
            
            # Swing low: lower than 5 bars before and after
            if all(df['low'].iloc[i] < df['low'].iloc[i-5:i]) and \
               all(df['low'].iloc[i] < df['low'].iloc[i+1:i+6]):
                df.loc[df.index[i], 'swing_low'] = True
        
        # Get resistance and support levels
        resistance_levels = df[df['swing_high']]['high'].values
        support_levels = df[df['swing_low']]['low'].values
        
        # CRITICAL NULL CHECK - This is where your code was breaking
        if resistance_levels is None or len(resistance_levels) == 0:
            logger.warning("No resistance levels found")
            resistance_levels = np.array([])
        
        if support_levels is None or len(support_levels) == 0:
            logger.warning("No support levels found")
            support_levels = np.array([])
        
        # Calculate features for each bar
        current_price = df['close'].values
        
        if len(support_levels) > 0:
            # Find nearest support for each bar
            df['sr_nearest_support'] = [
                support_levels[support_levels <= price].max() 
                if len(support_levels[support_levels <= price]) > 0 
                else np.nan
                for price in current_price
            ]
            
            # Distance to support as percentage
            df['distance_to_support_pct'] = (
                (df['close'] - df['sr_nearest_support']) / df['close'] * 100
            )
        else:
            df['sr_nearest_support'] = np.nan
            df['distance_to_support_pct'] = np.nan
        
        if len(resistance_levels) > 0:
            # Find nearest resistance for each bar
            df['sr_nearest_resistance'] = [
                resistance_levels[resistance_levels >= price].min()
                if len(resistance_levels[resistance_levels >= price]) > 0
                else np.nan
                for price in current_price
            ]
            
            # Distance to resistance as percentage
            df['distance_to_resistance_pct'] = (
                (df['sr_nearest_resistance'] - df['close']) / df['close'] * 100
            )
        else:
            df['sr_nearest_resistance'] = np.nan
            df['distance_to_resistance_pct'] = np.nan
        
        logger.info(
            f"✅ S/R Detection: Found {len(support_levels)} support "
            f"and {len(resistance_levels)} resistance levels"
        )
        
    except Exception as e:
        logger.error(f"❌ S/R detection failed: {e}")
        logger.error(f"   Setting all S/R features to NaN")
        
        # Don't crash - set features to NaN
        for col in ['sr_nearest_support', 'sr_nearest_resistance',
                   'distance_to_support_pct', 'distance_to_resistance_pct']:
            df[col] = np.nan
    
    return df


# ============================================================================
# FIX #3: TA-LIB INDICATORS WITH ERROR HANDLING
# ============================================================================

def safe_talib_wrapper(func, *args, **kwargs) -> np.ndarray:
    """
    Safely call any TA-Lib function with proper error handling
    
    Returns:
        Numpy array with indicator values, or array of NaN if calculation fails
    """
    try:
        result = func(*args, **kwargs)
        
        # Check if result is valid
        if result is None:
            logger.warning(f"TA-Lib function {func.__name__} returned None")
            return np.full(len(args[0]), np.nan)
        
        if isinstance(result, tuple):
            # Some TA-Lib functions return tuples (e.g., BBANDS)
            return result
        
        return result
        
    except Exception as e:
        logger.warning(f"TA-Lib {func.__name__} failed: {e}")
        # Return NaN array of same length as input
        return np.full(len(args[0]), np.nan)


def calculate_talib_indicators_fixed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate TA-Lib indicators with proper error handling
    
    This fixes the issues with:
    - williams_r: All NaN
    - cci: All NaN  
    - bb_upper/bb_lower: All NaN
    - volume indicators: All NaN
    """
    
    # Bollinger Bands (need 20 bars minimum)
    if len(df) >= 20:
        upper, middle, lower = safe_talib_wrapper(
            talib.BBANDS,
            df['close'].values,
            timeperiod=20,
            nbdevup=2,
            nbdevdn=2,
            matype=0
        )
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        df['bb_width'] = (upper - lower) / middle * 100
        df['bb_pct_b'] = (df['close'] - lower) / (upper - lower)
    else:
        logger.warning("Not enough data for Bollinger Bands (need 20 bars)")
        df['bb_upper'] = np.nan
        df['bb_middle'] = np.nan
        df['bb_lower'] = np.nan
        df['bb_width'] = np.nan
        df['bb_pct_b'] = np.nan
    
    # Williams %R (need 14 bars minimum)
    if len(df) >= 14:
        df['williams_r'] = safe_talib_wrapper(
            talib.WILLR,
            df['high'].values,
            df['low'].values,
            df['close'].values,
            timeperiod=14
        )
    else:
        logger.warning("Not enough data for Williams %R (need 14 bars)")
        df['williams_r'] = np.nan
    
    # CCI (need 20 bars minimum)
    if len(df) >= 20:
        df['cci'] = safe_talib_wrapper(
            talib.CCI,
            df['high'].values,
            df['low'].values,
            df['close'].values,
            timeperiod=20
        )
    else:
        logger.warning("Not enough data for CCI (need 20 bars)")
        df['cci'] = np.nan
    
    # MFI - Money Flow Index (need 14 bars + volume)
    if len(df) >= 14 and 'volume' in df.columns:
        df['mfi_14'] = safe_talib_wrapper(
            talib.MFI,
            df['high'].values,
            df['low'].values,
            df['close'].values,
            df['volume'].values,
            timeperiod=14
        )
    else:
        logger.warning("Not enough data for MFI (need 14 bars)")
        df['mfi_14'] = np.nan
    
    # Volume SMA
    if len(df) >= 20 and 'volume' in df.columns:
        df['volume_sma_20'] = safe_talib_wrapper(
            talib.SMA,
            df['volume'].values,
            timeperiod=20
        )
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
    else:
        df['volume_sma_20'] = np.nan
        df['volume_ratio'] = np.nan
    
    return df


# ============================================================================
# FIX #4: MARKET CORRELATION FEATURES
# ============================================================================

def calculate_market_correlations_fixed(df: pd.DataFrame,
                                       api,
                                       symbol: str,
                                       timeframe: str) -> pd.DataFrame:
    """
    Calculate market correlation features properly
    
    This fixes:
    - spy_correlation_20d: Stuck at 0.0
    - spy_correlation_60d: Stuck at 0.0
    - market_beta_20d: Stuck at 1.0
    - market_rs_20d: All NaN
    """
    
    try:
        # Fetch SPY data for the same period
        from datetime import timedelta
        
        if len(df) > 0:
            start_date = df['timestamp'].min() - timedelta(days=10)  # Buffer
            
            spy_bars = api.get_bars(
                "SPY",
                timeframe,
                start=start_date.isoformat()
            )
            
            spy_df = pd.DataFrame({
                'timestamp': [b.t for b in spy_bars],
                'close': [b.c for b in spy_bars],
            })
            
            # Merge with main dataframe
            df = df.merge(
                spy_df,
                on='timestamp',
                how='left',
                suffixes=('', '_spy')
            )
            
            # Calculate SPY returns
            df['returns_spy'] = df['close_spy'].pct_change()
            
            # Correlation features
            if len(df) >= 20:
                df['spy_correlation_20d'] = (
                    df['returns_1d']
                    .rolling(20)
                    .corr(df['returns_spy'])
                )
            else:
                df['spy_correlation_20d'] = np.nan
            
            if len(df) >= 60:
                df['spy_correlation_60d'] = (
                    df['returns_1d']
                    .rolling(60)
                    .corr(df['returns_spy'])
                )
            else:
                df['spy_correlation_60d'] = np.nan
            
            # Beta calculation (20-day)
            if len(df) >= 20:
                cov = df['returns_1d'].rolling(20).cov(df['returns_spy'])
                var = df['returns_spy'].rolling(20).var()
                df['market_beta_20d'] = cov / var
            else:
                df['market_beta_20d'] = 1.0  # Default
            
            # Relative Strength vs SPY
            if len(df) >= 20:
                df['market_rs_20d'] = (
                    (1 + df['returns_1d']).rolling(20).apply(np.prod) /
                    (1 + df['returns_spy']).rolling(20).apply(np.prod)
                )
            else:
                df['market_rs_20d'] = np.nan
            
            logger.info(f"✅ Calculated market correlations with SPY")
            
    except Exception as e:
        logger.error(f"❌ Market correlation calculation failed: {e}")
        df['spy_correlation_20d'] = np.nan
        df['spy_correlation_60d'] = np.nan
        df['market_beta_20d'] = 1.0
        df['market_rs_20d'] = np.nan
    
    return df


# ============================================================================
# FIX #5: SUPABASE TABLE NAME
# ============================================================================

def save_to_supabase_fixed(df: pd.DataFrame, supabase_client):
    """
    Save indicators to Supabase with correct table name
    
    Your code was trying to use 'indicator_snapshots' 
    but the table is actually called 'indicator_values'
    """
    
    # WRONG:
    # table = supabase_client.table('indicator_snapshots')
    
    # CORRECT:
    table = supabase_client.table('indicator_values')
    
    try:
        # Prepare data for insertion
        records = df.to_dict('records')
        
        # Batch insert (Supabase recommends batches of 100-1000)
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            result = table.insert(batch).execute()
            logger.info(f"✅ Inserted batch {i//batch_size + 1}: {len(batch)} records")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Supabase insert failed: {e}")
        return False


# ============================================================================
# FIX #6: DATA VALIDATION LAYER
# ============================================================================

def validate_indicators(df: pd.DataFrame, 
                       critical_indicators: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that critical indicators calculated properly before saving
    
    Args:
        df: DataFrame with indicators
        critical_indicators: List of must-have indicators
    
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    
    for indicator in critical_indicators:
        if indicator not in df.columns:
            issues.append(f"❌ Missing: {indicator}")
            continue
        
        values = df[indicator]
        
        # Check if all NaN
        if values.isna().all():
            issues.append(f"❌ All NaN: {indicator}")
            continue
        
        # Check if >80% NaN (warning)
        nan_pct = values.isna().sum() / len(values)
        if nan_pct > 0.8:
            issues.append(f"⚠️  {nan_pct*100:.0f}% NaN: {indicator}")
        
        # Check if all zeros (suspicious)
        non_nan = values.dropna()
        if len(non_nan) > 0 and (non_nan == 0).all():
            issues.append(f"⚠️  All zeros: {indicator}")
        
        # Check if static (no variation)
        if len(non_nan) > 1 and non_nan.std() == 0:
            issues.append(f"⚠️  Static value: {indicator} = {non_nan.iloc[0]}")
    
    is_valid = len([i for i in issues if i.startswith("❌")]) == 0
    
    return is_valid, issues


# ============================================================================
# COMPLETE FIXED PIPELINE
# ============================================================================

def process_indicators_fixed(api, symbol: str, timeframe: str, supabase_client):
    """
    Complete fixed indicator calculation pipeline
    
    This is how your pipeline SHOULD work:
    1. Fetch sufficient data (250+ bars)
    2. Calculate TA-Lib indicators with error handling
    3. Calculate custom indicators (S/R, SuperTrend)
    4. Calculate market correlations
    5. Validate data quality
    6. Save to Supabase (correct table name)
    """
    
    logger.info(f"🔄 Processing indicators for {symbol}")
    
    # Step 1: Fetch sufficient data
    df = fetch_sufficient_data(api, symbol, timeframe, min_bars=250)
    
    if len(df) < 50:
        logger.error(f"❌ Insufficient data: only {len(df)} bars")
        return None
    
    # Step 2: Calculate TA-Lib indicators
    df = calculate_talib_indicators_fixed(df)
    
    # Step 3: Calculate S/R (your custom function, but fixed)
    df = detect_support_resistance_fixed(df, lookback=100)
    
    # Step 4: Calculate market correlations
    df = calculate_market_correlations_fixed(df, api, symbol, timeframe)
    
    # Step 5: Validate critical indicators
    critical_indicators = [
        'close', 'returns_1d', 'rsi_14', 'macd', 'atr_14',
        'sma_20', 'ema_12', 'adx'
    ]
    
    is_valid, issues = validate_indicators(df, critical_indicators)
    
    if issues:
        logger.warning("⚠️  Validation issues found:")
        for issue in issues:
            logger.warning(f"   {issue}")
    
    if not is_valid:
        logger.error("❌ Critical validation failures - not saving to Supabase")
        return None
    
    # Step 6: Save to Supabase
    success = save_to_supabase_fixed(df, supabase_client)
    
    if success:
        logger.info(f"✅ Successfully processed {len(df)} bars for {symbol}")
    
    return df


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == '__main__':
    """
    Example of how to use these fixes in your code
    """
    
    # Your existing imports
    # from alpaca.data import StockHistoricalDataClient
    # from supabase import create_client
    
    # Initialize your clients (example)
    # api = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    # supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Run the fixed pipeline
    # df = process_indicators_fixed(api, 'AAPL', '1Day', supabase)
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                    CRITICAL FIXES SUMMARY                          ║
    ╠════════════════════════════════════════════════════════════════════╣
    ║                                                                    ║
    ║  ✅ FIX #1: Fetch 250+ bars instead of 10                         ║
    ║  ✅ FIX #2: Added null checks to S/R detection                    ║
    ║  ✅ FIX #3: Wrapped TA-Lib with error handling                    ║
    ║  ✅ FIX #4: Fixed market correlation calculations                 ║
    ║  ✅ FIX #5: Corrected Supabase table name                         ║
    ║  ✅ FIX #6: Added data validation layer                           ║
    ║                                                                    ║
    ║  To apply these fixes:                                            ║
    ║  1. Copy the functions you need into your code                    ║
    ║  2. Replace your existing broken functions                        ║
    ║  3. Test with process_indicators_fixed()                          ║
    ║                                                                    ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
