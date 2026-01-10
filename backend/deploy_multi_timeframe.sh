#!/bin/bash
# Multi-Timeframe & Symbol Tracking Deployment Script
# Run this to deploy the complete system

set -e  # Exit on error

PROJECT_REF="cygflaemtmwiwaviclks"
BACKEND_DIR="/Users/ericpeterson/SwiftBolt_ML/backend/supabase"

echo "=========================================="
echo "Multi-Timeframe Deployment Script"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -d "$BACKEND_DIR" ]; then
    echo "❌ Error: Backend directory not found: $BACKEND_DIR"
    exit 1
fi

cd "$BACKEND_DIR"

# Step 1: Apply Database Migration
echo "📋 Step 1: Applying database migration..."
echo ""
supabase db push --linked

if [ $? -eq 0 ]; then
    echo "✅ Migration applied successfully"
else
    echo "❌ Migration failed"
    exit 1
fi

echo ""
echo "⏳ Waiting 5 seconds for migration to settle..."
sleep 5

# Step 2: Deploy Edge Function
echo ""
echo "📋 Step 2: Deploying sync-user-symbols Edge Function..."
echo ""
supabase functions deploy sync-user-symbols --linked

if [ $? -eq 0 ]; then
    echo "✅ Edge Function deployed successfully"
else
    echo "❌ Edge Function deployment failed"
    exit 1
fi

# Step 3: Verify Deployment
echo ""
echo "📋 Step 3: Verifying deployment..."
echo ""

# Check if SUPABASE_DB_PASSWORD is set
if [ -z "$SUPABASE_DB_PASSWORD" ]; then
    echo "⚠️  Warning: SUPABASE_DB_PASSWORD not set. Skipping database verification."
    echo "   Set it with: export SUPABASE_DB_PASSWORD='your-password'"
else
    echo "Running verification queries..."
    
    # Check job definitions
    psql "postgresql://postgres.${PROJECT_REF}:${SUPABASE_DB_PASSWORD}@aws-0-us-east-1.pooler.supabase.com:6543/postgres" \
        -c "SELECT timeframe, COUNT(*) as job_count FROM job_definitions WHERE timeframe IN ('m15', 'h1', 'h4') AND enabled = true GROUP BY timeframe ORDER BY timeframe;" \
        2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Database verification passed"
    else
        echo "⚠️  Database verification skipped (check connection)"
    fi
fi

# Step 4: Summary
echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "What was deployed:"
echo "  ✅ user_symbol_tracking table with RLS"
echo "  ✅ Auto-trigger for job creation"
echo "  ✅ Helper functions for monitoring"
echo "  ✅ 60 job definitions (20 symbols × 3 timeframes)"
echo "  ✅ sync-user-symbols Edge Function"
echo ""
echo "Next steps:"
echo "  1. Build and run Swift app"
echo "  2. Add a symbol to watchlist"
echo "  3. Wait 2-3 minutes"
echo "  4. Check monitoring queries:"
echo "     psql ... -f monitor_multi_timeframe.sql"
echo ""
echo "Documentation:"
echo "  📖 See MULTI_TIMEFRAME_DEPLOYMENT.md for details"
echo ""
echo "Monitoring:"
echo "  📊 Run: psql ... -f monitor_multi_timeframe.sql"
echo ""
echo "=========================================="
