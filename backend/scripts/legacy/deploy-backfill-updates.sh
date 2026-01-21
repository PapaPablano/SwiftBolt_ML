#!/bin/bash
# Deploy updated backfill functions with Alpaca support

set -e

echo "============================================"
echo "Deploying Backfill Updates"
echo "============================================"
echo ""

cd /Users/ericpeterson/SwiftBolt_ML

# Check which directory has the run-backfill-worker
if [ -d "supabase/functions/run-backfill-worker" ]; then
  FUNCTIONS_DIR="supabase/functions"
  echo "Using supabase/functions directory"
elif [ -d "backend/supabase/functions/run-backfill-worker" ]; then
  FUNCTIONS_DIR="backend/supabase/functions"
  echo "Using backend/supabase/functions directory"
else
  echo "❌ Error: Cannot find run-backfill-worker function"
  exit 1
fi

echo ""
echo "Deploying functions from: $FUNCTIONS_DIR"
echo ""

# Deploy the backfill worker
echo "1. Deploying run-backfill-worker..."
echo "-------------------------------------------"

cd "${FUNCTIONS_DIR}/.." 2>/dev/null || cd "backend"

npx supabase functions deploy run-backfill-worker --no-verify-jwt 2>&1

echo ""
echo ""

# Also deploy the provider factory and backfill adapter shared code
echo "2. Shared code will be included automatically in deployment"
echo ""

echo "============================================"
echo "✅ Deployment Complete!"
echo "============================================"
echo ""
echo "The updated code is now live:"
echo "  • Alpaca as primary provider"
echo "  • Proper provider names in database"
echo "  • No more Polygon/Massive fallback"
echo ""
echo "Now run the backfill trigger again:"
echo "  cd backend && ./scripts/simple-backfill-trigger.sh"
echo ""
