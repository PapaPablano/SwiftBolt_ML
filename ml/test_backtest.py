#!/usr/bin/env python3
"""Test script for backtest strategy endpoint.

Usage:
    python test_backtest.py
    python test_backtest.py --symbol AAPL --strategy supertrend_ai
"""

import json
import sys
from datetime import datetime, timedelta

import requests

# Default test parameters
DEFAULT_PARAMS = {
    "symbol": "AAPL",
    "strategy": "supertrend_ai",
    "startDate": "2025-01-22",
    "endDate": "2026-01-22",
    "timeframe": "d1",
    "initialCapital": 10000,
    "params": {
        "atrLength": 10,
        "minMultiplier": 1.0,
        "maxMultiplier": 5.0,
    },
}

FASTAPI_URL = "http://localhost:8000"


def test_backtest(**kwargs):
    """Test backtest strategy endpoint."""
    params = {**DEFAULT_PARAMS, **kwargs}
    
    print("=" * 70)
    print("Testing Backtest Strategy")
    print("=" * 70)
    print(f"URL: {FASTAPI_URL}/api/v1/backtest-strategy")
    print(f"Request: {json.dumps(params, indent=2)}")
    print()
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/api/v1/backtest-strategy",
            json=params,
            timeout=300,  # 5 minutes timeout
        )
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(json.dumps(result, indent=2))
            
            # Print key metrics
            if "metrics" in result:
                metrics = result["metrics"]
                print()
                print("Key Metrics:")
                print(f"  Total Return: {result.get('totalReturn', 0):.2%}")
                print(f"  Total Trades: {metrics.get('totalTrades', 0)}")
                print(f"  Sharpe Ratio: {metrics.get('sharpeRatio', 0):.2f}")
                print(f"  Max Drawdown: {metrics.get('maxDrawdown', 0):.2%}")
        else:
            print("❌ ERROR!")
            try:
                error = response.json()
                print(json.dumps(error, indent=2))
            except:
                print(response.text)
        
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test backtest strategy")
    parser.add_argument("--symbol", default="AAPL", help="Symbol to test")
    parser.add_argument("--strategy", default="supertrend_ai", 
                       choices=["supertrend_ai", "sma_crossover", "buy_and_hold"])
    parser.add_argument("--start-date", default="2025-01-22", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-01-22", help="End date (YYYY-MM-DD)")
    parser.add_argument("--timeframe", default="d1", help="Timeframe")
    parser.add_argument("--initial-capital", type=int, default=10000, help="Initial capital")
    
    args = parser.parse_args()
    
    kwargs = {
        "symbol": args.symbol,
        "strategy": args.strategy,
        "startDate": args.start_date,
        "endDate": args.end_date,
        "timeframe": args.timeframe,
        "initialCapital": args.initial_capital,
    }
    
    success = test_backtest(**kwargs)
    sys.exit(0 if success else 1)
