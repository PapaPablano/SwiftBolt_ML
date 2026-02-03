#!/usr/bin/env python3
"""
SwiftBolt ML - Indicator Validation & Diagnostic Script

This script validates all indicator calculations, identifies issues,
and provides specific fixes for broken indicators.

Usage:
    python indicator_diagnostics.py
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, List, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IndicatorDiagnostics:
    """Comprehensive indicator validation and diagnostics"""
    
    def __init__(self):
        self.results = {
            'working': [],
            'broken': [],
            'warnings': [],
            'fixes': []
        }
        
    def validate_talib_indicator(self, 
                                  df: pd.DataFrame, 
                                  indicator_name: str,
                                  min_periods: int) -> Dict:
        """Validate a single TA-Lib indicator"""
        result = {
            'name': indicator_name,
            'status': 'unknown',
            'issue': None,
            'fix': None
        }
        
        # Check if indicator exists
        if indicator_name not in df.columns:
            result['status'] = 'missing'
            result['issue'] = f"Column '{indicator_name}' not found in dataframe"
            return result
        
        # Get the indicator values
        values = df[indicator_name]
        
        # Check 1: All NaN
        if values.isna().all():
            result['status'] = 'broken'
            result['issue'] = f"All values are NaN"
            result['fix'] = f"Need at least {min_periods} bars of data"
            return result
        
        # Check 2: Insufficient data
        if len(df) < min_periods:
            result['status'] = 'broken'
            result['issue'] = f"Only {len(df)} bars, need {min_periods}"
            result['fix'] = f"Fetch at least {min_periods} bars"
            return result
        
        # Check 3: Too many NaN (>50%)
        nan_pct = values.isna().sum() / len(values)
        if nan_pct > 0.5:
            result['status'] = 'warning'
            result['issue'] = f"{nan_pct*100:.1f}% NaN values"
            result['fix'] = "Check calculation logic or increase data"
            return result
        
        # Check 4: Static values (std == 0)
        non_nan_values = values.dropna()
        if len(non_nan_values) > 0 and non_nan_values.std() == 0:
            result['status'] = 'warning'
            result['issue'] = f"Static value: {non_nan_values.iloc[0]}"
            result['fix'] = "Indicator not updating - check calculation"
            return result
        
        result['status'] = 'working'
        result['stats'] = {
            'count': len(non_nan_values),
            'mean': non_nan_values.mean(),
            'std': non_nan_values.std(),
            'min': non_nan_values.min(),
            'max': non_nan_values.max()
        }
        return result
    
    def test_talib_calculations(self, df: pd.DataFrame) -> None:
        """Test all TA-Lib indicator calculations"""
        logger.info("\n" + "="*80)
        logger.info("TESTING TA-LIB INDICATOR CALCULATIONS")
        logger.info("="*80)
        
        # Define TA-Lib indicators with their minimum periods
        talib_indicators = {
            # Moving Averages
            'sma_5': 5,
            'sma_10': 10,
            'sma_20': 20,
            'sma_50': 50,
            'sma_200': 200,
            'ema_12': 12,
            'ema_26': 26,
            
            # Momentum
            'rsi_14': 14,
            'macd': 26,
            'macd_signal': 35,  # 26 + 9
            'macd_hist': 35,
            'stoch_k': 14,
            'stoch_d': 17,  # 14 + 3
            'williams_r': 14,
            'cci': 20,
            
            # Volatility
            'atr_14': 14,
            'bb_upper': 20,
            'bb_middle': 20,
            'bb_lower': 20,
            
            # Volume
            'obv': 2,
            'mfi_14': 14,
        }
        
        for indicator, min_periods in talib_indicators.items():
            result = self.validate_talib_indicator(df, indicator, min_periods)
            
            if result['status'] == 'working':
                self.results['working'].append(result)
                logger.info(f"✅ {indicator}: WORKING")
                if 'stats' in result:
                    stats = result['stats']
                    logger.info(f"   Range: [{stats['min']:.2f}, {stats['max']:.2f}], "
                              f"Mean: {stats['mean']:.2f}, Std: {stats['std']:.2f}")
            
            elif result['status'] == 'broken':
                self.results['broken'].append(result)
                logger.error(f"❌ {indicator}: BROKEN - {result['issue']}")
                if result['fix']:
                    logger.error(f"   Fix: {result['fix']}")
                    self.results['fixes'].append({
                        'indicator': indicator,
                        'fix': result['fix']
                    })
            
            elif result['status'] == 'warning':
                self.results['warnings'].append(result)
                logger.warning(f"⚠️  {indicator}: WARNING - {result['issue']}")
                if result['fix']:
                    logger.warning(f"   Suggestion: {result['fix']}")
    
    def test_custom_indicators(self, df: pd.DataFrame) -> None:
        """Test custom indicator calculations"""
        logger.info("\n" + "="*80)
        logger.info("TESTING CUSTOM INDICATOR CALCULATIONS")
        logger.info("="*80)
        
        custom_indicators = {
            # SuperTrend AI
            'supertrend_value': 'SuperTrend level',
            'supertrend_factor': 'SuperTrend factor',
            'supertrend_performance_index': 'Performance index',
            'supertrend_signal_strength': 'Signal strength',
            'signal_confidence': 'Confidence score',
            
            # Support/Resistance
            'sr_nearest_support': 'Nearest support level',
            'sr_nearest_resistance': 'Nearest resistance level',
            'distance_to_support_pct': 'Distance to support %',
            'distance_to_resistance_pct': 'Distance to resistance %',
            'sr_poly_support': 'Polynomial support',
            'sr_poly_resistance': 'Polynomial resistance',
            
            # Market Context
            'spy_correlation_20d': 'SPY 20d correlation',
            'market_beta_20d': 'Market beta 20d',
            'market_rs_20d': 'Relative strength 20d',
        }
        
        for indicator, description in custom_indicators.items():
            if indicator not in df.columns:
                logger.error(f"❌ {indicator}: MISSING from dataframe")
                self.results['broken'].append({
                    'name': indicator,
                    'status': 'missing',
                    'issue': 'Column not found'
                })
                continue
            
            values = df[indicator].dropna()
            
            # Check if all NaN
            if len(values) == 0:
                logger.error(f"❌ {indicator} ({description}): ALL NaN")
                self.results['broken'].append({
                    'name': indicator,
                    'status': 'broken',
                    'issue': 'All NaN values'
                })
                continue
            
            # Check if all zeros
            if (values == 0).all():
                logger.warning(f"⚠️  {indicator} ({description}): ALL ZEROS")
                logger.warning(f"   This might indicate calculation not running")
                self.results['warnings'].append({
                    'name': indicator,
                    'status': 'warning',
                    'issue': 'All zero values - likely not calculated'
                })
                continue
            
            # Check if static
            if values.std() == 0:
                logger.warning(f"⚠️  {indicator} ({description}): STATIC VALUE = {values.iloc[0]}")
                self.results['warnings'].append({
                    'name': indicator,
                    'status': 'warning',
                    'issue': f'Static value: {values.iloc[0]}'
                })
                continue
            
            # Working
            logger.info(f"✅ {indicator} ({description}): WORKING")
            logger.info(f"   Range: [{values.min():.3f}, {values.max():.3f}], "
                       f"Mean: {values.mean():.3f}, Std: {values.std():.3f}")
            self.results['working'].append({
                'name': indicator,
                'status': 'working'
            })
    
    def test_support_resistance_system(self, df: pd.DataFrame) -> None:
        """Specifically test the S/R detection system"""
        logger.info("\n" + "="*80)
        logger.info("TESTING SUPPORT/RESISTANCE DETECTION SYSTEM")
        logger.info("="*80)
        
        sr_indicators = [
            'distance_to_support_pct',
            'distance_to_resistance_pct',
            'sr_nearest_support',
            'sr_nearest_resistance',
            'sr_poly_support',
            'sr_poly_resistance',
            'sr_support_prob_avg',
            'sr_resistance_prob_avg',
            'sr_density_2pct',
            'sr_signal_count',
            'support_volume_strength',
            'resistance_volume_strength'
        ]
        
        broken_count = 0
        for indicator in sr_indicators:
            if indicator not in df.columns:
                logger.error(f"❌ {indicator}: MISSING")
                broken_count += 1
                continue
            
            values = df[indicator]
            
            if values.isna().all():
                logger.error(f"❌ {indicator}: ALL NaN")
                broken_count += 1
            elif (values == 0).all():
                logger.warning(f"⚠️  {indicator}: ALL ZEROS (not calculated)")
                broken_count += 1
            else:
                logger.info(f"✅ {indicator}: Has valid data")
        
        if broken_count == len(sr_indicators):
            logger.error("\n🔴 CRITICAL: S/R SYSTEM COMPLETELY BROKEN")
            logger.error("   All S/R indicators are NaN or zero")
            logger.error("   This indicates a fundamental issue with S/R detection")
            logger.error("\n   Possible causes:")
            logger.error("   1. S/R detection function not being called")
            logger.error("   2. Exception being caught silently")
            logger.error("   3. Insufficient data (need 100+ bars)")
            logger.error("   4. Format string error (seen in your output)")
        elif broken_count > 0:
            logger.warning(f"\n⚠️  S/R SYSTEM PARTIALLY BROKEN: {broken_count}/{len(sr_indicators)} indicators broken")
    
    def validate_data_sufficiency(self, df: pd.DataFrame) -> None:
        """Check if we have enough data for all indicators"""
        logger.info("\n" + "="*80)
        logger.info("VALIDATING DATA SUFFICIENCY")
        logger.info("="*80)
        
        n_bars = len(df)
        logger.info(f"Available data: {n_bars} bars")
        
        requirements = {
            'Basic indicators (RSI, MACD)': 26,
            'Short-term SMA (20d)': 20,
            'Medium-term SMA (50d)': 50,
            'GARCH features': 50,
            'S/R detection (minimum)': 100,
            'Long-term SMA (200d)': 200,
            'Robust S/R detection': 250,
        }
        
        for feature, required in requirements.items():
            if n_bars >= required:
                logger.info(f"✅ {feature}: OK (need {required}, have {n_bars})")
            else:
                logger.error(f"❌ {feature}: INSUFFICIENT (need {required}, have {n_bars})")
                self.results['fixes'].append({
                    'indicator': feature,
                    'fix': f'Increase data fetch to at least {required} bars'
                })
    
    def generate_fix_script(self) -> str:
        """Generate a script with all recommended fixes"""
        fixes = []
        
        # Data fetching fix
        if len([f for f in self.results['fixes'] if 'bars' in f.get('fix', '')]) > 0:
            fixes.append("""
