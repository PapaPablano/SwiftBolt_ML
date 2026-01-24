#!/bin/bash
set -e

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "Checking chunk date range for AAPL h1..."
curl -s -X GET \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  "$SUPABASE_URL/rest/v1/backfill_chunks?symbol=eq.AAPL&timeframe=eq.h1&select=day,status&order=day.asc&limit=10" | jq '.'

echo ""
echo "Checking oldest and newest chunks..."
curl -s -X GET \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  "$SUPABASE_URL/rest/v1/backfill_chunks?symbol=eq.AAPL&timeframe=eq.h1&select=day&order=day.asc&limit=1" | jq -r '.[0].day' | xargs -I {} echo "Oldest chunk: {}"

curl -s -X GET \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  "$SUPABASE_URL/rest/v1/backfill_chunks?symbol=eq.AAPL&timeframe=eq.h1&select=day&order=day.desc&limit=1" | jq -r '.[0].day' | xargs -I {} echo "Newest chunk: {}"

echo ""
echo "Count of pending vs done chunks..."
curl -s -X GET \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  "$SUPABASE_URL/rest/v1/rpc/count_chunks_by_status" | jq '.' 2>/dev/null || {
  # Fallback if RPC doesn't exist
  echo "Pending:"
  curl -s -X GET \
    -H "Authorization: Bearer $ANON_KEY" \
    -H "apikey: $ANON_KEY" \
    -H "Prefer: count=exact" \
    "$SUPABASE_URL/rest/v1/backfill_chunks?symbol=eq.AAPL&timeframe=eq.h1&status=eq.pending&select=*" | grep -i "content-range" || echo "Cannot get count"
  
  echo "Done:"
  curl -s -X GET \
    -H "Authorization: Bearer $ANON_KEY" \
    -H "apikey: $ANON_KEY" \
    -H "Prefer: count=exact" \
    "$SUPABASE_URL/rest/v1/backfill_chunks?symbol=eq.AAPL&timeframe=eq.h1&status=eq.done&select=*" | grep -i "content-range" || echo "Cannot get count"
}
