#!/usr/bin/env python3
"""Test script for walk-forward optimization endpoint.

Usage:
    python test_walk_forward.py
    python test_walk_forward.py --symbol AAPL --horizon 1D
"""

import json
import sys
from pathlib import Path

import requests

# Default test parameters
DEFAULT_PARAMS = {
    "symbol": "AAPL",
    "horizon": "1D",
    "forecaster": "baseline",
    "timeframe": "d1",
    "trainWindow": None,  # Auto
    "testWindow": None,   # Auto
    "stepSize": None,     # Auto
}

FASTAPI_URL = "http://localhost:8000"


def test_walk_forward(**kwargs):
    """Test walk-forward optimization endpoint."""
    params = {**DEFAULT_PARAMS, **kwargs}
    
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}
    
    print("=" * 70)
    print("Testing Walk-Forward Optimization")
    print("=" * 70)
    print(f"URL: {FASTAPI_URL}/api/v1/walk-forward-optimize")
    print(f"Request: {json.dumps(params, indent=2)}")
    print()
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/api/v1/walk-forward-optimize",
            json=params,
            timeout=300,  # 5 minutes timeout
        )
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(json.dumps(result, indent=2))
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
    
    parser = argparse.ArgumentParser(description="Test walk-forward optimization")
    parser.add_argument("--symbol", default="AAPL", help="Symbol to test")
    parser.add_argument("--horizon", default="1D", help="Forecast horizon")
    parser.add_argument("--forecaster", default="baseline", choices=["baseline", "enhanced"])
    parser.add_argument("--timeframe", default="d1", help="Timeframe")
    parser.add_argument("--train-window", type=int, help="Training window size")
    parser.add_argument("--test-window", type=int, help="Test window size")
    parser.add_argument("--step-size", type=int, help="Step size")
    
    args = parser.parse_args()
    
    kwargs = {
        "symbol": args.symbol,
        "horizon": args.horizon,
        "forecaster": args.forecaster,
        "timeframe": args.timeframe,
    }
    
    if args.train_window:
        kwargs["trainWindow"] = args.train_window
    if args.test_window:
        kwargs["testWindow"] = args.test_window
    if args.step_size:
        kwargs["stepSize"] = args.step_size
    
    success = test_walk_forward(**kwargs)
    sys.exit(0 if success else 1)
