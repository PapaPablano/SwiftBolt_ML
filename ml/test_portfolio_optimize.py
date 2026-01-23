#!/usr/bin/env python3
"""Test script for portfolio optimization endpoint.

Usage:
    python test_portfolio_optimize.py
    python test_portfolio_optimize.py --symbols AAPL,MSFT,GOOGL --method max_sharpe
    python test_portfolio_optimize.py --symbols AAPL,MSFT --method efficient --target-return 0.15
"""

import argparse
import json
import sys

import requests

# Default test parameters
DEFAULT_PARAMS = {
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "method": "max_sharpe",
    "lookbackDays": 252,
    "riskFreeRate": 0.02,
    "minWeight": 0.0,
    "maxWeight": 1.0,
}

FASTAPI_URL = "http://localhost:8000"


def test_portfolio_optimize(**kwargs):
    """Test portfolio optimization endpoint."""
    params = {**DEFAULT_PARAMS, **kwargs}
    
    print("=" * 70)
    print("Testing Portfolio Optimization")
    print("=" * 70)
    print(f"URL: {FASTAPI_URL}/api/v1/portfolio-optimize")
    print(f"Request: {json.dumps(params, indent=2)}")
    print()
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/api/v1/portfolio-optimize",
            json=params,
            timeout=120,  # 2 minutes timeout
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print()
            print("Results:")
            print(f"  Method: {result.get('method', 'N/A')}")
            print(f"  Symbols: {', '.join(result.get('symbols', []))}")
            print(f"  Lookback Days: {result.get('lookbackDays', 0)}")
            print()
            allocation = result.get('allocation', {})
            print("Allocation:")
            print(f"  Expected Return: {allocation.get('expectedReturn', 0):.2%}")
            print(f"  Volatility: {allocation.get('volatility', 0):.2%}")
            print(f"  Sharpe Ratio: {allocation.get('sharpeRatio', 0):.2f}")
            print()
            if allocation.get('weights'):
                print("Weights:")
                for symbol, weight in allocation['weights'].items():
                    print(f"  {symbol}: {weight:.2%}")
        else:
            print("❌ ERROR!")
            try:
                error = response.json()
                print(f"Error: {error.get('detail', 'Unknown error')}")
            except:
                print(f"Error: {response.text}")
        
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to FastAPI server.")
        print(f"   Make sure the server is running at {FASTAPI_URL}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test portfolio optimization endpoint")
    parser.add_argument("--symbols", help="Comma-separated list of symbols")
    parser.add_argument("--method", help="Optimization method (max_sharpe, min_variance, risk_parity, efficient)")
    parser.add_argument("--lookback-days", type=int, help="Lookback period in days")
    parser.add_argument("--risk-free-rate", type=float, help="Risk-free rate")
    parser.add_argument("--target-return", type=float, help="Target return (for efficient method)")
    parser.add_argument("--min-weight", type=float, help="Minimum weight per asset")
    parser.add_argument("--max-weight", type=float, help="Maximum weight per asset")
    
    args = parser.parse_args()
    
    kwargs = {}
    if args.symbols:
        kwargs["symbols"] = [s.strip().upper() for s in args.symbols.split(",")]
    if args.method:
        kwargs["method"] = args.method
    if args.lookback_days:
        kwargs["lookbackDays"] = args.lookback_days
    if args.risk_free_rate:
        kwargs["riskFreeRate"] = args.risk_free_rate
    if args.target_return:
        kwargs["targetReturn"] = args.target_return
    if args.min_weight:
        kwargs["minWeight"] = args.min_weight
    if args.max_weight:
        kwargs["maxWeight"] = args.max_weight
    
    success = test_portfolio_optimize(**kwargs)
    sys.exit(0 if success else 1)
