#!/usr/bin/env python3
"""
Test script for forecast quality API endpoint.
Tests the /api/v1/forecast-quality endpoint directly.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

# Add parent directory to path
ml_dir = Path(__file__).parent
sys.path.insert(0, str(ml_dir))

BASE_URL = "http://localhost:8000"


def test_forecast_quality(symbol: str, horizon: str = "1D", timeframe: str = "d1"):
    """Test the forecast-quality endpoint."""
    url = f"{BASE_URL}/api/v1/forecast-quality"
    
    payload = {
        "symbol": symbol.upper(),
        "horizon": horizon,
        "timeframe": timeframe,
    }
    
    print(f"Testing Forecast Quality API: {symbol} ({horizon}, {timeframe})")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"Symbol: {result['symbol']}")
            print(f"Horizon: {result['horizon']}")
            print(f"Timeframe: {result['timeframe']}")
            print(f"\nQuality Metrics:")
            print(f"  Quality Score: {result['qualityScore']:.3f}")
            print(f"  Confidence: {result['confidence']:.2%}")
            print(f"  Model Agreement: {result['modelAgreement']:.2%}")
            print(f"  Issues Found: {len(result['issues'])}")
            
            if result['issues']:
                print(f"\nIssues:")
                for issue in result['issues']:
                    print(f"  [{issue['level'].upper()}] {issue['type']}: {issue['message']}")
                    print(f"    Action: {issue['action']}")
            else:
                print("\n✅ No quality issues detected")
            
            print(f"\nTimestamp: {result['timestamp']}")
            return result
        else:
            print("❌ ERROR!")
            try:
                error = response.json()
                print(f"Error: {error.get('detail', 'Unknown error')}")
            except:
                print(f"Error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to FastAPI server.")
        print("Make sure the server is running: cd ml && uvicorn api.main:app --reload")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test forecast quality API")
    parser.add_argument("--symbol", default="AAPL", help="Stock ticker symbol")
    parser.add_argument("--horizon", default="1D", help="Forecast horizon (1D, 1W, etc.)")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    
    args = parser.parse_args()
    
    result = test_forecast_quality(
        symbol=args.symbol,
        horizon=args.horizon,
        timeframe=args.timeframe,
    )
    
    if result:
        print("\n" + "="*60)
        print("Full Response:")
        print("="*60)
        print(json.dumps(result, indent=2))
