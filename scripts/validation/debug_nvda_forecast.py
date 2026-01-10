#!/usr/bin/env python3
"""
Debug script to examine NVDA ML forecast data for anomalies.
Checks for spikes or unusual values in forecast points.
"""

import os
import sys
from datetime import datetime, timedelta
import json

# Add ml/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ml', 'src'))

from data.supabase_db import SupabaseDatabase

def check_nvda_forecasts():
    """Check NVDA forecast data for anomalies around June 10th."""
    db = SupabaseDatabase()
    
    # Get NVDA symbol_id
    symbol_id = db.get_symbol_id("NVDA")
    if not symbol_id:
        print("ERROR: NVDA symbol not found")
        return
    
    print(f"NVDA symbol_id: {symbol_id}")
    print("\n" + "="*80)
    
    # Query ml_forecasts for NVDA
    response = db.supabase.table("ml_forecasts").select(
        "id, horizon, overall_label, confidence, points, run_at, created_at"
    ).eq("symbol_id", symbol_id).order("run_at", desc=True).limit(10).execute()
    
    if not response.data:
        print("No forecasts found for NVDA")
        return
    
    print(f"\nFound {len(response.data)} recent forecasts for NVDA\n")
    
    # Get recent OHLC data for context (from v2 - real Alpaca data)
    ohlc_response = db.supabase.table("ohlc_bars_v2").select(
        "ts, close, high, low"
    ).eq("symbol_id", symbol_id).eq("timeframe", "d1").eq(
        "provider", "alpaca"
    ).eq("is_forecast", False).order(
        "ts", desc=True
    ).limit(100).execute()
    
    recent_prices = {}
    if ohlc_response.data:
        for bar in ohlc_response.data:
            ts = bar["ts"][:10]  # Just date
            recent_prices[ts] = {
                "close": float(bar["close"]),
                "high": float(bar["high"]),
                "low": float(bar["low"])
            }
    
    # Check each forecast
    for i, forecast in enumerate(response.data):
        print(f"\n{'='*80}")
        print(f"Forecast #{i+1}")
        print(f"{'='*80}")
        print(f"ID: {forecast['id']}")
        print(f"Horizon: {forecast['horizon']}")
        print(f"Label: {forecast['overall_label']}")
        print(f"Confidence: {forecast['confidence']}")
        print(f"Run at: {forecast['run_at']}")
        print(f"Created: {forecast['created_at']}")
        
        points = forecast.get("points", [])
        if not points:
            print("  No points data")
            continue
        
        print(f"\nPoints count: {len(points)}")
        print("\nAnalyzing forecast points:")
        print(f"{'Date':<12} {'Value':>10} {'Lower':>10} {'Upper':>10} {'ActualClose':>12} {'Deviation':>10}")
        print("-" * 80)
        
        anomalies = []
        
        for point in points:
            ts = point.get("ts", "")
            value = float(point.get("value", 0))
            lower = float(point.get("lower", 0))
            upper = float(point.get("upper", 0))
            
            # Parse timestamp
            if isinstance(ts, int):
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            else:
                date_str = ts[:10] if len(ts) >= 10 else ts
            
            # Get actual price for comparison
            actual_close = recent_prices.get(date_str, {}).get("close", 0)
            actual_high = recent_prices.get(date_str, {}).get("high", 0)
            actual_low = recent_prices.get(date_str, {}).get("low", 0)
            
            # Calculate deviation
            deviation = ""
            if actual_close > 0:
                pct_diff = ((value - actual_close) / actual_close) * 100
                deviation = f"{pct_diff:+.1f}%"
                
                # Flag anomalies (>20% deviation or values outside reasonable range)
                if abs(pct_diff) > 20:
                    anomalies.append({
                        "date": date_str,
                        "forecast_value": value,
                        "actual_close": actual_close,
                        "deviation_pct": pct_diff
                    })
            
            # Check if forecast value is way outside actual price range
            if actual_high > 0 and actual_low > 0:
                if value > actual_high * 1.5 or value < actual_low * 0.5:
                    anomalies.append({
                        "date": date_str,
                        "forecast_value": value,
                        "actual_range": f"{actual_low:.2f}-{actual_high:.2f}",
                        "issue": "Outside reasonable range"
                    })
            
            print(f"{date_str:<12} {value:>10.2f} {lower:>10.2f} {upper:>10.2f} {actual_close:>12.2f} {deviation:>10}")
        
        # Report anomalies
        if anomalies:
            print(f"\n⚠️  ANOMALIES DETECTED ({len(anomalies)}):")
            for anomaly in anomalies:
                print(f"  - {json.dumps(anomaly, indent=4)}")
        else:
            print("\n✓ No major anomalies detected in this forecast")
    
    print("\n" + "="*80)
    print("Analysis complete")

if __name__ == "__main__":
    check_nvda_forecasts()
