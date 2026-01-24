#!/usr/bin/env python3
"""
Test script for model training API endpoint.
Tests the /api/v1/train-model endpoint directly.
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


def test_train_model(symbol: str, timeframe: str = "d1", lookback_days: int = 90):
    """Test the train-model endpoint."""
    url = f"{BASE_URL}/api/v1/train-model"
    
    payload = {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "lookbackDays": lookback_days,
    }
    
    print(f"Testing Model Training API: {symbol} ({timeframe})")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=300)  # 5 minute timeout for training
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"Symbol: {result['symbol']}")
            print(f"Timeframe: {result['timeframe']}")
            print(f"Status: {result['status']}")
            print(f"\nTraining Metrics:")
            print(f"  Train Accuracy: {result['trainingMetrics']['trainAccuracy']:.2%}")
            print(f"  Validation Accuracy: {result['trainingMetrics']['validationAccuracy']:.2%}")
            print(f"  Test Accuracy: {result['trainingMetrics']['testAccuracy']:.2%}")
            print(f"  Train Samples: {result['trainingMetrics']['trainSamples']}")
            print(f"  Validation Samples: {result['trainingMetrics']['validationSamples']}")
            print(f"  Test Samples: {result['trainingMetrics']['testSamples']}")
            print(f"\nModel Info:")
            print(f"  Model Hash: {result['modelInfo']['modelHash']}")
            print(f"  Feature Count: {result['modelInfo']['featureCount']}")
            print(f"  Trained At: {result['modelInfo']['trainedAt']}")
            if result.get('ensembleWeights'):
                print(f"\nEnsemble Weights:")
                for model, weight in result['ensembleWeights'].items():
                    print(f"  {model}: {weight:.3f}")
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
    parser = argparse.ArgumentParser(description="Test model training API")
    parser.add_argument("--symbol", default="AAPL", help="Stock ticker symbol")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    parser.add_argument("--lookback-days", type=int, default=90, help="Lookback days")
    
    args = parser.parse_args()
    
    result = test_train_model(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_days=args.lookback_days,
    )
    
    if result:
        print("\n" + "="*60)
        print("Full Response:")
        print("="*60)
        print(json.dumps(result, indent=2))
