#!/usr/bin/env python3
"""
Diagnostic script to test job worker dependencies and identify failure causes.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test all required imports."""
    print("=" * 60)
    print("Testing Imports...")
    print("=" * 60)
    
    try:
        from config.settings import settings
        print("✅ config.settings imported successfully")
        print(f"   SUPABASE_URL: {settings.supabase_url[:30]}...")
        print(f"   SUPABASE_KEY configured: {bool(settings.supabase_key)}")
    except Exception as e:
        print(f"❌ Failed to import config.settings: {e}")
        return False
    
    try:
        from src.data.supabase_db import SupabaseDatabase
        print("✅ SupabaseDatabase imported successfully")
    except Exception as e:
        print(f"❌ Failed to import SupabaseDatabase: {e}")
        return False
    
    try:
        from src.features.technical_indicators import add_technical_features
        print("✅ technical_indicators imported successfully")
    except Exception as e:
        print(f"❌ Failed to import technical_indicators: {e}")
        return False
    
    try:
        from src.models.baseline_forecaster import BaselineForecaster
        print("✅ BaselineForecaster imported successfully")
    except Exception as e:
        print(f"❌ Failed to import BaselineForecaster: {e}")
        return False
    
    try:
        from src.strategies.supertrend_ai import SuperTrendAI
        print("✅ SuperTrendAI imported successfully")
    except Exception as e:
        print(f"❌ Failed to import SuperTrendAI: {e}")
        return False
    
    return True


def test_database_connection():
    """Test database connection and required functions."""
    print("\n" + "=" * 60)
    print("Testing Database Connection...")
    print("=" * 60)
    
    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
        print("✅ Database connection established")
        
        # Test claim_next_job function exists
        try:
            result = db.client.rpc("claim_next_job", {"p_job_type": "forecast"}).execute()
            print(f"✅ claim_next_job function exists (returned {len(result.data)} jobs)")
        except Exception as e:
            print(f"❌ claim_next_job function error: {e}")
            return False
        
        # Test complete_job function exists
        try:
            # This will fail with invalid UUID but proves function exists
            db.client.rpc("complete_job", {
                "p_job_id": "00000000-0000-0000-0000-000000000000",
                "p_success": True,
                "p_error": None
            }).execute()
        except Exception as e:
            if "does not exist" in str(e).lower():
                print(f"❌ complete_job function missing: {e}")
                return False
            else:
                print("✅ complete_job function exists")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_ranking_worker():
    """Test ranking worker dependencies."""
    print("\n" + "=" * 60)
    print("Testing Ranking Worker...")
    print("=" * 60)
    
    try:
        from src.data.supabase_db import db
        print("✅ Ranking worker db imported successfully")
        
        # Test get_next_ranking_job function
        try:
            result = db.client.rpc("get_next_ranking_job").execute()
            print(f"✅ get_next_ranking_job function exists (returned {len(result.data)} jobs)")
        except Exception as e:
            print(f"❌ get_next_ranking_job function error: {e}")
            return False
        
        # Check if options_ranking_job.py exists
        script_path = Path(__file__).parent / "src" / "options_ranking_job.py"
        if script_path.exists():
            print(f"✅ options_ranking_job.py exists at {script_path}")
        else:
            print(f"❌ options_ranking_job.py not found at {script_path}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ranking worker test failed: {e}")
        return False


def main():
    """Run all diagnostic tests."""
    print("\n" + "=" * 60)
    print("JOB WORKER DIAGNOSTIC TEST")
    print("=" * 60 + "\n")
    
    results = {
        "Imports": test_imports(),
        "Database Connection": test_database_connection(),
        "Ranking Worker": test_ranking_worker(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ All tests passed! Job worker should be functional.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
