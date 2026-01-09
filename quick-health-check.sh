#!/bin/bash

# Quick health check for SwiftBolt backfill system
# Run this to verify edge functions are working

set -e

echo "🔍 SwiftBolt Backfill Health Check"
echo "=================================="
echo ""

# Check if SUPABASE_ANON_KEY is set
if [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "❌ SUPABASE_ANON_KEY environment variable is not set"
    echo ""
    echo "To fix:"
    echo "  export SUPABASE_ANON_KEY=\"your-anon-key-here\""
    echo ""
    echo "Get your anon key from:"
    echo "  https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api"
    exit 1
fi

echo "✅ SUPABASE_ANON_KEY is set"
echo ""

# Test trigger-backfill endpoint
echo "📡 Testing trigger-backfill endpoint..."
TRIGGER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{}')

HTTP_CODE=$(echo "$TRIGGER_RESPONSE" | tail -n1)
BODY=$(echo "$TRIGGER_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ trigger-backfill endpoint responding"
    echo "   Response: $BODY"

    # Check if worker processed chunks
    PROCESSED=$(echo "$BODY" | grep -o '"processed":[0-9]*' | cut -d':' -f2)
    if [ -n "$PROCESSED" ] && [ "$PROCESSED" -gt 0 ]; then
        echo "   ✅ Processed $PROCESSED chunks!"
    elif [ "$PROCESSED" = "0" ]; then
        echo "   ⚠️  Processed 0 chunks (all done or none pending)"
    fi
else
    echo "❌ trigger-backfill endpoint failed (HTTP $HTTP_CODE)"
    echo "   Response: $BODY"
fi

echo ""
echo "📊 Next steps:"
echo "1. Run SQL health check in Supabase dashboard (check-aapl-data.sql)"
echo "2. Check backfill progress with: SELECT * FROM backfill_jobs;"
echo "3. Monitor GitHub Actions: https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions"
echo ""
