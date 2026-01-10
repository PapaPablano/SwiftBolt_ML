#!/bin/bash
# Test script to verify backfill worker is processing chunks

echo "Testing backfill worker..."
echo ""

# Get your service role key from Supabase dashboard and set it here
# SUPABASE_SERVICE_ROLE_KEY="your-key-here"

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo "⚠️  Please set SUPABASE_SERVICE_ROLE_KEY environment variable"
  echo "   Get it from: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api"
  echo ""
  echo "   Then run:"
  echo "   export SUPABASE_SERVICE_ROLE_KEY='your-key-here'"
  echo "   ./test-backfill.sh"
  exit 1
fi

# Call the backfill worker
echo "Calling run-backfill-worker..."
RESPONSE=$(curl -s "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{}')

echo "$RESPONSE" | jq '.'
echo ""

# Check if it processed any chunks
PROCESSED=$(echo "$RESPONSE" | jq -r '.processed // 0')
SUCCEEDED=$(echo "$RESPONSE" | jq -r '.succeeded // 0')
FAILED=$(echo "$RESPONSE" | jq -r '.failed // 0')

if [ "$PROCESSED" -gt 0 ]; then
  echo "✅ Worker is processing chunks!"
  echo "   Processed: $PROCESSED"
  echo "   Succeeded: $SUCCEEDED"
  echo "   Failed: $FAILED"
else
  echo "ℹ️  No chunks to process (may be waiting for cron to create slices)"
fi
