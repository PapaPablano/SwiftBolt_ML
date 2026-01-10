#!/bin/bash
# Direct test of symbol creation via REST API

PROJECT_REF="cygflaemtmwiwaviclks"
SUPABASE_URL="https://${PROJECT_REF}.supabase.co"
SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"

if [ -z "$SERVICE_ROLE_KEY" ]; then
    echo "❌ SUPABASE_SERVICE_ROLE_KEY environment variable not set"
    echo "Set it with: export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key'"
    exit 1
fi

echo "=========================================="
echo "Testing Direct Symbol Creation"
echo "=========================================="
echo ""

# Test 1: Create AAPL symbol
echo "Test 1: Creating AAPL symbol..."
RESPONSE=$(curl -s -X POST \
    "${SUPABASE_URL}/rest/v1/symbols" \
    -H "apikey: ${SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d '{
        "ticker": "AAPL",
        "asset_type": "stock",
        "description": "Apple Inc."
    }')

echo "Response: $RESPONSE"
echo ""

# Test 2: Query symbols table
echo "Test 2: Querying symbols table..."
SYMBOLS=$(curl -s -X GET \
    "${SUPABASE_URL}/rest/v1/symbols?select=ticker,id&ticker=eq.AAPL" \
    -H "apikey: ${SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SERVICE_ROLE_KEY}")

echo "Symbols: $SYMBOLS"
echo ""

if echo "$SYMBOLS" | grep -q "AAPL"; then
    echo "✅ SUCCESS: AAPL symbol exists"
else
    echo "❌ FAILED: AAPL symbol not found"
fi

echo ""
echo "=========================================="