# FIX 1: Increase data fetching
# Change your data fetching code from:
# bars = api.get_bars(symbol, timeframe, limit=10)
# To:
bars = api.get_bars(symbol, timeframe, limit=250)

# Or better, fetch by date range:
from datetime import datetime, timedelta
start = datetime.now() - timedelta(days=365)
bars = api.get_bars(symbol, timeframe, start=start.isoformat())
""")
        
        # S/R detection fix
        if any('S/R' in str(r.get('name', '')) for r in self.results['broken']):
            fixes.append("""
# FIX 2: Fix Support/Resistance Detection
# Add proper null checks and error handling:

def detect_support_resistance(df):
    '''Detect S/R levels with proper error handling'''
    if len(df) < 100:
        logger.warning("Need at least 100 bars for S/R detection")
        # Return NaN for all S/R features
        sr_cols = [
            'sr_nearest_support', 'sr_nearest_resistance',
            'distance_to_support_pct', 'distance_to_resistance_pct'
        ]
        for col in sr_cols:
            df[col] = np.nan
        return df
    
    try:
        # Your S/R detection logic here
        sr_levels = calculate_sr_levels(df)
        
        # NULL CHECK before formatting
        if sr_levels is None or len(sr_levels) == 0:
            logger.warning("No S/R levels found")
            df['sr_nearest_support'] = np.nan
            df['sr_nearest_resistance'] = np.nan
            return df
        
        # Rest of your S/R code
        # ...
        
    except Exception as e:
        logger.error(f"S/R detection failed: {e}")
        # Set all S/R features to NaN
        for col in df.columns:
            if col.startswith('sr_') or 'support' in col or 'resistance' in col:
                df[col] = np.nan
    
    return df
