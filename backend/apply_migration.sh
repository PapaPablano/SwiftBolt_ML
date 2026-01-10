#!/bin/bash
# Apply migration to Supabase database
# Run this script OR copy the SQL to Supabase SQL Editor

PROJECT_REF="cygflaemtmwiwaviclks"
SUPABASE_URL="https://${PROJECT_REF}.supabase.co"

echo "=============================================="
echo "  Apply Alpaca Provider Migration"
echo "=============================================="
echo ""
echo "Option 1: Copy the SQL below to Supabase SQL Editor:"
echo "https://supabase.com/dashboard/project/${PROJECT_REF}/sql"
echo ""
echo "Option 2: Set SUPABASE_DB_PASSWORD and run:"
echo "  SUPABASE_DB_PASSWORD=your_password ./apply_migration.sh --auto"
echo ""
echo "=============================================="

# If --auto flag is passed, run the migration automatically
if [ "$1" = "--auto" ]; then
    if [ -z "$SUPABASE_DB_PASSWORD" ]; then
        echo "ERROR: SUPABASE_DB_PASSWORD environment variable not set"
        exit 1
    fi

    echo "Running migration..."
    npx supabase db push --project-ref ${PROJECT_REF} --password "$SUPABASE_DB_PASSWORD"
    exit $?
fi

echo ""
echo "==================== COPY SQL BELOW ===================="
echo ""
cat /Users/ericpeterson/SwiftBolt_ML/backend/supabase/migrations/20260110000000_add_alpaca_provider_support.sql
echo ""
echo "==================== END SQL =========================="
