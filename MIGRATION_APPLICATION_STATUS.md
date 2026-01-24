# Multi-Leg Options Ranking Trigger - Migration Status

**Date**: 2026-01-23  
**Migration**: `20260123000000_multi_leg_options_ranking_trigger.sql`  
**Status**: ⚠️ **NEEDS MANUAL APPLICATION**

---

## Current Status

### ✅ Completed
- Migration file created: `supabase/migrations/20260123000000_multi_leg_options_ranking_trigger.sql`
- Test strategy created on MU: `dd629b8b-38a6-4ac8-bd50-7f227786344c`
- MU symbol exists: `519487c1-eecc-4459-a021-ae63e6ee6c88`

### ❌ Not Working
- **Trigger did not fire** when test strategy was created
- No ranking job was queued automatically
- Migration functions/triggers may not be applied correctly

---

## Issue

The automated migration execution method (splitting SQL by semicolon) doesn't work well for complex SQL with:
- Function definitions (multi-line)
- Trigger definitions (multi-line)
- Comments and formatting

**Result**: Migration was partially applied but triggers may not be active.

---

## Solution: Manual Application Required

### Option 1: Supabase Dashboard (Recommended)

1. Go to https://supabase.com/dashboard
2. Select your project: `cygflaemtmwiwaviclks`
3. Navigate to **SQL Editor**
4. Copy the entire contents of:
   ```
   supabase/migrations/20260123000000_multi_leg_options_ranking_trigger.sql
   ```
5. Paste into SQL Editor
6. Click **Run** to execute

### Option 2: Supabase CLI (If you have DATABASE_URL)

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Get DATABASE_URL from .env or Supabase dashboard
# Format: postgresql://postgres:[password]@[host]:5432/postgres

psql $DATABASE_URL -f supabase/migrations/20260123000000_multi_leg_options_ranking_trigger.sql
```

### Option 3: Python Script (Alternative)

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python3 scripts/deployment/execute_migration.py supabase/migrations/20260123000000_multi_leg_options_ranking_trigger.sql
```

---

## Verification After Application

### 1. Check Functions Exist

```sql
SELECT proname 
FROM pg_proc 
WHERE proname IN (
    'queue_ranking_on_multi_leg_create',
    'queue_ranking_on_multi_leg_reopen',
    'get_multi_leg_strategy_symbols',
    'queue_multi_leg_strategy_ranking_jobs'
);
```

**Expected**: Should return 4 rows

### 2. Check Triggers Exist

```sql
SELECT tgname, tgrelid::regclass as table_name
FROM pg_trigger 
WHERE tgname IN (
    'trigger_queue_ranking_on_multi_leg_create',
    'trigger_queue_ranking_on_multi_leg_reopen'
);
```

**Expected**: Should return 2 rows, both on `options_strategies` table

### 3. Test the Trigger

```sql
-- Create a test strategy (or use existing test strategy)
-- Then check for ranking job:

SELECT * 
FROM ranking_jobs 
WHERE symbol = 'MU' 
  AND created_at > NOW() - INTERVAL '5 minutes'
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected**: Should find a ranking job with:
- `status = 'pending'`
- `priority = 2` (higher than watchlist default)
- `requested_by` should NOT be 'pg_cron_hourly'

---

## Test Results

### Test Strategy Created
- **ID**: `dd629b8b-38a6-4ac8-bd50-7f227786344c`
- **Symbol**: MU
- **Status**: open
- **Created**: 2026-01-24T01:46:26.967811+00:00

### Ranking Jobs Checked
- **Found**: 5 existing jobs for MU (all from `pg_cron_hourly`)
- **Missing**: No job created after strategy creation
- **Conclusion**: Trigger did not fire

---

## Next Steps

1. **Apply migration manually** using Option 1 (Supabase Dashboard)
2. **Verify functions/triggers** using SQL queries above
3. **Test again** by creating a new multi-leg strategy or updating the existing test strategy
4. **Verify ranking job** is queued automatically

---

## What This Migration Does

When applied correctly, this migration will:

1. **Auto-queue ranking job** when a multi-leg strategy is created with `status='open'`
2. **Auto-queue ranking job** when a strategy is reopened from closed/expired status
3. **Provide helper functions** to:
   - Get all symbols with active multi-leg strategies
   - Queue ranking jobs for all multi-leg strategy symbols (for scheduled jobs)

**Benefits**:
- ✅ No need to manually add symbols to watchlist
- ✅ Options data automatically refreshed for multi-leg strategies
- ✅ Ensures current options prices for P&L calculations
- ✅ Works even if symbol isn't in watchlist

---

## Cleanup

After testing, you can delete the test strategy:

```sql
DELETE FROM options_strategies 
WHERE id = 'dd629b8b-38a6-4ac8-bd50-7f227786344c';
```

---

## Files

- **Migration**: `supabase/migrations/20260123000000_multi_leg_options_ranking_trigger.sql`
- **Test Script**: `test_multi_leg_ranking_trigger.py`
- **Documentation**: `DATA_REFRESH_AUDIT.md` (updated with this feature)
