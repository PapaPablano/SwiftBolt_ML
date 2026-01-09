#!/bin/bash

# Step 3: Trigger Immediate Backfill
# Run this after Steps 1 and 2 are complete

set -e

# Configuration
SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"

# Check if service role key is set
if [ -z "$SERVICE_ROLE_KEY" ]; then
  echo "❌ ERROR: SUPABASE_SERVICE_ROLE_KEY environment variable not set"
  echo ""
  echo "Please set it first:"
  echo "  export SUPABASE_SERVICE_ROLE_KEY='your-key-here'"
  echo ""
  echo "Get your key from: Supabase Dashboard → Project Settings → API → service_role secret"
  exit 1
fi

echo "🚀 Triggering orchestrator backfill..."
echo ""

# Trigger orchestrator
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "${SUPABASE_URL}/functions/v1/orchestrator?action=tick" \
  -H "Authorization: Bearer ${SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo "Response:"
echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Orchestrator triggered successfully!"
  echo ""
  echo "📊 To monitor progress, run these SQL queries in Supabase:"
  echo ""
  echo "-- Check recent job runs:"
  echo "select symbol, timeframe, status, rows_written, provider, created_at"
  echo "from job_runs"
  echo "order by created_at desc"
  echo "limit 10;"
  echo ""
  echo "-- Check Alpaca data appearing:"
  echo "select count(*) from ohlc_bars_v2 where provider = 'alpaca';"
  echo ""
else
  echo "❌ ERROR: Orchestrator trigger failed!"
  echo ""
  echo "Troubleshooting:"
  echo "1. Verify service role key is correct"
  echo "2. Check that Step 2 (configure_cron.sql) was executed"
  echo "3. Check Edge Function logs in Supabase Dashboard"
fi
