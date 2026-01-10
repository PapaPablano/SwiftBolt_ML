#!/usr/bin/env python3
"""
Verify database prices against Yahoo Finance
Checks if the newly fetched data is accurate
"""

import os
import sys
from datetime import datetime, timedelta

try:
    import yfinance as yf
    from supabase import create_client
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "supabase"])
    import yfinance as yf
    from supabase import create_client

# Load environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_symbol_prices(symbol, timeframe="d1", days_back=30):
    """Check if database prices match Yahoo Finance"""
    
    print(f"\n{'='*80}")
    print(f"🔍 Checking {symbol} ({timeframe}) - Last {days_back} days")
    print(f"{'='*80}\n")
    
    # Get symbol ID
    symbol_data = supabase.table("symbols").select("id").eq("ticker", symbol).execute()
    if not symbol_data.data:
        print(f"❌ Symbol {symbol} not found in database")
        return False
    
    symbol_id = symbol_data.data[0]["id"]
    
    # Get recent bars from database
    cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
    db_bars = supabase.table("ohlc_bars").select(
        "time,open,high,low,close,is_adjusted"
    ).eq("symbol_id", symbol_id).eq("timeframe", timeframe).gte(
        "time", cutoff_date
    ).order("time", desc=False).execute()
    
    if not db_bars.data:
        print(f"❌ No data found in database for {symbol}")
        return False
    
    print(f"📊 Database: {len(db_bars.data)} bars")
    print(f"📅 Date range: {db_bars.data[0]['time'][:10]} to {db_bars.data[-1]['time'][:10]}")
    print(f"🔧 Adjusted: {db_bars.data[0].get('is_adjusted', 'N/A')}")
    
    # Get Yahoo Finance data
    print(f"\n🌐 Fetching Yahoo Finance data...")
    ticker = yf.Ticker(symbol)
    yf_data = ticker.history(period=f"{days_back+5}d", interval="1d")
    
    if yf_data.empty:
        print(f"❌ No data from Yahoo Finance")
        return False
    
    print(f"✅ Yahoo Finance: {len(yf_data)} bars\n")
    
    # Compare prices
    discrepancies = []
    matches = 0
    
    for db_bar in db_bars.data[-10:]:  # Check last 10 days
        db_date = datetime.fromisoformat(db_bar["time"].replace("Z", "+00:00")).date()
        
        # Find matching Yahoo Finance bar
        yf_bar = None
        for idx, row in yf_data.iterrows():
            yf_date = idx.date() if hasattr(idx, 'date') else idx
            if yf_date == db_date:
                yf_bar = row
                break
        
        if yf_bar is None:
            continue
        
        # Calculate differences
        close_diff_pct = abs((db_bar["close"] - yf_bar["Close"]) / yf_bar["Close"] * 100)
        
        if close_diff_pct > 1.0:  # More than 1% difference
            discrepancies.append({
                "date": db_date,
                "db_close": db_bar["close"],
                "yf_close": yf_bar["Close"],
                "diff_pct": close_diff_pct
            })
        else:
            matches += 1
    
    # Report results
    print(f"📊 Comparison Results:")
    print(f"   ✅ Matches (within 1%): {matches}")
    print(f"   ❌ Discrepancies (>1%): {len(discrepancies)}\n")
    
    if discrepancies:
        print(f"❌ Found {len(discrepancies)} price discrepancies:\n")
        for disc in discrepancies[:5]:  # Show first 5
            print(f"📅 {disc['date']}")
            print(f"   DB Close:  ${disc['db_close']:8.2f}")
            print(f"   YF Close:  ${disc['yf_close']:8.2f}")
            print(f"   Diff:      {disc['diff_pct']:+6.2f}%\n")
        
        if len(discrepancies) > 5:
            print(f"... and {len(discrepancies) - 5} more\n")
        
        return False
    else:
        print("✅ All prices match within 1% tolerance!")
        
        # Show sample comparison
        print("\n📊 Sample comparison (last 3 days):\n")
        for db_bar in db_bars.data[-3:]:
            db_date = datetime.fromisoformat(db_bar["time"].replace("Z", "+00:00")).date()
            yf_bar = None
            for idx, row in yf_data.iterrows():
                yf_date = idx.date() if hasattr(idx, 'date') else idx
                if yf_date == db_date:
                    yf_bar = row
                    break
            
            if yf_bar is not None:
                print(f"📅 {db_date}")
                print(f"   Close: DB=${db_bar['close']:8.2f}  YF=${yf_bar['Close']:8.2f}")
        
        return True

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("🔍 DATABASE PRICE ACCURACY VALIDATOR")
    print("="*80)
    
    results = {}
    
    # Check NVDA
    results['NVDA'] = check_symbol_prices('NVDA', 'd1', days_back=30)
    
    # Check AAPL
    results['AAPL'] = check_symbol_prices('AAPL', 'd1', days_back=30)
    
    # Check TSLA
    results['TSLA'] = check_symbol_prices('TSLA', 'd1', days_back=30)
    
    # Final summary
    print("\n" + "="*80)
    print("📋 FINAL SUMMARY")
    print("="*80 + "\n")
    
    for symbol, result in results.items():
        status = "✅ ACCURATE" if result else "❌ DISCREPANCIES FOUND"
        print(f"{symbol:15s}: {status}")
    
    print("\n" + "="*80 + "\n")
    
    # Exit code
    if all(results.values()):
        print("🎉 SUCCESS: All database prices are accurate!")
        sys.exit(0)
    else:
        print("⚠️  WARNING: Some discrepancies found. May need re-export of CSV files.")
        sys.exit(1)

if __name__ == "__main__":
    main()
