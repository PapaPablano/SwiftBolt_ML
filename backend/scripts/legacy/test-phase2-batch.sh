#!/bin/bash
# Test Phase 2 Batch Processing with Real Symbols
# This creates batch jobs for NVDA, TSLA, AMD, META, NFLX

set -e

SUPABASE_URL="${SUPABASE_URL:-https://cygflaemtmwiwaviclks.supabase.co}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo "❌ Error: SUPABASE_SERVICE_ROLE_KEY not set"
  exit 1
fi

echo "🚀 Phase 2 Batch Processing Test"
echo "================================"
echo ""
echo "Creating batch jobs for 5 symbols (NVDA, TSLA, AMD, META, NFLX)"
echo "Timeframes: h1, d1"
echo ""

# Create batch jobs
curl -X POST \
  "${SUPABASE_URL}/functions/v1/batch-backfill-orchestrator" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["NVDA", "TSLA", "AMD", "META", "NFLX"],
    "timeframes": ["h1", "d1"],
    "sliceType": "historical"
  }' | jq '.'

echo ""
echo "✅ Batch jobs created!"
echo ""
echo "📊 Checking job_definitions..."
echo ""

# Query to check created jobs
psql "${DATABASE_URL}" <<SQL
SELECT 
  id,
  symbol,
  timeframe,
  job_type,
  batch_version,
  jsonb_array_length(symbols_array) AS batch_size,
  symbols_array,
  batch_number,
  total_batches,
  enabled,
  created_at
FROM job_definitions
WHERE batch_version = 2
ORDER BY created_at DESC
LIMIT 10;
SQL

echo ""
echo "📈 Next steps:"
echo "1. Wait for orchestrator cron to pick up these jobs"
echo "2. Monitor job_runs table for progress"
echo "3. Check logs: supabase functions logs fetch-bars-batch"
echo ""
echo "Or manually trigger orchestrator:"
echo "curl -X POST '${SUPABASE_URL}/functions/v1/orchestrator?action=tick' \\"
echo "  -H 'Authorization: Bearer \$SUPABASE_SERVICE_ROLE_KEY'"
