#!/bin/bash
# Migrate Existing Universe to Phase 2 Batch Processing
# This creates batch_version=2 jobs for all symbols currently in job_definitions

set -e

SUPABASE_URL="${SUPABASE_URL:-https://cygflaemtmwiwaviclks.supabase.co}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo "❌ Error: SUPABASE_SERVICE_ROLE_KEY not set"
  exit 1
fi

echo "🔄 Migrating Existing Universe to Phase 2 Batch Processing"
echo "=========================================================="
echo ""

# Get all unique symbols from existing job_definitions
echo "📊 Fetching current symbols from job_definitions..."
SYMBOLS=$(psql "${DATABASE_URL}" -t -c "
  SELECT DISTINCT symbol 
  FROM job_definitions 
  WHERE batch_version = 1 
    AND symbol NOT LIKE 'BATCH_%'
    AND symbol NOT LIKE 'TEST_%'
  ORDER BY symbol;
" | tr '\n' ',' | sed 's/,$//' | sed 's/ //g')

if [ -z "$SYMBOLS" ]; then
  echo "❌ No symbols found to migrate"
  exit 1
fi

# Convert to JSON array
SYMBOLS_ARRAY=$(echo "$SYMBOLS" | awk -F',' '{
  printf "["
  for(i=1; i<=NF; i++) {
    if(i>1) printf ","
    printf "\"%s\"", $i
  }
  printf "]"
}')

SYMBOL_COUNT=$(echo "$SYMBOLS" | tr ',' '\n' | wc -l | tr -d ' ')

echo "✅ Found $SYMBOL_COUNT symbols to migrate"
echo ""
echo "Symbols: $SYMBOLS"
echo ""
echo "⚠️  This will create batch_version=2 jobs alongside existing batch_version=1 jobs"
echo "   Old jobs will remain enabled but can be disabled later"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled"
  exit 0
fi

echo ""
echo "🚀 Creating Phase 2 batch jobs..."
echo ""

# Create batch jobs for all standard timeframes
curl -X POST \
  "${SUPABASE_URL}/functions/v1/batch-backfill-orchestrator" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'Content-Type: application/json' \
  -d "{
    \"symbols\": ${SYMBOLS_ARRAY},
    \"timeframes\": [\"m15\", \"h1\", \"h4\", \"d1\"],
    \"sliceType\": \"historical\"
  }" | jq '.'

echo ""
echo "✅ Phase 2 batch jobs created!"
echo ""
echo "📊 Verifying batch jobs..."
echo ""

psql "${DATABASE_URL}" <<SQL
-- Show batch job summary
SELECT 
  batch_version,
  COUNT(*) as job_count,
  COUNT(DISTINCT timeframe) as timeframes,
  SUM(CASE WHEN symbols_array IS NOT NULL THEN jsonb_array_length(symbols_array) ELSE 1 END) as total_symbols
FROM job_definitions
GROUP BY batch_version
ORDER BY batch_version;

-- Show Phase 2 batch jobs
SELECT 
  symbol,
  timeframe,
  jsonb_array_length(symbols_array) AS batch_size,
  batch_number,
  total_batches,
  enabled
FROM job_definitions
WHERE batch_version = 2
ORDER BY timeframe, batch_number;
SQL

echo ""
echo "📈 Next Steps:"
echo "============="
echo ""
echo "1. Monitor the orchestrator to ensure batch jobs are being processed:"
echo "   curl '${SUPABASE_URL}/functions/v1/orchestrator?action=status' \\"
echo "     -H 'Authorization: Bearer \$SUPABASE_SERVICE_ROLE_KEY' | jq '.'"
echo ""
echo "2. Check job_runs for batch job execution:"
echo "   SELECT * FROM job_runs WHERE created_at > now() - interval '1 hour' ORDER BY created_at DESC;"
echo ""
echo "3. Monitor API efficiency (should see ~50x reduction in API calls):"
echo "   SELECT COUNT(*) FROM job_runs WHERE created_at > now() - interval '1 day';"
echo ""
echo "4. Once Phase 2 is proven stable, disable Phase 1 jobs:"
echo "   UPDATE job_definitions SET enabled = false WHERE batch_version = 1;"
echo ""
echo "5. Eventually clean up Phase 1 jobs:"
echo "   DELETE FROM job_definitions WHERE batch_version = 1 AND enabled = false;"
echo ""
