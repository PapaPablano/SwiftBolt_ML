#!/bin/bash
# Quick fix for intraday data - triggers backfill via API

set -e

echo "============================================"
echo "Quick Intraday Data Fix"
echo "============================================"
echo ""

# Load environment variables
if [ -f ".env" ]; then
  echo "Loading .env file..."
  export $(cat .env | grep -v '^#' | xargs)
fi

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo "❌ Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in .env"
  echo ""
  echo "Please set these in backend/.env:"
  echo "  SUPABASE_URL=https://your-project.supabase.co"
  echo "  SUPABASE_SERVICE_ROLE_KEY=your-service-role-key"
  exit 1
fi

echo "✅ Environment variables loaded"
echo ""

# Step 1: Check current status via edge function
echo "Step 1: Checking current provider distribution..."
echo "-------------------------------------------"

CHART_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"h1","days":60}' \
  "$SUPABASE_URL/functions/v1/chart-data-v2")

echo "$CHART_RESPONSE" | jq '.metadata, .layers.historical.provider, .layers.intraday.provider' 2>/dev/null || echo "$CHART_RESPONSE"

echo ""
echo ""

# Step 2: Trigger coverage check (this will create backfill jobs if needed)
echo "Step 2: Triggering coverage check for AAPL h1..."
echo "-------------------------------------------"

COVERAGE_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"h1","windowDays":730}' \
  "$SUPABASE_URL/functions/v1/ensure-coverage")

echo "$COVERAGE_RESPONSE" | jq '.' 2>/dev/null || echo "$COVERAGE_RESPONSE"

echo ""
echo ""

# Step 3: Same for NVDA
echo "Step 3: Triggering coverage check for NVDA h1..."
echo "-------------------------------------------"

COVERAGE_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NVDA","timeframe":"h1","windowDays":730}' \
  "$SUPABASE_URL/functions/v1/ensure-coverage")

echo "$COVERAGE_RESPONSE" | jq '.' 2>/dev/null || echo "$COVERAGE_RESPONSE"

echo ""
echo ""

# Step 4: Trigger backfill worker
echo "Step 4: Triggering backfill worker to process chunks..."
echo "-------------------------------------------"

for i in {1..3}; do
  echo "Worker run #$i..."
  WORKER_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    "$SUPABASE_URL/functions/v1/run-backfill-worker")

  echo "$WORKER_RESPONSE" | jq '.' 2>/dev/null || echo "$WORKER_RESPONSE"
  echo ""

  # Small delay between runs
  if [ $i -lt 3 ]; then
    sleep 2
  fi
done

echo ""
echo "============================================"
echo "✅ Done!"
echo "============================================"
echo ""
echo "The backfill worker has been triggered."
echo "It will continue processing in the background."
echo ""
echo "To check progress, run this script again or check:"
echo "  $SUPABASE_URL/functions/v1/chart-data-v2"
echo ""
echo "Expected timeline:"
echo "  - 5-10 minutes: First chunks complete"
echo "  - 30-60 minutes: Full 2-year history"
echo ""
