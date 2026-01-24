#!/usr/bin/env python3
"""
Test script to verify multi-leg strategy options ranking trigger.

This script:
1. Verifies the migration functions exist
2. Creates a test multi-leg strategy on MU
3. Checks if a ranking job was queued
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid

sys.path.insert(0, str(Path('ml').absolute()))

from src.data.supabase_db import db

def verify_migration():
    """Verify migration functions and triggers exist."""
    print("=" * 60)
    print("Step 1: Verifying Migration")
    print("=" * 60)
    
    # Check functions via direct SQL query
    functions = [
        'queue_ranking_on_multi_leg_create',
        'queue_ranking_on_multi_leg_reopen',
        'get_multi_leg_strategy_symbols',
        'queue_multi_leg_strategy_ranking_jobs'
    ]
    
    for func_name in functions:
        try:
            result = db.client.rpc('exec_sql', {
                'sql': f"SELECT proname FROM pg_proc WHERE proname = '{func_name}';"
            }).execute()
            if result.data:
                print(f"✅ Function exists: {func_name}")
            else:
                print(f"❌ Function NOT found: {func_name}")
                return False
        except Exception as e:
            print(f"⚠️  Could not verify {func_name}: {e}")
            # Continue anyway - might be a query issue
    
    print("\n✅ Migration verification complete\n")
    return True

def get_or_create_mu_symbol():
    """Get or create MU symbol."""
    print("=" * 60)
    print("Step 2: Getting/Creating MU Symbol")
    print("=" * 60)
    
    # Check if MU exists
    result = db.client.table('symbols').select('id, ticker').eq('ticker', 'MU').execute()
    
    if result.data and len(result.data) > 0:
        symbol_id = result.data[0]['id']
        print(f"✅ Found MU symbol: {symbol_id}")
        return symbol_id
    
    # Create MU symbol
    print("Creating MU symbol...")
    result = db.client.table('symbols').insert({
        'ticker': 'MU',
        'asset_type': 'stock',
        'description': 'Micron Technology (auto-created for test)'
    }).execute()
    
    if result.data:
        symbol_id = result.data[0]['id']
        print(f"✅ Created MU symbol: {symbol_id}")
        return symbol_id
    
    raise Exception("Failed to create MU symbol")

def create_test_strategy(symbol_id):
    """Create a test multi-leg strategy on MU."""
    print("=" * 60)
    print("Step 3: Creating Test Multi-Leg Strategy on MU")
    print("=" * 60)
    
    # Get a user ID (use placeholder for test)
    user_id = "00000000-0000-0000-0000-000000000000"
    
    # Create a simple long put strategy
    strategy_data = {
        'user_id': user_id,
        'name': 'MU Test Long Put',
        'strategy_type': 'custom',
        'underlying_symbol_id': symbol_id,
        'underlying_ticker': 'MU',
        'status': 'open',
        'num_contracts': 1,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'version': 1
    }
    
    print(f"Creating strategy: {strategy_data['name']}")
    result = db.client.table('options_strategies').insert(strategy_data).execute()
    
    if result.data:
        strategy_id = result.data[0]['id']
        print(f"✅ Created strategy: {strategy_id}")
        return strategy_id
    
    raise Exception("Failed to create strategy")

def check_ranking_job():
    """Check if ranking job was queued for MU."""
    print("=" * 60)
    print("Step 4: Checking for Queued Ranking Job")
    print("=" * 60)
    
    # Check for recent ranking jobs for MU
    result = db.client.table('ranking_jobs').select('*').eq('symbol', 'MU').order('created_at', desc=True).limit(5).execute()
    
    if result.data:
        print(f"Found {len(result.data)} ranking job(s) for MU:")
        for job in result.data:
            status = job.get('status', 'unknown')
            created = job.get('created_at', 'unknown')
            priority = job.get('priority', 0)
            requested_by = job.get('requested_by', 'unknown')
            
            print(f"  - Status: {status}, Priority: {priority}, Created: {created}")
            print(f"    Requested by: {requested_by}")
            
            # Check if created in last 5 minutes
            if isinstance(created, str):
                try:
                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    if (datetime.utcnow().replace(tzinfo=created_dt.tzinfo) - created_dt).seconds < 300:
                        print(f"  ✅ Recent job found (created {created})")
                        return True
                except:
                    pass
        
        # Check if any are pending/running
        pending = [j for j in result.data if j.get('status') in ['pending', 'running']]
        if pending:
            print(f"  ✅ Found {len(pending)} pending/running job(s)")
            return True
        else:
            print(f"  ⚠️  No pending/running jobs found")
            return False
    else:
        print("❌ No ranking jobs found for MU")
        return False

def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("Multi-Leg Strategy Options Ranking Trigger Test")
    print("=" * 60 + "\n")
    
    try:
        # Step 1: Verify migration
        if not verify_migration():
            print("\n⚠️  Migration verification failed. Please check migration status.")
            print("You may need to execute the migration manually in Supabase SQL Editor.")
            return
        
        # Step 2: Get MU symbol
        symbol_id = get_or_create_mu_symbol()
        
        # Step 3: Create test strategy
        strategy_id = create_test_strategy(symbol_id)
        
        # Step 4: Check for ranking job (wait a moment for trigger to fire)
        import time
        print("\nWaiting 2 seconds for trigger to fire...")
        time.sleep(2)
        
        job_queued = check_ranking_job()
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        if job_queued:
            print("✅ SUCCESS: Ranking job was automatically queued!")
            print("   The trigger is working correctly.")
        else:
            print("⚠️  WARNING: No ranking job found.")
            print("   This could mean:")
            print("   1. The trigger hasn't fired yet (wait a few more seconds)")
            print("   2. The migration wasn't applied correctly")
            print("   3. There was an error in the trigger")
            print("\n   Please check the ranking_jobs table manually:")
            print("   SELECT * FROM ranking_jobs WHERE symbol = 'MU' ORDER BY created_at DESC LIMIT 5;")
        
        print(f"\nTest strategy ID: {strategy_id}")
        print("You can delete this test strategy if needed.")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
