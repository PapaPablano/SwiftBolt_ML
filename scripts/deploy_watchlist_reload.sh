#!/bin/bash
# Deploy watchlist reload edge function and verify setup

set -e

echo "========================================="
echo "Watchlist Data Reload - Deployment"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -d "backend/supabase/functions/reload-watchlist-data" ]; then
    echo "❌ Error: Must run from project root"
    exit 1
fi

echo "📦 Step 1: Deploy edge function..."
cd backend/supabase/functions
supabase functions deploy reload-watchlist-data
cd ../../..

echo ""
echo "✅ Edge function deployed!"
echo ""

echo "📋 Step 2: Verify deployment..."
echo ""
echo "Run this command to test (replace with your project URL and key):"
echo ""
echo "curl -X POST \\"
echo "  https://YOUR_PROJECT.supabase.co/functions/v1/reload-watchlist-data \\"
echo "  -H \"Authorization: Bearer YOUR_SERVICE_ROLE_KEY\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"forceRefresh\": false,"
echo "    \"timeframes\": [\"m15\", \"h1\", \"h4\", \"d1\", \"w1\"],"
echo "    \"symbols\": [\"AAPL\"]"
echo "  }'"
echo ""

echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Test the function with a single symbol (see command above)"
echo "2. Run from Swift client: await watchlistViewModel.reloadAllData()"
echo "3. Verify data in Supabase SQL Editor:"
echo "   SELECT * FROM ohlc_bars_v2 WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL') LIMIT 10;"
echo ""
