#!/bin/bash
# Complete data flow test script
# Run this AFTER applying the migration

PROJECT_REF="cygflaemtmwiwaviclks"
SUPABASE_URL="https://${PROJECT_REF}.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "=============================================="
echo "  Complete Data Flow Test"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Sync symbol (creates symbol + jobs)
echo -e "${YELLOW}Test 1: Syncing AAPL (should create symbol + 3 jobs)${NC}"
RESPONSE=$(curl -s -X POST \
    "${SUPABASE_URL}/functions/v1/sync-user-symbols" \
    -H "Authorization: Bearer ${ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "symbols": ["AAPL"],
        "source": "watchlist",
        "timeframes": ["m15", "h1", "h4"]
    }')

echo "Response: $RESPONSE"
JOBS_CREATED=$(echo "$RESPONSE" | grep -o '"jobs_updated":[0-9]*' | grep -o '[0-9]*')
SYMBOLS_TRACKED=$(echo "$RESPONSE" | grep -o '"symbols_tracked":[0-9]*' | grep -o '[0-9]*')

if [ "${JOBS_CREATED:-0}" -gt 0 ]; then
    echo -e "${GREEN}✅ SUCCESS: ${JOBS_CREATED} jobs created, ${SYMBOLS_TRACKED} symbols tracked${NC}"
else
    echo -e "${RED}❌ FAILED: No jobs created. Did you apply the migration?${NC}"
    echo ""
    echo "Run the migration SQL in Supabase SQL Editor:"
    echo "https://supabase.com/dashboard/project/${PROJECT_REF}/sql"
    exit 1
fi

echo ""

# Test 2: Check orchestrator status
echo -e "${YELLOW}Test 2: Checking orchestrator status${NC}"
ORCH_STATUS=$(curl -s -X POST \
    "${SUPABASE_URL}/functions/v1/orchestrator?action=status" \
    -H "Authorization: Bearer ${ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d '{}')

QUEUED=$(echo "$ORCH_STATUS" | grep -o '"queued":[0-9]*' | grep -o '[0-9]*')
RUNNING=$(echo "$ORCH_STATUS" | grep -o '"running":[0-9]*' | grep -o '[0-9]*')

echo "Queued jobs: ${QUEUED:-0}, Running jobs: ${RUNNING:-0}"

if [ "${QUEUED:-0}" -gt 0 ] || [ "${RUNNING:-0}" -gt 0 ]; then
    echo -e "${GREEN}✅ Jobs are in the queue/running${NC}"
else
    echo -e "${YELLOW}⚠️  No jobs queued yet. Triggering orchestrator tick...${NC}"

    # Trigger a tick
    curl -s -X POST \
        "${SUPABASE_URL}/functions/v1/orchestrator?action=tick" \
        -H "Authorization: Bearer ${ANON_KEY}" \
        -H "Content-Type: application/json" \
        -d '{}' > /dev/null

    sleep 2

    # Check again
    ORCH_STATUS=$(curl -s -X POST \
        "${SUPABASE_URL}/functions/v1/orchestrator?action=status" \
        -H "Authorization: Bearer ${ANON_KEY}" \
        -H "Content-Type: application/json" \
        -d '{}')

    QUEUED=$(echo "$ORCH_STATUS" | grep -o '"queued":[0-9]*' | grep -o '[0-9]*')
    echo "Jobs now queued: ${QUEUED:-0}"
fi

echo ""

# Test 3: Trigger orchestrator tick and wait for data
echo -e "${YELLOW}Test 3: Triggering orchestrator tick to process jobs${NC}"
TICK_RESULT=$(curl -s -X POST \
    "${SUPABASE_URL}/functions/v1/orchestrator?action=tick" \
    -H "Authorization: Bearer ${ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d '{}')

echo "Tick result: $TICK_RESULT"

SLICES_CREATED=$(echo "$TICK_RESULT" | grep -o '"slices_created":[0-9]*' | grep -o '[0-9]*')
JOBS_DISPATCHED=$(echo "$TICK_RESULT" | grep -o '"jobs_dispatched":[0-9]*' | grep -o '[0-9]*')

if [ "${JOBS_DISPATCHED:-0}" -gt 0 ]; then
    echo -e "${GREEN}✅ ${JOBS_DISPATCHED} jobs dispatched${NC}"
else
    echo -e "${YELLOW}⚠️  No jobs dispatched. May need another tick or jobs are already complete.${NC}"
fi

echo ""

# Test 4: Check for recent successful jobs
echo -e "${YELLOW}Test 4: Checking for successful job completions${NC}"
sleep 5 # Wait for jobs to complete

FINAL_STATUS=$(curl -s -X POST \
    "${SUPABASE_URL}/functions/v1/orchestrator?action=status" \
    -H "Authorization: Bearer ${ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d '{}')

echo "Recent jobs:"
echo "$FINAL_STATUS" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    recent = data.get('recent_jobs', [])[:5]
    for job in recent:
        status = job.get('status', 'unknown')
        symbol = job.get('symbol', 'N/A')
        timeframe = job.get('timeframe', 'N/A')
        rows = job.get('rows_written', 0)
        provider = job.get('provider', 'N/A')
        print(f'  {symbol}/{timeframe}: {status} - {rows} rows ({provider})')
except:
    print('  Unable to parse response')
" 2>/dev/null || echo "  (Install python3 for better output)"

echo ""
echo "=============================================="
echo "  Summary"
echo "=============================================="
echo ""
echo "If jobs show 'success' with rows written, the data flow is working!"
echo ""
echo "Next steps:"
echo "1. Open your Swift app and view a chart"
echo "2. The chart should show historical data from Alpaca"
echo "3. Check Supabase Tables: ohlc_bars_v2 should have data"
echo ""
echo "Dashboard links:"
echo "- Functions: https://supabase.com/dashboard/project/${PROJECT_REF}/functions"
echo "- Tables: https://supabase.com/dashboard/project/${PROJECT_REF}/editor"
echo "- SQL Editor: https://supabase.com/dashboard/project/${PROJECT_REF}/sql"
