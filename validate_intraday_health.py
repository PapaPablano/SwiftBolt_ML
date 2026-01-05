#!/usr/bin/env python3
"""
Intraday Stock Data Health Validator for AAPL
Validates 15-minute and 60-minute data quality and indicator calculations
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys

class IntradayDataHealthValidator:
    """Validates intraday stock data health and indicator calculations"""
    
    def __init__(self, file_15min: str, file_60min: str):
        self.file_15min = file_15min
        self.file_60min = file_60min
        self.df_15min = None
        self.df_60min = None
        self.health_report = {
            '15min': {},
            '60min': {},
            'overall_status': 'UNKNOWN'
        }
        
    def load_data(self) -> bool:
        """Load CSV files and parse timestamps"""
        try:
            print("📊 Loading data files...")
            self.df_15min = pd.read_csv(self.file_15min)
            self.df_60min = pd.read_csv(self.file_60min)
            
            # Parse timestamps with UTC normalization
            self.df_15min['time'] = pd.to_datetime(self.df_15min['time'], utc=True).dt.tz_convert('America/Chicago')
            self.df_60min['time'] = pd.to_datetime(self.df_60min['time'], utc=True).dt.tz_convert('America/Chicago')
            
            # Sort by time
            self.df_15min = self.df_15min.sort_values('time').reset_index(drop=True)
            self.df_60min = self.df_60min.sort_values('time').reset_index(drop=True)
            
            print(f"✅ Loaded 15-min data: {len(self.df_15min)} rows")
            print(f"✅ Loaded 60-min data: {len(self.df_60min)} rows")
            return True
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def check_data_completeness(self, df: pd.DataFrame, interval: str) -> Dict:
        """Check for missing data, gaps, and completeness"""
        results = {}
        
        # Check for null values
        null_counts = df.isnull().sum()
        results['null_values'] = null_counts[null_counts > 0].to_dict()
        
        # Check OHLCV completeness
        ohlcv_cols = ['open', 'high', 'low', 'close', 'Volume']
        missing_ohlcv = sum(df[col].isnull().sum() for col in ohlcv_cols if col in df.columns)
        results['ohlcv_complete'] = missing_ohlcv == 0
        
        # Check for time gaps
        time_diffs = df['time'].diff()
        expected_interval = pd.Timedelta(minutes=int(interval.replace('min', '')))
        
        # Allow for market hours gaps (overnight, weekends)
        gaps = []
        for idx, diff in enumerate(time_diffs[1:], start=1):
            if diff > expected_interval * 2 and diff < pd.Timedelta(days=1):
                # Intraday gap (not overnight)
                gaps.append({
                    'index': idx,
                    'time': df.loc[idx, 'time'],
                    'gap_minutes': diff.total_seconds() / 60
                })
        
        results['intraday_gaps'] = gaps
        results['gap_count'] = len(gaps)
        
        # Check for duplicates
        duplicates = df[df.duplicated(subset=['time'], keep=False)]
        results['duplicate_timestamps'] = len(duplicates)
        results['duplicates'] = duplicates['time'].tolist() if len(duplicates) > 0 else []
        
        # Date range
        results['start_date'] = df['time'].min()
        results['end_date'] = df['time'].max()
        results['total_days'] = (results['end_date'] - results['start_date']).days
        
        return results
    
    def validate_ohlc_relationships(self, df: pd.DataFrame) -> Dict:
        """Validate OHLC data relationships"""
        results = {}
        
        # High should be >= Open, Close, Low
        high_violations = (
            (df['high'] < df['open']) | 
            (df['high'] < df['close']) | 
            (df['high'] < df['low'])
        ).sum()
        
        # Low should be <= Open, Close, High
        low_violations = (
            (df['low'] > df['open']) | 
            (df['low'] > df['close']) | 
            (df['low'] > df['high'])
        ).sum()
        
        results['high_violations'] = int(high_violations)
        results['low_violations'] = int(low_violations)
        results['ohlc_valid'] = (high_violations == 0 and low_violations == 0)
        
        # Check for zero or negative prices
        price_cols = ['open', 'high', 'low', 'close']
        zero_prices = sum((df[col] <= 0).sum() for col in price_cols)
        results['zero_or_negative_prices'] = int(zero_prices)
        
        # Check for extreme price movements (>20% in single bar)
        price_change_pct = ((df['close'] - df['open']) / df['open'] * 100).abs()
        extreme_moves = (price_change_pct > 20).sum()
        results['extreme_price_moves'] = int(extreme_moves)
        
        return results
    
    def validate_volume(self, df: pd.DataFrame) -> Dict:
        """Validate volume data"""
        results = {}
        
        # Check for zero volume
        zero_volume = (df['Volume'] == 0).sum()
        results['zero_volume_bars'] = int(zero_volume)
        
        # Check for negative volume
        negative_volume = (df['Volume'] < 0).sum()
        results['negative_volume_bars'] = int(negative_volume)
        
        # Volume statistics
        results['avg_volume'] = float(df['Volume'].mean())
        results['median_volume'] = float(df['Volume'].median())
        results['max_volume'] = float(df['Volume'].max())
        results['min_volume'] = float(df['Volume'].min())
        
        # Check for volume outliers (>10x median)
        median_vol = df['Volume'].median()
        outliers = (df['Volume'] > median_vol * 10).sum()
        results['volume_outliers'] = int(outliers)
        
        return results
    
    def validate_bollinger_bands(self, df: pd.DataFrame) -> Dict:
        """Validate Bollinger Bands calculations"""
        results = {}
        
        # Basis should be between Upper and Lower
        bb_violations = (
            (df['Basis'] > df['Upper']) | 
            (df['Basis'] < df['Lower'])
        ).sum()
        results['bb_structure_violations'] = int(bb_violations)
        
        # Close should mostly be within bands (allow some breakouts)
        outside_bands = (
            (df['close'] > df['Upper']) | 
            (df['close'] < df['Lower'])
        ).sum()
        outside_pct = (outside_bands / len(df)) * 100
        results['price_outside_bands_pct'] = float(outside_pct)
        results['bb_reasonable'] = outside_pct < 10  # Less than 10% outside
        
        # Check for null values in BB
        bb_nulls = df[['Basis', 'Upper', 'Lower']].isnull().sum().sum()
        results['bb_null_values'] = int(bb_nulls)
        
        return results
    
    def validate_rsi(self, df: pd.DataFrame) -> Dict:
        """Validate RSI calculations"""
        results = {}
        
        # RSI should be between 0 and 100
        rsi_out_of_range = ((df['RSI'] < 0) | (df['RSI'] > 100)).sum()
        results['rsi_out_of_range'] = int(rsi_out_of_range)
        
        # RSI statistics
        results['rsi_mean'] = float(df['RSI'].mean())
        results['rsi_median'] = float(df['RSI'].median())
        results['rsi_min'] = float(df['RSI'].min())
        results['rsi_max'] = float(df['RSI'].max())
        
        # Check RSI Cloud relationships
        cloud_violations = (df['RSI Cloud Lead'] < df['RSI Cloud Base']).sum()
        results['rsi_cloud_inversions'] = int(cloud_violations)
        
        # Overbought/Oversold levels
        overbought = (df['RSI'] > 70).sum()
        oversold = (df['RSI'] < 30).sum()
        results['overbought_periods'] = int(overbought)
        results['oversold_periods'] = int(oversold)
        results['overbought_pct'] = float((overbought / len(df)) * 100)
        results['oversold_pct'] = float((oversold / len(df)) * 100)
        
        return results
    
    def validate_adx(self, df: pd.DataFrame) -> Dict:
        """Validate ADX calculations"""
        results = {}
        
        # ADX should be between 0 and 100
        adx_cols = ['ADX Current Timeframe', 'ADX Different Timeframe']
        for col in adx_cols:
            if col in df.columns:
                out_of_range = ((df[col] < 0) | (df[col] > 100)).sum()
                results[f'{col}_out_of_range'] = int(out_of_range)
                results[f'{col}_mean'] = float(df[col].mean())
        
        # Check for strong trends (ADX > 25)
        strong_trends = (df['ADX Current Timeframe'] > 25).sum()
        results['strong_trend_periods'] = int(strong_trends)
        results['strong_trend_pct'] = float((strong_trends / len(df)) * 100)
        
        return results
    
    def check_timestamp_consistency(self, df: pd.DataFrame, interval: str) -> Dict:
        """Check timestamp consistency and market hours"""
        results = {}
        
        # Extract time components
        df['hour'] = df['time'].dt.hour
        df['minute'] = df['time'].dt.minute
        df['day_of_week'] = df['time'].dt.dayofweek
        
        # Check for weekend data (should not exist for stock market)
        weekend_data = df[df['day_of_week'].isin([5, 6])]
        results['weekend_bars'] = len(weekend_data)
        
        # Check for data outside market hours (9:30 AM - 4:00 PM ET)
        # Note: Times are in local timezone, adjust as needed
        outside_hours = df[
            (df['hour'] < 8) | 
            (df['hour'] > 15) | 
            ((df['hour'] == 8) & (df['minute'] < 30))
        ]
        results['outside_market_hours'] = len(outside_hours)
        
        # Check interval consistency
        expected_minutes = int(interval.replace('min', ''))
        if expected_minutes == 15:
            valid_minutes = [0, 15, 30, 45]
        elif expected_minutes == 60:
            valid_minutes = [30]  # Market opens at 9:30
        else:
            valid_minutes = list(range(0, 60, expected_minutes))
        
        invalid_minutes = df[~df['minute'].isin(valid_minutes)]
        results['invalid_minute_marks'] = len(invalid_minutes)
        
        return results
    
    def run_validation(self) -> bool:
        """Run all validation checks"""
        if not self.load_data():
            return False
        
        print("\n" + "="*70)
        print("🔍 INTRADAY DATA HEALTH VALIDATION - AAPL")
        print("="*70)
        
        for interval, df in [('15min', self.df_15min), ('60min', self.df_60min)]:
            print(f"\n{'='*70}")
            print(f"📈 Validating {interval.upper()} Data")
            print(f"{'='*70}\n")
            
            report = {}
            
            # Data Completeness
            print(f"1️⃣  Checking Data Completeness...")
            completeness = self.check_data_completeness(df, interval)
            report['completeness'] = completeness
            
            if completeness['ohlcv_complete']:
                print("   ✅ OHLCV data is complete (no nulls)")
            else:
                print(f"   ⚠️  Found null values: {completeness['null_values']}")
            
            print(f"   📅 Date range: {completeness['start_date']} to {completeness['end_date']}")
            print(f"   📊 Total bars: {len(df)}")
            print(f"   🕐 Intraday gaps: {completeness['gap_count']}")
            
            if completeness['duplicate_timestamps'] > 0:
                print(f"   ⚠️  Duplicate timestamps: {completeness['duplicate_timestamps']}")
            else:
                print("   ✅ No duplicate timestamps")
            
            # OHLC Validation
            print(f"\n2️⃣  Validating OHLC Relationships...")
            ohlc = self.validate_ohlc_relationships(df)
            report['ohlc'] = ohlc
            
            if ohlc['ohlc_valid']:
                print("   ✅ All OHLC relationships are valid")
            else:
                print(f"   ❌ High violations: {ohlc['high_violations']}")
                print(f"   ❌ Low violations: {ohlc['low_violations']}")
            
            if ohlc['zero_or_negative_prices'] > 0:
                print(f"   ❌ Zero/negative prices: {ohlc['zero_or_negative_prices']}")
            else:
                print("   ✅ No zero or negative prices")
            
            if ohlc['extreme_price_moves'] > 0:
                print(f"   ⚠️  Extreme price moves (>20%): {ohlc['extreme_price_moves']}")
            else:
                print("   ✅ No extreme price movements")
            
            # Volume Validation
            print(f"\n3️⃣  Validating Volume Data...")
            volume = self.validate_volume(df)
            report['volume'] = volume
            
            print(f"   📊 Average volume: {volume['avg_volume']:,.0f}")
            print(f"   📊 Median volume: {volume['median_volume']:,.0f}")
            
            if volume['zero_volume_bars'] > 0:
                print(f"   ⚠️  Zero volume bars: {volume['zero_volume_bars']}")
            else:
                print("   ✅ No zero volume bars")
            
            if volume['negative_volume_bars'] > 0:
                print(f"   ❌ Negative volume bars: {volume['negative_volume_bars']}")
            else:
                print("   ✅ No negative volume")
            
            if volume['volume_outliers'] > 0:
                print(f"   ℹ️  Volume outliers (>10x median): {volume['volume_outliers']}")
            
            # Bollinger Bands
            print(f"\n4️⃣  Validating Bollinger Bands...")
            bb = self.validate_bollinger_bands(df)
            report['bollinger_bands'] = bb
            
            if bb['bb_structure_violations'] > 0:
                print(f"   ❌ BB structure violations: {bb['bb_structure_violations']}")
            else:
                print("   ✅ BB structure is valid (Basis between Upper/Lower)")
            
            print(f"   📊 Price outside bands: {bb['price_outside_bands_pct']:.2f}%")
            if bb['bb_reasonable']:
                print("   ✅ BB breakouts are reasonable (<10%)")
            else:
                print("   ⚠️  High percentage of BB breakouts")
            
            # RSI
            print(f"\n5️⃣  Validating RSI Indicators...")
            rsi = self.validate_rsi(df)
            report['rsi'] = rsi
            
            if rsi['rsi_out_of_range'] > 0:
                print(f"   ❌ RSI out of range [0-100]: {rsi['rsi_out_of_range']}")
            else:
                print("   ✅ All RSI values in valid range [0-100]")
            
            print(f"   📊 RSI Mean: {rsi['rsi_mean']:.2f}")
            print(f"   📊 RSI Range: [{rsi['rsi_min']:.2f}, {rsi['rsi_max']:.2f}]")
            print(f"   📊 Overbought periods (>70): {rsi['overbought_pct']:.2f}%")
            print(f"   📊 Oversold periods (<30): {rsi['oversold_pct']:.2f}%")
            
            # ADX
            print(f"\n6️⃣  Validating ADX Indicators...")
            adx = self.validate_adx(df)
            report['adx'] = adx
            
            adx_valid = all(v == 0 for k, v in adx.items() if 'out_of_range' in k)
            if adx_valid:
                print("   ✅ All ADX values in valid range [0-100]")
            else:
                for k, v in adx.items():
                    if 'out_of_range' in k and v > 0:
                        print(f"   ❌ {k}: {v}")
            
            print(f"   📊 Strong trend periods (ADX>25): {adx['strong_trend_pct']:.2f}%")
            
            # Timestamp Consistency
            print(f"\n7️⃣  Checking Timestamp Consistency...")
            timestamps = self.check_timestamp_consistency(df, interval)
            report['timestamps'] = timestamps
            
            if timestamps['weekend_bars'] > 0:
                print(f"   ⚠️  Weekend data found: {timestamps['weekend_bars']} bars")
            else:
                print("   ✅ No weekend data")
            
            if timestamps['outside_market_hours'] > 0:
                print(f"   ⚠️  Data outside market hours: {timestamps['outside_market_hours']} bars")
            else:
                print("   ✅ All data within market hours")
            
            if timestamps['invalid_minute_marks'] > 0:
                print(f"   ⚠️  Invalid minute marks: {timestamps['invalid_minute_marks']}")
            else:
                print(f"   ✅ All timestamps align with {interval} intervals")
            
            self.health_report[interval] = report
        
        # Overall Assessment
        self._generate_overall_assessment()
        
        return True
    
    def _generate_overall_assessment(self):
        """Generate overall health assessment"""
        print("\n" + "="*70)
        print("📋 OVERALL HEALTH ASSESSMENT")
        print("="*70 + "\n")
        
        issues = []
        warnings = []
        
        for interval in ['15min', '60min']:
            report = self.health_report[interval]
            
            # Critical issues
            if not report['completeness']['ohlcv_complete']:
                issues.append(f"{interval}: Missing OHLCV data")
            
            if not report['ohlc']['ohlc_valid']:
                issues.append(f"{interval}: Invalid OHLC relationships")
            
            if report['ohlc']['zero_or_negative_prices'] > 0:
                issues.append(f"{interval}: Zero or negative prices detected")
            
            if report['volume']['negative_volume_bars'] > 0:
                issues.append(f"{interval}: Negative volume detected")
            
            if report['rsi']['rsi_out_of_range'] > 0:
                issues.append(f"{interval}: RSI values out of range")
            
            # Warnings
            if report['completeness']['gap_count'] > 5:
                warnings.append(f"{interval}: {report['completeness']['gap_count']} intraday gaps")
            
            if report['completeness']['duplicate_timestamps'] > 0:
                warnings.append(f"{interval}: Duplicate timestamps found")
            
            if not report['bollinger_bands']['bb_reasonable']:
                warnings.append(f"{interval}: High BB breakout percentage")
            
            if report['timestamps']['weekend_bars'] > 0:
                warnings.append(f"{interval}: Weekend data present")
        
        # Determine overall status
        if len(issues) == 0 and len(warnings) == 0:
            self.health_report['overall_status'] = 'HEALTHY'
            print("✅ **DATA HEALTH: EXCELLENT**")
            print("   All checks passed. Data is ready for analysis.")
        elif len(issues) == 0:
            self.health_report['overall_status'] = 'GOOD'
            print("✅ **DATA HEALTH: GOOD**")
            print("   No critical issues found. Some minor warnings:")
            for w in warnings:
                print(f"   ⚠️  {w}")
        else:
            self.health_report['overall_status'] = 'ISSUES_FOUND'
            print("❌ **DATA HEALTH: ISSUES DETECTED**")
            print("\n   Critical Issues:")
            for i in issues:
                print(f"   ❌ {i}")
            if warnings:
                print("\n   Warnings:")
                for w in warnings:
                    print(f"   ⚠️  {w}")
        
        print("\n" + "="*70)
        print("✅ Validation Complete")
        print("="*70 + "\n")


def main():
    """Main execution"""
    file_15min = "/Users/ericpeterson/SwiftBolt_ML/BATS_AAPL, 15_576d7.csv"
    file_60min = "/Users/ericpeterson/SwiftBolt_ML/BATS_AAPL, 60_7a5cf.csv"
    
    validator = IntradayDataHealthValidator(file_15min, file_60min)
    
    success = validator.run_validation()
    
    if not success:
        sys.exit(1)
    
    # Return exit code based on health status
    if validator.health_report['overall_status'] == 'ISSUES_FOUND':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
