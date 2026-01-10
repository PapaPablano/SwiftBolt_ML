#!/bin/bash
# Test script to verify symbol sync is creating jobs

PROJECT_REF="cygflaemtmwiwaviclks"
SUPABASE_URL="https://${PROJECT_REF}.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "=========================================="
echo "Testing Symbol Sync Edge Function"
echo "=========================================="
echo ""

# Test 1: Sync AAPL with watchlist source
echo "Test 1: Syncing AAPL (watchlist)..."
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
echo ""

# Check if jobs were created
JOBS_CREATED=$(echo "$RESPONSE" | grep -o '"jobs_updated":[0-9]*' | grep -o '[0-9]*')
echo "Jobs created: ${JOBS_CREATED:-0}"
echo ""

if [ "${JOBS_CREATED:-0}" -gt 0 ]; then
    echo "✅ SUCCESS: Jobs were created!"
else
    echo "❌ FAILED: No jobs created"
fi

echo ""
echo "=========================================="
echo "Check Supabase Dashboard:"
echo "  Tables → job_definitions"
echo "  Filter: symbol = 'AAPL'"
echo "  Expected: 3 rows (m15, h1, h4)"
echo "=========================================="
