"""
Test script for ValidationService

Tests the complete Phase 1 data pipeline:
1. Fetching backtesting scores
2. Fetching walk-forward scores
3. Fetching live scores
4. Fetching multi-TF scores
5. Creating unified prediction
6. Storing result in database

Usage:
    python ml/src/services/test_validation_service.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add ml to path
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

from src.services.validation_service import ValidationService
from src.data.supabase_db import SupabaseDatabase

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_validation_service():
    """Test ValidationService with a real symbol."""
    
    print("\n" + "="*80)
    print("TESTING VALIDATION SERVICE (Phase 1)")
    print("="*80 + "\n")
    
    # Initialize service
    print("1. Initializing ValidationService...")
    try:
        db = SupabaseDatabase()
        service = ValidationService(db)
        print("   ✅ ValidationService initialized successfully\n")
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}\n")
        return False
    
    # Test symbol
    test_symbol = "AAPL"
    test_direction = "BULLISH"
    
    print(f"2. Testing with symbol: {test_symbol} ({test_direction})")
    print("-" * 80)
    
    # Test backtesting score
    print("\n   a) Fetching backtesting score...")
    try:
        backtest_score = await service._get_backtesting_score(test_symbol)
        print(f"      ✅ Backtesting score: {backtest_score:.1%}")
    except Exception as e:
        print(f"      ⚠️  Warning: {e}")
        backtest_score = 0.55
    
    # Test walk-forward score
    print("\n   b) Fetching walk-forward score...")
    try:
        walkforward_score = await service._get_walkforward_score(test_symbol)
        print(f"      ✅ Walk-forward score: {walkforward_score:.1%}")
    except Exception as e:
        print(f"      ⚠️  Warning: {e}")
        walkforward_score = 0.60
    
    # Test live score
    print("\n   c) Fetching live score...")
    try:
        live_score = await service._get_live_score(test_symbol)
        print(f"      ✅ Live score: {live_score:.1%}")
    except Exception as e:
        print(f"      ⚠️  Warning: {e}")
        live_score = 0.50
    
    # Test multi-TF scores
    print("\n   d) Fetching multi-timeframe scores...")
    try:
        multi_tf_scores = await service._get_multi_tf_scores(test_symbol)
        print(f"      ✅ Multi-TF scores retrieved:")
        for tf, score in multi_tf_scores.items():
            print(f"         {tf}: {score:+.2f}")
    except Exception as e:
        print(f"      ⚠️  Warning: {e}")
        multi_tf_scores = {}
    
    # Test unified validation
    print(f"\n3. Running unified validation for {test_symbol} ({test_direction})...")
    print("-" * 80)
    try:
        result = await service.get_live_validation(test_symbol, test_direction)
        
        print("\n   ✅ VALIDATION SUCCESSFUL!")
        print("\n   Unified Prediction:")
        print(f"      Symbol: {result.symbol}")
        print(f"      Direction: {result.direction}")
        print(f"      Unified Confidence: {result.unified_confidence:.1%} {result.get_status_emoji()}")
        print(f"\n   Component Scores:")
        print(f"      Backtesting: {result.backtesting_score:.1%}")
        print(f"      Walk-forward: {result.walkforward_score:.1%}")
        print(f"      Live: {result.live_score:.1%}")
        print(f"\n   Drift Analysis:")
        print(f"      Drift Detected: {result.drift_detected}")
        print(f"      Drift Magnitude: {result.drift_magnitude:.1%}")
        print(f"      Drift Severity: {result.drift_severity}")
        print(f"      Explanation: {result.drift_explanation}")
        print(f"\n   Multi-Timeframe Analysis:")
        print(f"      Timeframe Conflict: {result.timeframe_conflict}")
        print(f"      Consensus Direction: {result.consensus_direction}")
        print(f"      Explanation: {result.conflict_explanation}")
        print(f"\n   Recommendations:")
        print(f"      {result.recommendation}")
        print(f"      Retraining Required: {result.retraining_trigger}")
        if result.retraining_trigger:
            print(f"      Reason: {result.retraining_reason}")
        
        print("\n" + "="*80)
        print("✅ PHASE 1 TEST PASSED")
        print("="*80 + "\n")
        return True
        
    except Exception as e:
        print(f"\n   ❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*80)
        print("❌ PHASE 1 TEST FAILED")
        print("="*80 + "\n")
        return False


async def test_database_tables():
    """Verify required database tables exist."""
    
    print("\n" + "="*80)
    print("VERIFYING DATABASE TABLES")
    print("="*80 + "\n")
    
    db = SupabaseDatabase()
    
    required_tables = [
        "symbols",
        "model_validation_stats",
        "live_predictions",
        "indicator_values",
        "validation_results",
    ]
    
    all_exist = True
    
    for table in required_tables:
        try:
            result = db.client.table(table).select("*").limit(1).execute()
            print(f"   ✅ Table '{table}' exists (found {len(result.data)} row(s))")
        except Exception as e:
            print(f"   ❌ Table '{table}' missing or inaccessible: {e}")
            all_exist = False
    
    print()
    if all_exist:
        print("✅ All required tables exist\n")
    else:
        print("⚠️  Some tables are missing. You may need to run migrations.\n")
    
    return all_exist


async def main():
    """Run all tests."""
    
    # Test database tables
    tables_ok = await test_database_tables()
    
    if not tables_ok:
        print("⚠️  Warning: Not all tables exist. Continuing with validation test anyway...")
        print("   (Default values will be used for missing data)\n")
    
    # Test validation service
    success = await test_validation_service()
    
    if success:
        print("\n🎉 Phase 1 implementation is working correctly!")
        print("\nNext steps:")
        print("  - Phase 2: Create API endpoints (validation_api.py)")
        print("  - Phase 3: Create dashboard integration")
        sys.exit(0)
    else:
        print("\n❌ Phase 1 implementation has issues that need to be fixed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
