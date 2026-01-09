#!/bin/bash
# Test if Alpaca credentials are working
# This calls the fetch-bars worker directly to test authentication

set -e

# Check for service role key
if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "❌ ERROR: SUPABASE_SERVICE_ROLE_KEY environment variable not set"
    echo ""
    echo "Please set it first:"
    echo "  export SUPABASE_SERVICE_ROLE_KEY='your-key-here'"
    exit 1
fi

echo "🔍 Testing Alpaca credentials and connectivity..."
echo ""

# Test with a simple AAPL 1h request (last 5 days)
curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/fetch-bars" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "job_run_id": "00000000-0000-0000-0000-000000000000",
    "symbol": "AAPL",
    "timeframe": "1h",
    "from": "2026-01-04T00:00:00.000Z",
    "to": "2026-01-09T00:00:00.000Z"
  }' \
  -w "\n\nHTTP Status: %{http_code}\n"

echo ""
echo "✅ Check the response above:"
echo "   - If you see 'ALPACA_API_KEY not set' → Credentials not configured"
echo "   - If you see '401 Unauthorized' → Wrong credentials"
echo "   - If you see 'rows_written: X' → Working!"
