#!/usr/bin/env python3
"""Debug NVDA price swing issue on November 1st, 2025."""

import os
import sys
from datetime import datetime, timedelta
from supabase import create_client, Client
import requests

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cygflaemtmwiwaviclks.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if not SUPABASE_KEY or not POLYGON_API_KEY:
    print("❌ Missing SUPABASE_SERVICE_KEY or POLYGON_API_KEY")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 80)
print("🔍 NVDA Price Swing Debug - November 1st, 2025")
print("=" * 80)

# 1. Get NVDA symbol ID
print("\n1️⃣ Looking up NVDA symbol...")
symbol_result = supabase.table("symbols").select("id,ticker").eq("ticker", "NVDA").execute()
if not symbol_result.data:
    print("❌ NVDA not found in symbols table")
    sys.exit(1)

symbol_id = symbol_result.data[0]["id"]
print(f"✅ Found NVDA: {symbol_id}")

# 2. Check database data around Nov 1st
print("\n2️⃣ Checking ohlc_bars_v2 table (Oct 30 - Nov 5, 2025)...")
db_bars = supabase.table("ohlc_bars_v2").select(
    "ts,open,high,low,close,volume,provider,is_intraday,is_forecast,data_status"
).eq("symbol_id", symbol_id).eq("timeframe", "d1").gte(
    "ts", "2025-10-30T00:00:00Z"
).lte(
    "ts", "2025-11-05T23:59:59Z"
).order("ts", desc=False).execute()

print(f"\n📊 Database has {len(db_bars.data)} bars:")
print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12} {'Provider':<10} {'Status'}")
print("-" * 100)

prev_close = None
for bar in db_bars.data:
    date = bar['ts'][:10]
    open_price = bar['open']
    high = bar['high']
    low = bar['low']
    close = bar['close']
    volume = bar['volume']
    provider = bar['provider']
    status = bar['data_status']
    
    # Calculate swing from previous close
    swing = ""
    if prev_close:
        pct_change = ((open_price - prev_close) / prev_close) * 100
        if abs(pct_change) > 5:
            swing = f"🚨 {pct_change:+.1f}%"
        else:
            swing = f"{pct_change:+.1f}%"
    
    print(f"{date:<12} {open_price:>10.2f} {high:>10.2f} {low:>10.2f} {close:>10.2f} {volume:>12,.0f} {provider:<10} {status:<10} {swing}")
    prev_close = close

# 3. Check Polygon API directly
print("\n3️⃣ Checking Polygon API (unadjusted)...")
polygon_url = f"https://api.polygon.io/v2/aggs/ticker/NVDA/range/1/day/2025-10-30/2025-11-05"
params = {"adjusted": "false", "apiKey": POLYGON_API_KEY}
response = requests.get(polygon_url, params=params)

if response.status_code == 200:
    polygon_data = response.json()
    if polygon_data.get("results"):
        print(f"\n📊 Polygon API has {len(polygon_data['results'])} bars:")
        print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
        print("-" * 80)
        
        prev_close = None
        for bar in polygon_data["results"]:
            timestamp = bar['t'] / 1000
            date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            open_price = bar['o']
            high = bar['h']
            low = bar['l']
            close = bar['c']
            volume = bar['v']
            
            swing = ""
            if prev_close:
                pct_change = ((open_price - prev_close) / prev_close) * 100
                if abs(pct_change) > 5:
                    swing = f"🚨 {pct_change:+.1f}%"
                else:
                    swing = f"{pct_change:+.1f}%"
            
            print(f"{date:<12} {open_price:>10.2f} {high:>10.2f} {low:>10.2f} {close:>10.2f} {volume:>12,.0f} {swing}")
            prev_close = close
    else:
        print("❌ No results from Polygon API")
else:
    print(f"❌ Polygon API error: {response.status_code}")

# 4. Check for stock splits
print("\n4️⃣ Checking for stock splits...")
splits_url = f"https://api.polygon.io/v3/reference/splits?ticker=NVDA&execution_date.gte=2025-10-01&execution_date.lte=2025-11-30"
splits_response = requests.get(splits_url, params={"apiKey": POLYGON_API_KEY})

if splits_response.status_code == 200:
    splits_data = splits_response.json()
    if splits_data.get("results"):
        print(f"⚠️  Found {len(splits_data['results'])} split(s):")
        for split in splits_data["results"]:
            print(f"   - Date: {split['execution_date']}, Ratio: {split['split_from']}:{split['split_to']}")
    else:
        print("✅ No splits found in this period")
else:
    print(f"❌ Splits API error: {splits_response.status_code}")

# 5. Check chart-data-v2 endpoint
print("\n5️⃣ Testing chart-data-v2 Edge Function...")
chart_url = f"{SUPABASE_URL}/functions/v1/chart-data-v2"
chart_response = requests.post(
    chart_url,
    json={"symbol": "NVDA", "days": 10, "includeForecast": False},
    headers={"Content-Type": "application/json"}
)

if chart_response.status_code == 200:
    chart_data = chart_response.json()
    historical = chart_data.get("layers", {}).get("historical", {}).get("data", [])
    
    print(f"\n📊 Edge Function returns {len(historical)} historical bars")
    if historical:
        print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10}")
        print("-" * 60)
        
        prev_close = None
        for bar in historical:
            if '2025-10-3' in bar['ts'] or '2025-11-0' in bar['ts']:
                date = bar['ts'][:10]
                open_price = bar['open']
                high = bar['high']
                low = bar['low']
                close = bar['close']
                
                swing = ""
                if prev_close:
                    pct_change = ((open_price - prev_close) / prev_close) * 100
                    if abs(pct_change) > 5:
                        swing = f"🚨 {pct_change:+.1f}%"
                    else:
                        swing = f"{pct_change:+.1f}%"
                
                print(f"{date:<12} {open_price:>10.2f} {high:>10.2f} {low:>10.2f} {close:>10.2f} {swing}")
                prev_close = close
else:
    print(f"❌ Edge Function error: {chart_response.status_code}")
    print(chart_response.text[:500])

print("\n" + "=" * 80)
print("🔍 Debug complete. Check for 🚨 markers indicating >5% swings.")
print("=" * 80)
