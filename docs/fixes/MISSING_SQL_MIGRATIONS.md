# Missing SQL Migrations - Action Required

## Issue

The GitHub Actions workflow "Daily Data Refresh" is failing because required SQL functions are missing from the database.

## Error Messages

```
Could not find the function public.detect_ohlc_gaps(p_max_gap_hours, p_symbol, p_timeframe) in the schema cache
Could not find the function public.get_ohlc_coverage_stats(p_symbol, p_timeframe) in the schema cache
```

## Root Cause

The migration file `20260110220000_add_gap_detection_rpc_functions.sql` exists locally but **has not been applied** to the Supabase database.

## Required Migrations to Apply

### 1. Gap Detection Functions (CRITICAL)
**File**: `backend/supabase/migrations/20260110220000_add_gap_detection_rpc_functions.sql`

**Creates**:
- `detect_ohlc_gaps(p_symbol, p_timeframe, p_max_gap_hours)` - Detects data gaps
- `get_ohlc_coverage_stats(p_symbol, p_timeframe)` - Returns coverage statistics

**Used by**: `ml/src/scripts/backfill_with_gap_detection.py` (called by daily-data-refresh workflow)

### 2. Simplified Chart Data Function (RECOMMENDED)
**File**: `backend/supabase/migrations/20260110210000_simplify_chart_data_v2_unified.sql`

**Updates**:
- `get_chart_data_v2()` - Simplified unified query for all timeframes

**Benefits**: Removes intraday/historical distinction, aligns with Alpaca-first strategy

## How to Apply Migrations

### Option 1: Supabase Dashboard (Recommended)
1. Go to https://supabase.com/dashboard
2. Select your project
3. Navigate to **SQL Editor**
4. Copy the contents of each migration file
5. Execute them in order:
   - `20260110210000_simplify_chart_data_v2_unified.sql`
   - `20260110220000_add_gap_detection_rpc_functions.sql`

### Option 2: Supabase CLI
```bash
cd backend/supabase
supabase db push
```

### Option 3: Manual SQL Execution
```bash
# From project root
psql $DATABASE_URL < backend/supabase/migrations/20260110210000_simplify_chart_data_v2_unified.sql
psql $DATABASE_URL < backend/supabase/migrations/20260110220000_add_gap_detection_rpc_functions.sql
```

## Verification

After applying migrations, verify functions exist:

```sql
-- Check if functions exist
SELECT 
  proname as function_name,
  pg_get_function_arguments(oid) as arguments
FROM pg_proc 
WHERE proname IN ('detect_ohlc_gaps', 'get_ohlc_coverage_stats', 'get_chart_data_v2')
ORDER BY proname;
```

Expected output:
```
function_name              | arguments
---------------------------+--------------------------------------------------
detect_ohlc_gaps           | p_symbol text, p_timeframe text, p_max_gap_hours integer DEFAULT 24
get_chart_data_v2          | p_symbol_id uuid, p_timeframe character varying, p_start_date timestamp with time zone, p_end_date timestamp with time zone
get_ohlc_coverage_stats    | p_symbol text, p_timeframe text
```

## Impact

**Until these migrations are applied**:
- ❌ Daily data refresh workflow will fail
- ❌ Gap detection won't work
- ❌ Coverage statistics unavailable
- ⚠️ Chart data may use old complex query logic

**After migrations are applied**:
- ✅ Daily data refresh will succeed
- ✅ Gap detection will identify missing data
- ✅ Coverage stats will track data quality
- ✅ Chart queries simplified and faster

## Related Files

- Migration files:
  - `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/migrations/20260110210000_simplify_chart_data_v2_unified.sql`
  - `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/migrations/20260110220000_add_gap_detection_rpc_functions.sql`

- Scripts that depend on these functions:
  - `@/Users/ericpeterson/SwiftBolt_ML/ml/src/scripts/backfill_with_gap_detection.py`

- Workflows affected:
  - `@/Users/ericpeterson/SwiftBolt_ML/.github/workflows/daily-data-refresh.yml`

## Next Steps

1. **IMMEDIATE**: Apply `20260110220000_add_gap_detection_rpc_functions.sql` to fix workflow
2. **RECOMMENDED**: Apply `20260110210000_simplify_chart_data_v2_unified.sql` for v2 migration
3. **VERIFY**: Re-run "Daily Data Refresh" workflow to confirm fix
4. **MONITOR**: Check workflow runs daily to ensure stability

---

**Status**: ⚠️ **ACTION REQUIRED** - Migrations must be applied manually to Supabase database
