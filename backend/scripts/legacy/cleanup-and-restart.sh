#!/bin/bash
# Clean up bad data and restart backfill

set -e

SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "============================================"
echo "Cleanup and Restart Backfill"
echo "============================================"
echo ""

echo "Step 1: Deleting bad Alpaca bars (1970 timestamps)..."
echo "-------------------------------------------"

# Delete bars with timestamps before 2020 (these are the bad 1970 ones)
curl -s -X DELETE \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  -H "Prefer: return=minimal" \
  "$SUPABASE_URL/rest/v1/ohlc_bars_v2?symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5&timeframe=eq.h1&provider=eq.alpaca&ts=lt.2020-01-01T00:00:00"

echo "✅ Bad Alpaca bars deleted"
echo ""

echo "Step 2: Resetting backfill job status..."
echo "-------------------------------------------"

# Reset the job to pending status
curl -s -X PATCH \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  -d '{"status":"pending","progress":0,"error":null}' \
  "$SUPABASE_URL/rest/v1/backfill_jobs?symbol_id=eq.77e74624-6b80-430a-9543-328d41e52ce5&timeframe=eq.h1"

echo "✅ Backfill job reset to pending"
echo ""

echo "Step 3: Resetting chunks to pending..."
echo "-------------------------------------------"

# Reset all AAPL h1 chunks to pending
curl -s -X PATCH \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  -d '{"status":"pending","try_count":0,"last_error":null}' \
  "$SUPABASE_URL/rest/v1/backfill_chunks?symbol=eq.AAPL&timeframe=eq.h1&status=in.(done,error)"

echo "✅ Chunks reset to pending"
echo ""

echo "Step 4: Triggering worker (5 runs to process more chunks)..."
echo "-------------------------------------------"

for i in {1..5}; do
  echo "Worker run #$i..."

  RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $ANON_KEY" \
    -H "apikey: $ANON_KEY" \
    "$SUPABASE_URL/functions/v1/run-backfill-worker")

  echo "$RESPONSE" | jq '.'
  echo ""

  if [ $i -lt 5 ]; then
    sleep 2
  fi
done

echo ""
echo "============================================"
echo "✅ Cleanup Complete!"
echo "============================================"
echo ""
echo "Now check the results:"
echo "  ./scripts/simple-backfill-trigger.sh"
echo ""
echo "You should see:"
echo "  • Bar count increasing"
echo "  • Provider changing to 'alpaca'"
echo "  • Correct dates (2024-2026, not 1970!)"
echo ""
