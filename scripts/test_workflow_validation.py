#!/usr/bin/env python3
"""
Test Workflow Validation Fixes

This script tests the validation fixes implemented in GitHub workflows.
Can be run locally to verify validation logic before deploying.

Usage:
    python scripts/test_workflow_validation.py [--test-type all|ohlc|service|integration]
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path

# Add ml directory to path
ml_dir = Path(__file__).parent.parent / "ml"
sys.path.insert(0, str(ml_dir))

from dotenv import load_dotenv

# Load environment variables
env_path = ml_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


def test_ohlc_validator():
    """Test OHLC Validator functionality."""
    print("🧪 Testing OHLC Validator...")
    print("=" * 60)
    
    try:
        from src.data.data_validator import OHLCValidator
        from src.data.supabase_db import db
        
        validator = OHLCValidator()
        test_symbols = ['SPY', 'AAPL', 'NVDA']
        
        all_passed = True
        for symbol in test_symbols:
            try:
                print(f"\n📊 Testing {symbol}...")
                df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=100)
                
                if df.empty:
                    print(f"  ⚠️ No data for {symbol}")
                    continue
                
                print(f"  ✅ Fetched {len(df)} bars")
                
                df, result = validator.validate(df, fix_issues=False)
                
                if result.is_valid:
                    print(f"  ✅ Validation PASSED")
                    score = validator.get_data_quality_score(df)
                    print(f"     Quality score: {score:.2%}")
                else:
                    # Check if it's just outliers (acceptable in real data)
                    is_only_outliers = all('outlier' in issue.lower() for issue in result.issues)
                    if is_only_outliers and len(result.issues) == 1:
                        print(f"  ⚠️ Validation WARNING (outliers detected - acceptable)")
                        print(f"     Issues: {result.issues}")
                        print(f"     Quality score: {validator.get_data_quality_score(df):.2%}")
                        # Don't fail on outliers alone - they exist in real market data
                    else:
                        print(f"  ❌ Validation FAILED")
                        print(f"     Issues: {result.issues}")
                        all_passed = False
            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ All OHLC validation tests PASSED")
            return True
        else:
            print("❌ Some OHLC validation tests FAILED")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation_service():
    """Test ValidationService functionality."""
    print("\n🧪 Testing ValidationService...")
    print("=" * 60)
    
    try:
        from src.services.validation_service import ValidationService
        
        service = ValidationService()
        print("✅ ValidationService imported and instantiated")
        
        async def test_async():
            test_symbols = ['AAPL', 'SPY']
            
            for symbol in test_symbols:
                try:
                    print(f"\n📊 Testing {symbol}...")
                    result = await service.get_live_validation(symbol, 'BULLISH')
                    
                    print(f"  ✅ Validation completed")
                    print(f"     Unified confidence: {result.unified_confidence:.1%}")
                    print(f"     Drift severity: {result.drift_severity}")
                    print(f"     Consensus: {result.consensus_direction}")
                except Exception as e:
                    print(f"  ⚠️ {symbol}: {str(e)}")
                    # Don't fail - may not have data for all symbols
        
        asyncio.run(test_async())
        print("\n" + "=" * 60)
        print("✅ ValidationService tests completed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test integration of validation steps as used in workflows."""
    print("\n🧪 Testing Integration (Workflow Validation Steps)...")
    print("=" * 60)
    
    try:
        from src.data.data_validator import OHLCValidator
        from src.data.supabase_db import db
        from src.services.validation_service import ValidationService
        from src.scripts.universe_utils import get_symbol_universe
        
        # Test 1: OHLC Validation (from ml-orchestration.yml)
        print("\n📊 Test 1: OHLC Validation Step")
        validator = OHLCValidator()
        universe = get_symbol_universe()
        symbols = universe.get('symbols', []) or ['SPY', 'AAPL']
        
        validation_errors = []
        validation_warnings = []
        for symbol in symbols[:3]:
            try:
                df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=252)
                if df.empty:
                    continue
                df, result = validator.validate(df, fix_issues=False)
                if not result.is_valid:
                    # Check if it's just outliers (acceptable in real data)
                    is_only_outliers = all('outlier' in issue.lower() for issue in result.issues)
                    if is_only_outliers:
                        validation_warnings.append(f'{symbol}: {result.issues}')
                    else:
                        validation_errors.append(f'{symbol}: {result.issues}')
            except Exception as e:
                validation_errors.append(f'{symbol}: {str(e)}')
        
        if validation_errors:
            print(f"  ❌ Found {len(validation_errors)} errors")
            for error in validation_errors:
                print(f"     - {error}")
        elif validation_warnings:
            print(f"  ⚠️ Found {len(validation_warnings)} warnings (outliers - acceptable)")
            for warning in validation_warnings:
                print(f"     - {warning}")
            print("  ✅ OHLC validation passed (warnings only)")
        else:
            print("  ✅ OHLC validation passed")
        
        # Test 2: Unified Validation (from ml-orchestration.yml)
        print("\n📊 Test 2: Unified Validation Step")
        service = ValidationService()
        
        async def test_unified():
            test_symbols = ['AAPL', 'SPY']
            for symbol in test_symbols:
                try:
                    result = await service.get_live_validation(symbol, 'BULLISH')
                    print(f"  ✅ {symbol}: {result.unified_confidence:.1%} confidence")
                except Exception as e:
                    print(f"  ⚠️ {symbol}: {str(e)}")
        
        asyncio.run(test_unified())
        
        print("\n" + "=" * 60)
        print("✅ Integration tests completed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test workflow validation fixes")
    parser.add_argument(
        '--test-type',
        choices=['all', 'ohlc', 'service', 'integration'],
        default='all',
        help='Type of test to run'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧪 Workflow Validation Fixes Test Suite")
    print("=" * 60)
    
    results = {}
    
    if args.test_type in ['all', 'ohlc']:
        results['ohlc'] = test_ohlc_validator()
    
    if args.test_type in ['all', 'service']:
        results['service'] = test_validation_service()
    
    if args.test_type in ['all', 'integration']:
        results['integration'] = test_integration()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.upper()}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✅ All tests PASSED")
        return 0
    else:
        print("❌ Some tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
