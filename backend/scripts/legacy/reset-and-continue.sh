#!/bin/bash
set -e

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "Resetting job status to pending..."
curl -s -X PATCH \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  -d '{"status":"pending","error":null}' \
  "$SUPABASE_URL/rest/v1/backfill_jobs?symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5&timeframe=eq.h1"

echo "✅ Job reset to pending"
echo ""
echo "Triggering worker 10 times to process more chunks..."

for i in {1..10}; do
  echo "Worker run #$i..."
  RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $ANON_KEY" \
    -H "apikey: $ANON_KEY" \
    "$SUPABASE_URL/functions/v1/run-backfill-worker")
  
  echo "$RESPONSE" | jq -c '{processed, succeeded, failed, elapsed}'
  
  if [ $i -lt 10 ]; then
    sleep 2
  fi
done

echo ""
echo "✅ Done! Checking current bar count..."
curl -s -X GET \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  "$SUPABASE_URL/rest/v1/ohlc_bars_v2?symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5&timeframe=eq.h1&provider=eq.alpaca&select=count" \
  -H "Prefer: count=exact" | head -1
