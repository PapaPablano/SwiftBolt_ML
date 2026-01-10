#!/bin/bash
# Purge and re-fetch US stocks only (Polygon supports US markets only)
# Filters out international symbols that Polygon doesn't support

set -e

echo "=================================================="
echo "🔄 PURGE & RE-FETCH US STOCK DATA"
echo "=================================================="
echo ""
echo "This script will:"
echo "  1. Fetch only US stock symbols (no international)"
echo "  2. Re-fetch data from Polygon with unadjusted prices"
echo "  3. Skip symbols Polygon doesn't support"
echo ""
read -p "⚠️  Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Support both SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_ROLE_KEY
if [ -n "$SUPABASE_SERVICE_KEY" ]; then
    export SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_KEY"
fi

# Check for required env vars
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
    exit 1
fi

# Get list of US symbols only (filter out international)
echo ""
echo "Step 1: Fetching US stock symbols..."
echo "=================================================="

# Fetch all symbols
SYMBOLS_JSON=$(curl -s "$SUPABASE_URL/rest/v1/symbols?asset_type=eq.stock&select=ticker&order=ticker" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")

ALL_SYMBOLS=$(echo "$SYMBOLS_JSON" | grep -o '"ticker":"[^"]*"' | cut -d'"' -f4)

# Filter to US symbols only (exclude international suffixes)
US_SYMBOLS=$(echo "$ALL_SYMBOLS" | grep -v '\.' | grep -v '^[0-9]')

if [ -z "$US_SYMBOLS" ]; then
    echo "❌ No US symbols found"
    exit 1
fi

TOTAL_COUNT=$(echo "$ALL_SYMBOLS" | wc -l | tr -d ' ')
US_COUNT=$(echo "$US_SYMBOLS" | wc -l | tr -d ' ')
INTL_COUNT=$((TOTAL_COUNT - US_COUNT))

echo "Found $TOTAL_COUNT total symbols:"
echo "  ✅ $US_COUNT US stocks (will re-fetch)"
echo "  ⏭️  $INTL_COUNT international stocks (skipping - Polygon doesn't support)"
echo ""

# Show sample of what will be fetched
echo "Sample US symbols to re-fetch:"
echo "$US_SYMBOLS" | head -10
echo "..."
echo ""

read -p "Continue with re-fetch? (yes/no): " confirm2
if [ "$confirm2" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Re-fetch data for each US symbol
echo ""
echo "Step 2: Re-fetching US stock data..."
echo "=================================================="

CURRENT=0
SUCCESS=0
FAILED=0

for SYMBOL in $US_SYMBOLS; do
    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$US_COUNT] Re-fetching $SYMBOL..."
    
    # Call symbol-backfill function
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$SUPABASE_URL/functions/v1/symbol-backfill" \
        -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"symbol\": \"$SYMBOL\", \"timeframes\": [\"d1\", \"h1\", \"m15\"], \"force\": true}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        TOTAL_BARS=$(echo "$BODY" | grep -o '"totalBars":[0-9]*' | cut -d':' -f2)
        if [ -n "$TOTAL_BARS" ] && [ "$TOTAL_BARS" -gt 0 ]; then
            echo "   ✅ Success: $TOTAL_BARS bars inserted"
            SUCCESS=$((SUCCESS + 1))
        else
            echo "   ⚠️  No data returned"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "   ❌ Failed (HTTP $HTTP_CODE)"
        FAILED=$((FAILED + 1))
    fi
    
    # Rate limiting: Polygon free tier = 5 req/min
    # Wait 15 seconds between symbols (4 req/min to be safe)
    if [ $CURRENT -lt $US_COUNT ]; then
        sleep 15
    fi
done

echo ""
echo "=================================================="
echo "✅ RE-FETCH COMPLETE"
echo "=================================================="
echo ""
echo "Results:"
echo "  ✅ Success: $SUCCESS symbols"
echo "  ❌ Failed:  $FAILED symbols"
echo ""
echo "Next steps:"
echo "  1. Run: python3 verify_price_accuracy.py"
echo "  2. Check specific symbols if needed"
echo ""
