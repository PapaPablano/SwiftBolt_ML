# ML Forecast Database Schema Fix

**Date:** 2026-01-24  
**Status:** ✅ COMPLETE - Migration applied and pushed  
**Commit:** `23b5ba5`

## Problem Summary

The ML forecast pipeline was working correctly in Python (5/5 symbols processed successfully), but **all 40 forecasts failed to save** to the database with error:

```
Error upserting forecast: {
  'message': 'there is no unique or exclusion constraint matching the ON CONFLICT specification',
  'code': '42P10'
}
```

## Root Cause

**Schema Mismatch:**
- Python code: `upsert(..., on_conflict="symbol_id,timeframe,horizon")`
- Database constraint: `UNIQUE(symbol_id, horizon)` ← **missing `timeframe`!**

The `timeframe` column was added to `ml_forecasts` in migration `20260121000000` to support multi-timeframe forecasting, but the unique constraint was never updated to include it.

## Solution

Created and applied migration: `20260124000000_fix_ml_forecasts_unique_constraint.sql`

### What It Does:

1. **Drops** old `UNIQUE(symbol_id, horizon)` constraint
2. **Creates** new `UNIQUE(symbol_id, timeframe, horizon)` index
3. **Backfills** existing rows with `timeframe='d1'` default
4. **Enforces** `timeframe NOT NULL` constraint

### Migration Applied:

```sql
CREATE UNIQUE INDEX ux_ml_forecasts_symbol_timeframe_horizon
ON ml_forecasts(symbol_id, timeframe, horizon);
```

## Verification

**Database Status:**
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'ml_forecasts' AND indexname LIKE 'ux_%';
```

Result: ✅ `ux_ml_forecasts_symbol_timeframe_horizon` created successfully

## Expected Outcome

Next GitHub Actions `ml-forecast` run will show:
- ✅ 5/5 symbols processed
- ✅ 40/40 forecasts saved (5 symbols × 8 horizons: 1D, 1W, 1M, 2M, 3M, 4M, 5M, 6M)
- ✅ No more error `42P10`
- ✅ Forecasts queryable in `ml_forecasts` table

## Related Files

- **Python Code:** `ml/src/data/supabase_db.py` (line 818-821)
- **Migration:** `supabase/migrations/20260124000000_fix_ml_forecasts_unique_constraint.sql`
- **Schema Definition:** `supabase/migrations/003_ml_forecasts_table.sql`
- **Multi-horizon Update:** `supabase/migrations/20260121000000_multi_horizon_forecasts.sql`

## Testing

To manually test the fix works:

```bash
# Re-trigger GitHub Actions workflow
gh workflow run ml-forecast.yml

# Or run locally
cd ml
python -m src.unified_forecast_job --symbol AAPL
```

## Notes

- Python code changes (`current_price` field, `ForecastWeights` conversion) were already committed in `0ef76d82` on 2026-01-23
- This migration completes the fix by aligning the database schema with the Python code expectations
- The old `UNIQUE(symbol_id, horizon)` constraint would have prevented storing forecasts for the same symbol/horizon across different timeframes (e.g., both `m15/1D` and `h1/1D`)
