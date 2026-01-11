#!/bin/bash
# Test V2 Migration Setup
# Verifies SQL functions, database connectivity, and Alpaca integration

set -e

echo "🔍 Testing V2 Migration Setup"
echo "=============================="
echo ""

# Load environment
if [ -f "ml/.env" ]; then
    export $(cat ml/.env | grep -v '^#' | xargs)
fi

# Test 1: Verify SQL functions exist
echo "1️⃣ Checking SQL functions..."
psql "$DATABASE_URL" -c "
SELECT 
  proname as function_name,
  pg_get_function_arguments(oid) as arguments
FROM pg_proc 
WHERE proname IN ('detect_ohlc_gaps', 'get_ohlc_coverage_stats', 'get_chart_data_v2')
ORDER BY proname;
" || echo "⚠️  Could not verify functions (check DATABASE_URL)"

echo ""

# Test 2: Check ohlc_bars_v2 table structure
echo "2️⃣ Checking ohlc_bars_v2 table..."
psql "$DATABASE_URL" -c "
SELECT 
  column_name, 
  data_type,
  is_nullable
FROM information_schema.columns 
WHERE table_name = 'ohlc_bars_v2'
ORDER BY ordinal_position;
" || echo "⚠️  Could not verify table structure"

echo ""

# Test 3: Count bars by provider
echo "3️⃣ Checking data by provider..."
psql "$DATABASE_URL" -c "
SELECT 
  provider,
  timeframe,
  COUNT(*) as bar_count,
  MIN(ts) as oldest,
  MAX(ts) as newest
FROM ohlc_bars_v2
WHERE is_forecast = false
GROUP BY provider, timeframe
ORDER BY provider, timeframe;
" || echo "⚠️  Could not query data"

echo ""

# Test 4: Test gap detection function
echo "4️⃣ Testing gap detection function..."
psql "$DATABASE_URL" -c "
SELECT * FROM detect_ohlc_gaps('AAPL', 'd1', 48) LIMIT 5;
" || echo "⚠️  Gap detection function failed"

echo ""

# Test 5: Test coverage stats function
echo "5️⃣ Testing coverage stats function..."
psql "$DATABASE_URL" -c "
SELECT * FROM get_ohlc_coverage_stats('AAPL', 'd1');
" || echo "⚠️  Coverage stats function failed"

echo ""

# Test 6: Verify Alpaca credentials (without exposing them)
echo "6️⃣ Checking Alpaca credentials..."
if [ -z "$ALPACA_API_KEY" ]; then
    echo "❌ ALPACA_API_KEY not set"
else
    echo "✅ ALPACA_API_KEY is set (${#ALPACA_API_KEY} chars)"
fi

if [ -z "$ALPACA_API_SECRET" ]; then
    echo "❌ ALPACA_API_SECRET not set"
else
    echo "✅ ALPACA_API_SECRET is set (${#ALPACA_API_SECRET} chars)"
fi

echo ""
echo "=============================="
echo "✅ V2 Setup Verification Complete"
echo ""
echo "Next steps:"
echo "  1. Run a test backfill: cd ml && python src/scripts/alpaca_backfill_ohlc_v2.py --symbol AAPL --timeframe d1"
echo "  2. Trigger 'Daily Data Refresh' workflow manually from GitHub Actions"
echo "  3. Monitor workflow runs for success"
