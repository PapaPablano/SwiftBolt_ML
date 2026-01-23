#!/bin/bash
# Script to apply the entry/exit ranking migration to Supabase
# Usage: ./scripts/run_migration.sh

set -e  # Exit on error

echo "======================================"
echo "Entry/Exit Ranking Migration"
echo "======================================"
echo ""

# Get Supabase project details
echo "📋 Project Info:"
echo "   Database: Supabase PostgreSQL"
echo "   Migration: Add entry_rank, exit_rank, and component scores"
echo ""

# Confirm before proceeding
read -p "🔐 Apply migration to production database? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Migration cancelled"
    exit 1
fi

echo ""
echo "🔄 Applying migration..."
echo ""

# Option 1: Using Supabase CLI (if available)
if command -v supabase &> /dev/null; then
    echo "Using Supabase CLI..."
    supabase db push --dry-run supabase/migrations/20260123_add_entry_exit_rankings.sql
    
    read -p "Dry run complete. Proceed with actual migration? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        supabase db push supabase/migrations/20260123_add_entry_exit_rankings.sql
        echo "✅ Migration applied via Supabase CLI"
    else
        echo "❌ Migration cancelled"
        exit 1
    fi
else
    # Option 2: Manual instructions
    echo "⚠️  Supabase CLI not found"
    echo ""
    echo "📝 Manual Migration Steps:"
    echo "   1. Go to your Supabase project: https://supabase.com/dashboard"
    echo "   2. Navigate to: SQL Editor"
    echo "   3. Copy the contents of: supabase/migrations/20260123_add_entry_exit_rankings.sql"
    echo "   4. Paste into SQL Editor and click 'Run'"
    echo ""
    echo "   Or use psql:"
    echo "   psql \$DATABASE_URL -f supabase/migrations/20260123_add_entry_exit_rankings.sql"
    echo ""
    exit 0
fi

echo ""
echo "🔍 Running verification..."
echo ""

# Run verification (if Supabase CLI is available)
if command -v supabase &> /dev/null; then
    supabase db execute < scripts/verify_ranking_migration.sql
else
    echo "Run verification manually:"
    echo "psql \$DATABASE_URL -f scripts/verify_ranking_migration.sql"
fi

echo ""
echo "======================================"
echo "✅ Migration Complete!"
echo "======================================"
echo ""
echo "📊 Next Steps:"
echo "   1. Review verification output above"
echo "   2. Run Python ranking job with new modes:"
echo "      python -m src.options_ranking_job --symbol AAPL --mode entry"
echo "      python -m src.options_ranking_job --symbol AAPL --mode exit"
echo "   3. Check that entry_rank and exit_rank are populated"
echo "   4. Deploy frontend with mode selector"
echo ""
echo "🔄 To rollback (if needed):"
echo "   psql \$DATABASE_URL -f supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql"
echo ""
