#!/bin/bash
# Purge corrupted adjusted price data and re-fetch with unadjusted prices
# Run this script after deploying the adjusted=false fix

set -e

echo "=================================================="
echo "🔄 PURGE & RE-FETCH STOCK DATA"
echo "=================================================="
echo ""
echo "This script will:"
echo "  1. Delete all existing OHLC data (corrupted adjusted prices)"
echo "  2. Re-fetch data from Polygon with unadjusted prices"
echo "  3. Verify data accuracy against Yahoo Finance"
echo ""
read -p "⚠️  This will delete ALL existing price data. Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check for required env vars
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
    exit 1
fi

echo ""
echo "Step 1: Deleting corrupted data from database..."
echo "=================================================="

# Delete all ohlc_bars data
psql "$DATABASE_URL" <<EOF
-- Backup count before deletion
SELECT 
    COUNT(*) as total_bars,
    COUNT(DISTINCT symbol_id) as total_symbols,
    COUNT(DISTINCT timeframe) as total_timeframes
FROM ohlc_bars;

-- Delete all bars (will be re-fetched)
DELETE FROM ohlc_bars WHERE is_adjusted = true OR is_adjusted IS NULL;

-- Show remaining count (should be 0 or only unadjusted data)
SELECT COUNT(*) as remaining_bars FROM ohlc_bars;
EOF

echo "✅ Database purged"
echo ""

# Get list of symbols to re-fetch
echo "Step 2: Fetching list of symbols..."
echo "=================================================="

SYMBOLS=$(psql "$DATABASE_URL" -t -c "SELECT ticker FROM symbols WHERE asset_type = 'stock' ORDER BY ticker;")

if [ -z "$SYMBOLS" ]; then
    echo "❌ No symbols found in database"
    exit 1
fi

SYMBOL_COUNT=$(echo "$SYMBOLS" | wc -l | tr -d ' ')
echo "Found $SYMBOL_COUNT symbols to re-fetch"
echo ""

# Re-fetch data for each symbol
echo "Step 3: Re-fetching data with unadjusted prices..."
echo "=================================================="

CURRENT=0
for SYMBOL in $SYMBOLS; do
    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$SYMBOL_COUNT] Re-fetching $SYMBOL..."
    
    # Call symbol-backfill function
    curl -X POST "$SUPABASE_URL/functions/v1/symbol-backfill" \
        -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"symbol\": \"$SYMBOL\", \"timeframes\": [\"d1\", \"h1\", \"m15\"], \"force\": true}" \
        --silent --show-error || echo "⚠️  Failed to fetch $SYMBOL"
    
    # Rate limiting: Polygon free tier = 5 req/min
    # Wait 15 seconds between symbols (4 req/min to be safe)
    if [ $CURRENT -lt $SYMBOL_COUNT ]; then
        echo "   Rate limit delay (15s)..."
        sleep 15
    fi
done

echo ""
echo "✅ All symbols re-fetched"
echo ""

# Verify data accuracy
echo "Step 4: Verifying data accuracy..."
echo "=================================================="

cd "$(dirname "$0")"
python3 verify_price_accuracy.py

echo ""
echo "=================================================="
echo "✅ PURGE & RE-FETCH COMPLETE"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Check verify_price_accuracy.py output above"
echo "  2. If discrepancies remain, investigate specific symbols"
echo "  3. Re-export CSV files for any affected symbols"
echo ""
