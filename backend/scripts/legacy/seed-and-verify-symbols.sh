#!/bin/bash
# Seed symbols and verify they were created
# Usage: ./seed-and-verify-symbols.sh

set -e

PROJECT_REF="cygflaemtmwiwaviclks"
SUPABASE_URL="https://${PROJECT_REF}.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "=========================================="
echo "SwiftBolt ML - Symbol Seeding & Verification"
echo "=========================================="
echo ""

# Step 1: Call seed-symbols edge function
echo "Step 1: Seeding symbols via edge function..."
SEED_RESPONSE=$(curl -s -X POST \
    "${SUPABASE_URL}/functions/v1/seed-symbols" \
    -H "Authorization: Bearer ${ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d '{}' 2>&1)

echo "Seed response: $SEED_RESPONSE"
echo ""

# Check for success
if echo "$SEED_RESPONSE" | grep -q '"success":true'; then
    echo "✅ Seed function executed successfully"
else
    echo "⚠️  Seed function may have failed - check response above"
    echo "   If function not deployed, run: supabase functions deploy seed-symbols"
fi
echo ""

# Step 2: Verify symbols exist by searching for AAPL
echo "Step 2: Verifying symbols exist..."
SEARCH_RESPONSE=$(curl -s -X GET \
    "${SUPABASE_URL}/functions/v1/symbols-search?q=AAPL" \
    -H "Authorization: Bearer ${ANON_KEY}" 2>&1)

echo "Search response: $SEARCH_RESPONSE"
echo ""

if echo "$SEARCH_RESPONSE" | grep -q '"ticker":"AAPL"'; then
    echo "✅ AAPL symbol found in database"
else
    echo "❌ AAPL symbol NOT found"
fi
echo ""

# Step 3: Test symbol sync creates jobs
echo "Step 3: Testing symbol sync creates jobs..."
SYNC_RESPONSE=$(curl -s -X POST \
    "${SUPABASE_URL}/functions/v1/sync-user-symbols" \
    -H "Authorization: Bearer ${ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "symbols": ["AAPL"],
        "source": "watchlist",
        "timeframes": ["m15", "h1", "h4"]
    }' 2>&1)

echo "Sync response: $SYNC_RESPONSE"
echo ""

# Extract jobs count
JOBS_UPDATED=$(echo "$SYNC_RESPONSE" | grep -o '"jobs_updated":[0-9]*' | grep -o '[0-9]*' || echo "0")
SYMBOLS_SYNCED=$(echo "$SYNC_RESPONSE" | grep -o '"symbols_synced":[0-9]*' | grep -o '[0-9]*' || echo "0")

echo "=========================================="
echo "RESULTS:"
echo "=========================================="
echo "Symbols synced: ${SYMBOLS_SYNCED:-0}"
echo "Jobs updated:   ${JOBS_UPDATED:-0}"
echo ""

if [ "${JOBS_UPDATED:-0}" -gt 0 ]; then
    echo "✅ SUCCESS: Symbol tracking is working!"
    echo "   Jobs were created for AAPL across m15, h1, h4 timeframes"
else
    echo "❌ ISSUE: No jobs were created"
    echo ""
    echo "Possible causes:"
    echo "  1. seed-symbols function not deployed"
    echo "  2. symbols table still empty"
    echo "  3. RLS policies blocking access"
    echo ""
    echo "Try running the SQL seed script directly:"
    echo "  1. Go to Supabase Dashboard > SQL Editor"
    echo "  2. Paste contents of: backend/scripts/seed-symbols.sql"
    echo "  3. Click 'Run'"
fi
echo ""
echo "=========================================="
