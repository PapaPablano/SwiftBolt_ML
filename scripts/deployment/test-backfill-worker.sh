#!/bin/bash
# Test script for backfill-intraday-worker edge function

set -e

# Load environment variables
source .env

echo "Testing backfill-intraday-worker edge function..."
echo ""

# Test the edge function
echo "Calling edge function..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/backfill-intraday-worker" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -d '{}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo "Response Body:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_CODE" -eq 200 ]; then
  echo "✅ Edge function executed successfully"
else
  echo "❌ Edge function failed with status $HTTP_CODE"
fi
