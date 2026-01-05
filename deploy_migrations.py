"""
Deploy migrations to Supabase database.
Executes SQL migration files directly through the Supabase client.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "ml"))

from src.data.supabase_db import db

def execute_sql_file(filepath: str) -> bool:
    """Execute a SQL file against the database."""
    try:
        with open(filepath, 'r') as f:
            sql = f.read()
        
        print(f"\n{'='*60}")
        print(f"Executing: {filepath}")
        print(f"{'='*60}")
        
        # Execute the SQL
        result = db.client.rpc('exec_sql', {'sql': sql}).execute()
        
        print(f"✅ Successfully executed {filepath}")
        return True
        
    except Exception as e:
        print(f"❌ Error executing {filepath}: {e}")
        
        # Try executing directly if RPC doesn't exist
        try:
            print("Attempting direct execution...")
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            
            for i, stmt in enumerate(statements, 1):
                if stmt:
                    print(f"  Executing statement {i}/{len(statements)}...")
                    db.client.postgrest.session.execute_sql(stmt)
            
            print(f"✅ Successfully executed {filepath} (direct method)")
            return True
            
        except Exception as e2:
            print(f"❌ Direct execution also failed: {e2}")
            print("\nPlease execute this SQL manually in Supabase dashboard:")
            print(f"File: {filepath}")
            return False

def main():
    """Deploy all pending migrations."""
    migrations_dir = Path(__file__).parent / "backend" / "supabase" / "migrations"
    
    # Migration files to execute in order
    migration_files = [
        "20260105000000_ohlc_bars_v2.sql",
        "20260105000001_migrate_to_v2.sql",
    ]
    
    print("\n🚀 Starting migration deployment")
    print(f"Migrations directory: {migrations_dir}")
    
    success_count = 0
    failed_count = 0
    
    for filename in migration_files:
        filepath = migrations_dir / filename
        
        if not filepath.exists():
            print(f"⚠️  Migration file not found: {filepath}")
            failed_count += 1
            continue
        
        if execute_sql_file(str(filepath)):
            success_count += 1
        else:
            failed_count += 1
    
    print(f"\n{'='*60}")
    print("MIGRATION DEPLOYMENT SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {failed_count}")
    
    if failed_count > 0:
        print("\n⚠️  Some migrations failed. Please execute them manually.")
        print("You can find the SQL files in:")
        print(f"  {migrations_dir}")
        return 1
    
    print("\n✅ All migrations deployed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
