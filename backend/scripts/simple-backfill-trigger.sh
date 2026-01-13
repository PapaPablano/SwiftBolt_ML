#!/bin/bash
# Simple backfill trigger using anon key from client config

set -e

echo "============================================"
echo "Simple Backfill Trigger"
echo "============================================"
echo ""

# Hardcoded from client config (publicly visible anyway)
SUPABASE_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs"

echo "Using:"
echo "  URL: $SUPABASE_URL"
echo "  Auth: anon key"
echo ""

# Step 1: Check current status
echo "Step 1: Checking AAPL h1 status..."
echo "-------------------------------------------"

CHART_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "apikey: $ANON_KEY" \
  -d '{"symbol":"AAPL","timeframe":"h1","days":60}' \
  "$SUPABASE_URL/functions/v1/chart-data-v2")

echo "Current bar count:"
echo "$CHART_RESPONSE" | jq '.metadata.total_bars, .layers' 2>/dev/null || echo "$CHART_RESPONSE"

echo ""
echo ""

# Step 2: Trigger coverage check for AAPL (creates backfill jobs)
echo "Step 2: Triggering coverage check for AAPL h1 (2 years)..."
echo "-------------------------------------------"

COVERAGE_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "apikey: $ANON_KEY" \
  -d '{"symbol":"AAPL","timeframe":"h1","windowDays":730}' \
  "$SUPABASE_URL/functions/v1/ensure-coverage")

echo "$COVERAGE_RESPONSE" | jq '.' 2>/dev/null || echo "$COVERAGE_RESPONSE"

echo ""
echo ""

# Step 3: Same for NVDA
echo "Step 3: Triggering coverage check for NVDA h1 (2 years)..."
echo "-------------------------------------------"

COVERAGE_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "apikey: $ANON_KEY" \
  -d '{"symbol":"NVDA","timeframe":"h1","windowDays":730}' \
  "$SUPABASE_URL/functions/v1/ensure-coverage")

echo "$COVERAGE_RESPONSE" | jq '.' 2>/dev/null || echo "$COVERAGE_RESPONSE"

echo ""
echo ""

# Step 4: Trigger backfill worker multiple times
echo "Step 4: Triggering backfill worker (3 runs)..."
echo "-------------------------------------------"

for i in {1..3}; do
  echo ""
  echo "Worker run #$i..."

  WORKER_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $ANON_KEY" \
    -H "apikey: $ANON_KEY" \
    "$SUPABASE_URL/functions/v1/run-backfill-worker")

  echo "$WORKER_RESPONSE" | jq '.' 2>/dev/null || echo "$WORKER_RESPONSE"

  # Small delay between runs
  if [ "$i" -lt 3 ]; then
    sleep 3
  fi
done

echo ""
echo ""
echo "============================================"
echo "✅ Backfill Triggered!"
echo "============================================"
echo ""
echo "What happens next:"
echo "  1. Backfill jobs created for AAPL & NVDA (h1 timeframe)"
echo "  2. Worker processes chunks in the background"
echo "  3. Data fetched from Alpaca API"
echo "  4. Written to ohlc_bars_v2 table"
echo ""
echo "Timeline:"
echo "  • 5-10 minutes: First 50-100 bars appear"
echo "  • 30-60 minutes: Full 2-year history (730 days × 7-8 hours/day)"
echo ""
echo "To check progress:"
echo "  • Re-run this script to see updated bar counts"
echo "  • Or refresh your macOS app and switch to h1 timeframe"
echo ""
echo "The cron job will also continue processing automatically."
echo ""
