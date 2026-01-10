#!/usr/bin/env python3
"""
Price Accuracy Validator - Compares CSV data against real market prices
Uses yfinance to fetch actual historical data and compare
"""

import pandas as pd
import glob
import sys

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf


def check_symbol_accuracy(symbol, csv_pattern, sample_dates=None):
    """Check price accuracy for a given symbol"""
    
    # Find CSV file
    csv_files = glob.glob(csv_pattern)
    if not csv_files:
        print(f"❌ No CSV file found for pattern: {csv_pattern}")
        return None
    
    print(f"\n{'='*80}")
    print(f"🔍 Checking {symbol} Price Accuracy")
    print(f"{'='*80}\n")
    print(f"📁 CSV File: {csv_files[0]}")
    
    # Read CSV
    df_csv = pd.read_csv(csv_files[0])
    df_csv['time'] = pd.to_datetime(df_csv['time'], utc=True)
    if df_csv['time'].dt.tz is not None:
        df_csv['time'] = df_csv['time'].dt.tz_localize(None)
    df_csv = df_csv.sort_values('time')
    
    # Get date range
    start_date = df_csv['time'].min()
    end_date = df_csv['time'].max()
    
    print(f"📅 CSV Date Range: {start_date.date()} to {end_date.date()}")
    print(f"📊 Total bars in CSV: {len(df_csv)}")
    
    # Fetch real market data
    print(f"\n🌐 Fetching actual market data from Yahoo Finance...")
    ticker = yf.Ticker(symbol)
    
    # Determine interval based on data frequency
    time_diff = (df_csv['time'].iloc[1] - df_csv['time'].iloc[0]).total_seconds()
    if time_diff < 3600:  # Less than 1 hour
        interval = '15m' if time_diff < 1800 else '1h'
        period = '60d'  # yfinance limit for intraday
    else:
        interval = '1d'
        period = 'max'
    
    try:
        df_real = ticker.history(period=period, interval=interval)
        df_real = df_real.reset_index()
        
        # Normalize column names
        if 'Date' in df_real.columns:
            df_real = df_real.rename(columns={'Date': 'time'})
        elif 'Datetime' in df_real.columns:
            df_real = df_real.rename(columns={'Datetime': 'time'})
        
        df_real['time'] = pd.to_datetime(df_real['time'])
        if df_real['time'].dt.tz is not None:
            df_real['time'] = df_real['time'].dt.tz_localize(None)
        
        # Filter to CSV date range
        df_real = df_real[
            (df_real['time'] >= start_date) & 
            (df_real['time'] <= end_date)
        ]
        
        print(f"✅ Fetched {len(df_real)} bars from Yahoo Finance")
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None
    
    # Compare prices
    print(f"\n📊 Comparing Prices...")
    print(f"{'='*80}\n")
    
    discrepancies = []
    
    # Merge on date (normalize to date only for daily data)
    if interval == '1d':
        df_csv['date'] = df_csv['time'].dt.date
        df_real['date'] = df_real['time'].dt.date
        merge_key = 'date'
    else:
        # For intraday, round to nearest interval
        df_csv['time_rounded'] = df_csv['time'].dt.floor('15min')
        df_real['time_rounded'] = df_real['time'].dt.floor('15min')
        merge_key = 'time_rounded'
    
    # Merge datasets
    merged = pd.merge(
        df_csv,
        df_real,
        on=merge_key,
        suffixes=('_csv', '_real'),
        how='inner'
    )
    
    if len(merged) == 0:
        print("⚠️  No matching dates found between CSV and real data")
        return None
    
    print(f"📍 Matched {len(merged)} data points\n")
    
    # Calculate differences
    for col in ['Open', 'High', 'Low', 'Close']:
        csv_col = 'open' if col == 'Open' else col.lower()
        real_col = col
        
        if csv_col in merged.columns and real_col in merged.columns:
            merged[f'{col}_diff'] = merged[csv_col] - merged[real_col]
            merged[f'{col}_diff_pct'] = (
                (merged[csv_col] - merged[real_col]) / merged[real_col] * 100
            )
    
    # Find significant discrepancies (>1% difference)
    threshold = 1.0  # 1% threshold
    
    for idx, row in merged.iterrows():
        issues = []
        for col in ['Open', 'High', 'Low', 'Close']:
            diff_pct_col = f'{col}_diff_pct'
            if diff_pct_col in row and abs(row[diff_pct_col]) > threshold:
                csv_col = 'open' if col == 'Open' else col.lower()
                issues.append({
                    'field': col,
                    'csv_value': row[csv_col],
                    'real_value': row[col],
                    'diff_pct': row[diff_pct_col]
                })
        
        if issues:
            discrepancies.append({
                'date': row['time_csv'] if 'time_csv' in row else row['date'],
                'issues': issues
            })
    
    # Report findings
    if discrepancies:
        print(f"❌ Found {len(discrepancies)} dates with price discrepancies >1%:\n")
        
        for disc in discrepancies[:20]:  # Show first 20
            print(f"📅 {disc['date']}")
            for issue in disc['issues']:
                print(f"   {issue['field']:6s}: CSV=${issue['csv_value']:8.2f}  "
                      f"Real=${issue['real_value']:8.2f}  "
                      f"Diff={issue['diff_pct']:+6.2f}%")
            print()
        
        if len(discrepancies) > 20:
            print(f"... and {len(discrepancies) - 20} more discrepancies\n")
        
        # Summary statistics
        print(f"\n{'='*80}")
        print(f"📊 Summary Statistics")
        print(f"{'='*80}\n")
        
        for col in ['Open', 'High', 'Low', 'Close']:
            diff_col = f'{col}_diff'
            diff_pct_col = f'{col}_diff_pct'
            
            if diff_pct_col in merged.columns:
                mean_diff = merged[diff_pct_col].mean()
                max_diff = merged[diff_pct_col].abs().max()
                std_diff = merged[diff_pct_col].std()
                
                print(f"{col:6s}: Mean Diff={mean_diff:+6.2f}%  "
                      f"Max Diff={max_diff:6.2f}%  StdDev={std_diff:5.2f}%")
        
        return False
    else:
        print("✅ All prices match within 1% tolerance!")
        print("\n📊 Sample comparison (first 5 dates):\n")
        
        sample = merged.head(5)
        for idx, row in sample.iterrows():
            date = row['time_csv'] if 'time_csv' in row else row['date']
            print(f"📅 {date}")
            print(f"   Close: CSV=${row['close']:8.2f}  Real=${row['Close']:8.2f}")
        
        return True


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("🔍 PRICE ACCURACY VALIDATOR")
    print("="*80)
    
    results = {}
    
    # Check NVDA daily
    results['NVDA_1D'] = check_symbol_accuracy('NVDA', '*NVDA*1D*.csv')
    
    # Check AAPL 15min
    results['AAPL_15m'] = check_symbol_accuracy('AAPL', '*AAPL*15*.csv')
    
    # Check AAPL 60min
    results['AAPL_60m'] = check_symbol_accuracy('AAPL', '*AAPL*60*.csv')
    
    # Final summary
    print("\n" + "="*80)
    print("📋 FINAL SUMMARY")
    print("="*80 + "\n")
    
    for key, result in results.items():
        if result is None:
            status = "⚠️  SKIPPED"
        elif result:
            status = "✅ ACCURATE"
        else:
            status = "❌ DISCREPANCIES FOUND"
        
        print(f"{key:15s}: {status}")
    
    print("\n" + "="*80 + "\n")
    
    # Exit code
    if any(r is False for r in results.values()):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
