#!/bin/bash
# Data Health Check Script
# Tests all components of the multi-provider pipeline

set -e

echo "🔍 SwiftBolt Data Health Check"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if SUPABASE_ANON_KEY is set
if [ -z "$SUPABASE_ANON_KEY" ]; then
  echo -e "${YELLOW}⚠️  SUPABASE_ANON_KEY not set${NC}"
  echo "   Get it from: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api"
  echo ""
  echo "   Then run:"
  echo "   export SUPABASE_ANON_KEY='your-anon-key-here'"
  echo "   ./test-data-health.sh"
  echo ""
  exit 1
fi

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"

echo "1️⃣  Testing Edge Function Endpoints..."
echo "   ----------------------------------"

# Test trigger-backfill endpoint
echo -n "   Trigger endpoint: "
TRIGGER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$SUPABASE_URL/functions/v1/trigger-backfill" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' 2>/dev/null || echo "000")

HTTP_CODE=$(echo "$TRIGGER_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ]; then
  echo -e "${GREEN}✅ Working${NC}"
else
  echo -e "${RED}❌ Failed (HTTP $HTTP_CODE)${NC}"
fi

# Test run-backfill-worker endpoint
echo -n "   Worker endpoint: "
WORKER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$SUPABASE_URL/functions/v1/run-backfill-worker" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' 2>/dev/null || echo "000")

HTTP_CODE=$(echo "$WORKER_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ]; then
  RESPONSE_BODY=$(echo "$WORKER_RESPONSE" | head -n -1)
  PROCESSED=$(echo "$RESPONSE_BODY" | jq -r '.processed // 0' 2>/dev/null || echo "0")
  echo -e "${GREEN}✅ Working (processed $PROCESSED chunks)${NC}"
else
  echo -e "${RED}❌ Failed (HTTP $HTTP_CODE)${NC}"
fi

echo ""
echo "2️⃣  Checking Database Connection..."
echo "   ---------------------------------"

# Test chart-data-v2 endpoint (this queries the database)
echo -n "   Chart data API: "
CHART_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$SUPABASE_URL/functions/v1/chart-data-v2" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"h1","days":7}' 2>/dev/null || echo "000")

HTTP_CODE=$(echo "$CHART_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "200" ]; then
  RESPONSE_BODY=$(echo "$CHART_RESPONSE" | head -n -1)
  HISTORICAL_COUNT=$(echo "$RESPONSE_BODY" | jq -r '.historical | length' 2>/dev/null || echo "0")
  echo -e "${GREEN}✅ Working ($HISTORICAL_COUNT bars returned)${NC}"

  if [ "$HISTORICAL_COUNT" -gt "0" ]; then
    echo -e "      ${GREEN}✅ Historical data is available!${NC}"
  else
    echo -e "      ${YELLOW}⚠️  No historical data yet (backfill in progress)${NC}"
  fi
else
  echo -e "${RED}❌ Failed (HTTP $HTTP_CODE)${NC}"
fi

echo ""
echo "3️⃣  Quick Status Summary..."
echo "   ------------------------"

# Trigger a test run and show results
echo "   Triggering test backfill run..."
TEST_RUN=$(curl -s -X POST \
  "$SUPABASE_URL/functions/v1/trigger-backfill" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' 2>/dev/null || echo '{"success":false}')

SUCCESS=$(echo "$TEST_RUN" | jq -r '.success // false' 2>/dev/null)
WORKER_RESP=$(echo "$TEST_RUN" | jq -r '.worker_response // {}' 2>/dev/null)

if [ "$SUCCESS" = "true" ]; then
  PROCESSED=$(echo "$WORKER_RESP" | jq -r '.processed // 0')
  SUCCEEDED=$(echo "$WORKER_RESP" | jq -r '.succeeded // 0')
  FAILED=$(echo "$WORKER_RESP" | jq -r '.failed // 0')

  echo ""
  echo -e "   ${GREEN}✅ Backfill system is working!${NC}"
  echo "   Processed: $PROCESSED chunks"
  echo "   Succeeded: $SUCCEEDED"
  echo "   Failed: $FAILED"

  if [ "$PROCESSED" = "0" ]; then
    echo ""
    echo -e "   ${YELLOW}ℹ️  No chunks to process right now${NC}"
    echo "   This is normal if:"
    echo "   - All chunks are already completed"
    echo "   - Workers are currently processing chunks"
    echo "   - Chunks are waiting for their turn"
  fi
else
  echo -e "   ${YELLOW}⚠️  Could not complete test run${NC}"
  echo "   Response: $TEST_RUN"
fi

echo ""
echo "4️⃣  Next Steps..."
echo "   --------------"
echo "   📊 Check detailed status in SQL:"
echo "      https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql"
echo ""
echo "   📝 Run the comprehensive health check:"
echo "      Open: check-data-health.sql in SQL Editor"
echo ""
echo "   🔄 View edge function logs:"
echo "      https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions"
echo ""
echo "   📈 Check GitHub Actions:"
echo "      https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions"
echo ""
echo "================================"
echo "Health check complete! ✅"