""")
        
        # TA-Lib validation fix
        fixes.append("""
# FIX 3: Add validation for TA-Lib indicators
# Wrap each TA-Lib call with error handling:

def safe_talib_indicator(func, *args, **kwargs):
    '''Safely call TA-Lib function with error handling'''
    try:
        result = func(*args, **kwargs)
        if result is None or (isinstance(result, np.ndarray) and len(result) == 0):
            return np.nan
        return result
    except Exception as e:
        logger.warning(f"TA-Lib calculation failed: {e}")
        return np.nan

# Example usage:
df['williams_r'] = safe_talib_indicator(
    talib.WILLR, 
    df['high'], df['low'], df['close'], 
    timeperiod=14
)

df['cci'] = safe_talib_indicator(
    talib.CCI,
    df['high'], df['low'], df['close'],
    timeperiod=20
)
""")
        
        # Market correlation fix
        fixes.append("""
# FIX 4: Fix Market Correlation Features
# Add SPY data fetching:

# Fetch SPY data alongside your symbol
spy_bars = api.get_bars("SPY", timeframe, limit=250)
spy_df = pd.DataFrame({
    'timestamp': [b.t for b in spy_bars],
    'close': [b.c for b in spy_bars]
})

# Merge with main dataframe
df = df.merge(spy_df, on='timestamp', how='left', suffixes=('', '_spy'))

