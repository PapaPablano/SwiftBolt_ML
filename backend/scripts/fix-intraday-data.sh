#!/bin/bash
# ============================================================================
# Fix Intraday Data Script
# Purpose: Diagnose and fix intraday data issues with Alpaca
# Date: 2026-01-09
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================"
echo "Intraday Data Diagnostic and Fix Tool"
echo "============================================"
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/backend/supabase/config.toml" ]; then
  echo "❌ Error: Cannot find supabase config.toml"
  echo "   Make sure you're running this from the project root"
  exit 1
fi

cd "$PROJECT_ROOT/backend"

echo "Step 1: Running diagnostics..."
echo "-------------------------------------------"
npx supabase db execute --file "$SCRIPT_DIR/diagnose-intraday-data.sql" --local 2>&1 || {
  echo ""
  echo "⚠️  Local database not running. Trying linked project..."
  npx supabase db execute --file "$SCRIPT_DIR/diagnose-intraday-data.sql" --linked 2>&1
}

echo ""
echo ""
read -p "Do you want to trigger Alpaca backfill for AAPL and NVDA? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo ""
  echo "Step 2: Triggering backfill jobs..."
  echo "-------------------------------------------"

  npx supabase db execute --file "$SCRIPT_DIR/trigger-alpaca-backfill.sql" --local 2>&1 || {
    echo ""
    echo "⚠️  Local database not running. Trying linked project..."
    npx supabase db execute --file "$SCRIPT_DIR/trigger-alpaca-backfill.sql" --linked 2>&1
  }

  echo ""
  echo "✅ Backfill jobs created!"
  echo ""
  echo "Step 3: Triggering backfill worker..."
  echo "-------------------------------------------"

  # Get the Supabase URL and anon key
  if [ -f "$PROJECT_ROOT/backend/.env" ]; then
    source "$PROJECT_ROOT/backend/.env"
  fi

  if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "⚠️  SUPABASE_URL or SUPABASE_ANON_KEY not found in .env"
    echo ""
    echo "To manually trigger the backfill worker, run:"
    echo "  curl -X POST \\\"
    echo "    -H \"Authorization: Bearer YOUR_ANON_KEY\" \\"
    echo "    https://YOUR_PROJECT.supabase.co/functions/v1/run-backfill-worker"
  else
    echo "Calling run-backfill-worker edge function..."

    RESPONSE=$(curl -s -X POST \
      -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
      "$SUPABASE_URL/functions/v1/run-backfill-worker")

    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"

    echo ""
    echo "✅ Worker triggered! Processing chunks..."
    echo ""
    echo "The worker will:"
    echo "  1. Claim pending chunks from backfill_chunks table"
    echo "  2. Fetch data from Alpaca API"
    echo "  3. Write to ohlc_bars_v2 table"
    echo ""
    echo "Monitor progress by running this script again (it will show updated diagnostics)"
  fi
else
  echo ""
  echo "Skipping backfill trigger."
  echo ""
  echo "To trigger manually later, run:"
  echo "  psql -f $SCRIPT_DIR/trigger-alpaca-backfill.sql"
fi

echo ""
echo "============================================"
echo "Done!"
echo "============================================"
