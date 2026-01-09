#!/bin/bash
# Phase 2 Batch Backfill Deployment Script
# Deploys all Phase 2 components for 50-symbol batch processing

set -e

PROJECT_REF="cygflaemtmwiwaviclks"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SUPABASE_DIR="$BACKEND_DIR/supabase"

echo "=========================================="
echo "Phase 2 Batch Backfill Deployment"
echo "=========================================="
echo ""

# Step 1: Apply database migration
echo "Step 1: Applying database migration..."
cd "$SUPABASE_DIR"

if [ -f "migrations/20260109000000_add_symbols_array.sql" ]; then
  echo "  - Applying symbols_array column migration..."
  supabase db push --linked
  echo "  ✓ Migration applied"
else
  echo "  ⚠ Migration file not found, skipping"
fi

echo ""

# Step 2: Deploy batch-backfill-orchestrator
echo "Step 2: Deploying batch-backfill-orchestrator..."
supabase functions deploy batch-backfill-orchestrator --no-verify-jwt

echo "  ✓ batch-backfill-orchestrator deployed"
echo ""

# Step 3: Deploy updated fetch-bars (with batch detection)
echo "Step 3: Deploying updated fetch-bars..."
supabase functions deploy fetch-bars --no-verify-jwt

echo "  ✓ fetch-bars deployed (now batch-aware)"
echo ""

# Step 4: Verify fetch-bars-batch is deployed
echo "Step 4: Verifying fetch-bars-batch..."
supabase functions list | grep -q "fetch-bars-batch" && \
  echo "  ✓ fetch-bars-batch already deployed" || \
  (echo "  ⚠ fetch-bars-batch not found, deploying..." && \
   supabase functions deploy fetch-bars-batch --no-verify-jwt)

echo ""

# Step 5: Verify environment variables
echo "Step 5: Checking environment variables..."
echo "  Required variables:"
echo "    - SUPABASE_URL"
echo "    - SUPABASE_SERVICE_ROLE_KEY"
echo "    - ALPACA_API_KEY"
echo "    - ALPACA_API_SECRET"
echo ""
echo "  Please verify these are set in Supabase Dashboard:"
echo "  https://supabase.com/dashboard/project/$PROJECT_REF/settings/functions"
echo ""

# Step 6: Test deployment
echo "Step 6: Testing batch orchestrator..."
echo "  Run this command to test:"
echo ""
echo "  curl -X POST \\"
echo "    'https://$PROJECT_REF.supabase.co/functions/v1/batch-backfill-orchestrator' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'Authorization: Bearer \$SUPABASE_SERVICE_ROLE_KEY' \\"
echo "    -d '{\"symbols\": [\"AAPL\", \"MSFT\", \"GOOGL\"], \"timeframes\": [\"d1\"]}'"
echo ""

echo "=========================================="
echo "Phase 2 Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Run validation queries (see backend/scripts/validate-phase2.sql)"
echo "  2. Trigger a test batch backfill via GitHub Actions"
echo "  3. Monitor job_definitions table for batch jobs"
echo "  4. Check job_runs for batch execution results"
echo ""
echo "Expected improvements:"
echo "  - Jobs: 5000+ → ~100-150 (50-symbol batches)"
echo "  - API calls: 5000+ → ~100-150"
echo "  - Runtime: ~2.4 hours → ~1-2 hours"
echo "  - Rate limit usage: 95% → <10%"
echo ""