# Calculate correlations properly
df['spy_correlation_20d'] = df['close'].rolling(20).corr(df['close_spy'])
df['spy_correlation_60d'] = df['close'].rolling(60).corr(df['close_spy'])

# Calculate beta
df['returns_spy'] = df['close_spy'].pct_change()
cov = df['returns_1d'].rolling(20).cov(df['returns_spy'])
var = df['returns_spy'].rolling(20).var()
df['market_beta_20d'] = cov / var
""")
        
        return "\n".join(fixes)
    
    def print_summary(self) -> None:
        """Print summary of diagnostics"""
        logger.info("\n" + "="*80)
        logger.info("DIAGNOSTIC SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\n✅ Working indicators: {len(self.results['working'])}")
        logger.info(f"❌ Broken indicators: {len(self.results['broken'])}")
        logger.info(f"⚠️  Warnings: {len(self.results['warnings'])}")
        
        if self.results['broken']:
            logger.info("\nBroken indicators:")
            for result in self.results['broken']:
                logger.info(f"  - {result['name']}: {result.get('issue', 'unknown')}")
        
        if self.results['warnings']:
            logger.info("\nWarnings:")
            for result in self.results['warnings']:
                logger.info(f"  - {result['name']}: {result.get('issue', 'unknown')}")
        
        logger.info(f"\n📋 Total fixes needed: {len(self.results['fixes'])}")


def main():
    """Main diagnostic function"""
    # You'll need to replace this with your actual data loading
    # This is just a placeholder
    logger.info("🔍 SwiftBolt ML - Indicator Diagnostics")
    logger.info("="*80)
    logger.info("This script will validate all your indicator calculations")
    logger.info("and provide specific fixes for any issues found.")
    logger.info("="*80)
    
    # TODO: Load your actual data here
    # df = load_your_data()
    
    # For testing, create synthetic data
    dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
    df = pd.DataFrame({
        'timestamp': dates,
        'close': [100 + i for i in range(10)],
        'high': [102 + i for i in range(10)],
        'low': [98 + i for i in range(10)],
        'open': [99 + i for i in range(10)],
        'volume': [1000000 + i*10000 for i in range(10)],
    })
    
    logger.warning("\n⚠️  USING SYNTHETIC DATA FOR TESTING")
    logger.warning("Replace this with your actual data loading code!\n")
    
    # Run diagnostics
    diagnostics = IndicatorDiagnostics()
    
    # Validate data sufficiency
    diagnostics.validate_data_sufficiency(df)
    
    # NOTE: You'll need to add your indicator calculations here
    # df = calculate_all_indicators(df)
    
    # Test TA-Lib indicators
    # diagnostics.test_talib_calculations(df)
    
    # Test custom indicators
    # diagnostics.test_custom_indicators(df)
    
    # Test S/R system specifically
    # diagnostics.test_support_resistance_system(df)
    
    # Print summary
    diagnostics.print_summary()
    
    # Generate fix script
    fix_script = diagnostics.generate_fix_script()
    
    # Save to file
    fix_file_path = '/Users/ericpeterson/SwiftBolt_ML/indicator_fixes.py'
    with open(fix_file_path, 'w') as f:
        f.write("#!/usr/bin/env python3\n")
        f.write('"""\nRecommended fixes for SwiftBolt ML indicators\n"""\n')
        f.write(fix_script)
    
    logger.info(f"\n✅ Fix script generated: {fix_file_path}")
    logger.info("\nNext steps:")
    logger.info("1. Update this script with your actual data loading code")
    logger.info("2. Add your indicator calculation functions")
    logger.info("3. Run this script on your local machine")
    logger.info("4. Apply the fixes from indicator_fixes.py")


if __name__ == '__main__':
    main()
