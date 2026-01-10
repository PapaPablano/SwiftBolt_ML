#!/bin/bash
# Quick verification of database prices

set -e

# Load environment
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -n "$SUPABASE_SERVICE_KEY" ]; then
    export SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_KEY"
fi

echo "=================================================="
echo "🔍 DATABASE PRICE VERIFICATION"
echo "=================================================="
echo ""

# Get NVDA symbol ID
NVDA_ID=$(curl -s "$SUPABASE_URL/rest/v1/symbols?select=id&ticker=eq.NVDA" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq -r '.[0].id')

echo "📊 NVDA Recent Daily Bars (Last 5 days):"
echo "=================================================="

curl -s "$SUPABASE_URL/rest/v1/ohlc_bars?select=time,open,high,low,close,volume,is_adjusted&symbol_id=eq.$NVDA_ID&timeframe=eq.d1&order=time.desc&limit=5" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq -r '.[] | "📅 \(.time[:10])  Close: $\(.close)  Adjusted: \(.is_adjusted // "null")"'

echo ""
echo "=================================================="
echo "✅ Database Query Complete"
echo "=================================================="
echo ""
echo "Expected for NVDA (Jan 2-3, 2026):"
echo "  Jan 3: ~$140-145 (unadjusted)"
echo "  Jan 2: ~$138-142 (unadjusted)"
echo ""
echo "If prices show ~$186-202, data is still adjusted (BAD)"
echo "If prices show ~$138-145, data is unadjusted (GOOD)"
echo ""
