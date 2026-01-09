#!/bin/bash
# Check what's actually in the database

set -e

echo "============================================"
echo "Database Direct Query"
echo "============================================"
echo ""

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "1. Checking ohlc_bars_v2 for AAPL h1 (last 20 rows)..."
echo "-------------------------------------------"

curl -s -G \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  --data-urlencode "select=ts,open,close,provider,is_intraday,fetched_at" \
  --data-urlencode "symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5" \
  --data-urlencode "timeframe=eq.h1" \
  --data-urlencode "is_forecast=eq.false" \
  --data-urlencode "order=ts.desc" \
  --data-urlencode "limit=20" \
  "$SUPABASE_URL/rest/v1/ohlc_bars_v2" | jq '.'

echo ""
echo ""

echo "2. Count by provider for AAPL h1..."
echo "-------------------------------------------"

curl -s -G \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  --data-urlencode "select=provider" \
  --data-urlencode "symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5" \
  --data-urlencode "timeframe=eq.h1" \
  --data-urlencode "is_forecast=eq.false" \
  "$SUPABASE_URL/rest/v1/ohlc_bars_v2" | jq 'group_by(.provider) | map({provider: .[0].provider, count: length})'

echo ""
echo ""

echo "3. Checking backfill_jobs status..."
echo "-------------------------------------------"

curl -s -G \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  --data-urlencode "select=*" \
  --data-urlencode "symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5" \
  --data-urlencode "timeframe=eq.h1" \
  --data-urlencode "order=created_at.desc" \
  --data-urlencode "limit=3" \
  "$SUPABASE_URL/rest/v1/backfill_jobs" | jq '.'

echo ""
echo ""

echo "4. Checking recent backfill_chunks (last 10)..."
echo "-------------------------------------------"

curl -s -G \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  --data-urlencode "select=symbol,timeframe,day,status,try_count,last_error" \
  --data-urlencode "symbol=in.(AAPL,NVDA)" \
  --data-urlencode "timeframe=eq.h1" \
  --data-urlencode "order=day.desc" \
  --data-urlencode "limit=10" \
  "$SUPABASE_URL/rest/v1/backfill_chunks" | jq '.'

echo ""
