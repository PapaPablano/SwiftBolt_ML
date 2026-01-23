#!/usr/bin/env python3
"""Test script for stress testing endpoint.

Usage:
    python test_stress_test.py
    python test_stress_test.py --scenario 2008_financial_crisis
    python test_stress_test.py --custom-shocks '{"AAPL": -0.20, "MSFT": -0.15}'
"""

import argparse
import json
import sys

import requests

# Default test parameters
DEFAULT_PARAMS = {
    "positions": {"AAPL": 100, "MSFT": 50, "GOOGL": 30},
    "prices": {"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 120.0},
    "scenario": "2008_financial_crisis",
    "varLevel": 0.05,
}

FASTAPI_URL = "http://localhost:8000"


def test_stress_test(**kwargs):
    """Test stress testing endpoint."""
    params = {**DEFAULT_PARAMS, **kwargs}
    
    # Handle custom shocks if provided
    if "customShocks" in kwargs:
        params["scenario"] = None  # Clear scenario if custom shocks provided
    
    print("=" * 70)
    print("Testing Stress Test")
    print("=" * 70)
    print(f"URL: {FASTAPI_URL}/api/v1/stress-test")
    print(f"Request: {json.dumps(params, indent=2)}")
    print()
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/api/v1/stress-test",
            json=params,
            timeout=60,
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print()
            print("Results:")
            print(f"  Scenario: {result.get('scenario', 'N/A')}")
            print(f"  Portfolio Value: ${result.get('portfolio', {}).get('currentValue', 0):,.2f}")
            print(f"  Change: ${result.get('portfolio', {}).get('change', 0):,.2f}")
            print(f"  Change %: {result.get('portfolio', {}).get('changePercent', 0):.2%}")
            print(f"  Severity: {result.get('risk', {}).get('severity', 'N/A')}")
            print(f"  VaR Breached: {result.get('risk', {}).get('varBreached', False)}")
            print()
            if result.get('positionChanges'):
                print("Position Changes:")
                for symbol, change in result['positionChanges'].items():
                    print(f"  {symbol}: ${change:,.2f}")
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
    parser = argparse.ArgumentParser(description="Test stress testing endpoint")
    parser.add_argument("--scenario", help="Historical scenario name")
    parser.add_argument("--custom-shocks", help="JSON dict of custom shocks")
    parser.add_argument("--positions", help="JSON dict of positions")
    parser.add_argument("--prices", help="JSON dict of prices")
    parser.add_argument("--var-level", type=float, help="VaR confidence level")
    
    args = parser.parse_args()
    
    kwargs = {}
    if args.scenario:
        kwargs["scenario"] = args.scenario
    if args.custom_shocks:
        kwargs["customShocks"] = json.loads(args.custom_shocks)
    if args.positions:
        kwargs["positions"] = json.loads(args.positions)
    if args.prices:
        kwargs["prices"] = json.loads(args.prices)
    if args.var_level:
        kwargs["varLevel"] = args.var_level
    
    success = test_stress_test(**kwargs)
    sys.exit(0 if success else 1)
