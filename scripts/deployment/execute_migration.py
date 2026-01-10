#!/usr/bin/env python3
"""Execute SQL migration files directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "ml"))

from src.data.supabase_db import db


def execute_migration(filepath: str):
    """Execute a SQL migration file."""
    print(f"\nExecuting: {filepath}")
    print("=" * 60)
    
    with open(filepath, 'r') as f:
        sql = f.read()
    
    # Split into individual statements and execute
    statements = []
    current = []
    
    for line in sql.split('\n'):
        # Skip comments
        if line.strip().startswith('--'):
            continue
        current.append(line)
        if ';' in line:
            stmt = '\n'.join(current).strip()
            if stmt and not stmt.startswith('COMMENT'):
                statements.append(stmt)
            current = []
    
    print(f"Found {len(statements)} statements to execute")
    
    for i, stmt in enumerate(statements, 1):
        try:
            # Use raw SQL execution
            response = db.client.postgrest.session.post(
                f"{db.client.supabase_url}/rest/v1/rpc/exec_sql",
                json={"query": stmt},
                headers=db.client.postgrest.session.headers
            )
            
            if response.status_code not in (200, 201, 204):
                print(f"  [{i}/{len(statements)}] ⚠️  Status {response.status_code}")
            else:
                print(f"  [{i}/{len(statements)}] ✅")
                
        except Exception as e:
            print(f"  [{i}/{len(statements)}] ❌ Error: {e}")
            # Continue with next statement
    
    print("✅ Migration execution completed\n")


if __name__ == "__main__":
    migrations = [
        "backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql",
        "backend/supabase/migrations/20260105000001_migrate_to_v2.sql",
    ]
    
    for migration in migrations:
        filepath = Path(__file__).parent / migration
        if filepath.exists():
            execute_migration(str(filepath))
        else:
            print(f"❌ File not found: {filepath}")
