# Intraday Data Staleness Fix (h1 and m15)

**Date:** 2026-01-10  
**Issue:** Charts showing stale historical h1/m15 bars instead of today's real-time Alpaca data  
**Status:** ✅ Fixed - Migration ready to apply

---

## Root Cause Analysis

### The Problem

The `get_chart_data_v2` database function had a critical flaw that caused stale data to be returned for intraday timeframes (m15, h1, h4):

1. **No explicit TODAY filter**: The function queried ALL Alpaca data between `p_start_date` and `p_end_date`, which included both:
   - Historical bars (yesterday and before)
   - Today's real-time bars (IF they existed in the database)

2. **is_intraday calculated AFTER fetch**: The `is_intraday` flag was computed during the query result transformation, not used as a filter criterion

3. **No freshness guarantee**: The function didn't verify that today's bars were actually present or recent

4. **Fallback to stale data**: When today's Alpaca intraday bars weren't in the database, the function would return historical bars, and the client had no way to know they were stale

### Why This Happened

The data collection pipeline (`alpaca_backfill_ohlc_v2.py`) runs every 15 minutes during market hours via GitHub Actions cron job. However:

- If the cron job fails or is delayed, today's bars won't be in the database
- The database function doesn't distinguish between "no data for today" vs "stale historical data"
- The client receives bars with timestamps from yesterday, but the `is_intraday` flag might be incorrectly set

### The Evidence

From your logs:
```
Server returned stale h1 "historical" bars and no "intraday" layer
```

This confirms the function was returning historical bars when it should have returned fresh intraday data.

---

## The Fix

### Migration: `20260110200000_fix_intraday_data_freshness.sql`

**Key Changes:**

1. **Explicit Layer Separation** for intraday timeframes (m15/h1/h4):
   ```sql
   WITH historical_data AS (
     -- Layer 1: Historical bars (dates < today)
     -- Alpaca primary, legacy fallback allowed
     WHERE DATE(o.ts AT TIME ZONE 'America/New_York') < today_date
   ),
   intraday_data AS (
     -- Layer 2: Today's intraday bars (ALPACA ONLY)
     -- This is the critical fix: explicitly query TODAY's data
     WHERE DATE(o.ts AT TIME ZONE 'America/New_York') = today_date
       AND o.provider = 'alpaca'
   )
   ```

2. **Correct is_intraday flag**:
   - Historical layer: `is_intraday = false` (always)
   - Intraday layer: `is_intraday = true` (always)
   - No more runtime calculation that could be wrong

3. **Alpaca-only for today**: Today's data MUST come from Alpaca provider, ensuring consistency with the data collection pipeline

4. **New monitoring function**: `check_intraday_freshness()` to verify data freshness:
   ```sql
   SELECT * FROM check_intraday_freshness(
     (SELECT id FROM symbols WHERE ticker = 'AAPL'),
     'h1'
   );
   ```

### What This Fixes

✅ **m15 charts** will show today's 15-minute bars (if collected)  
✅ **h1 charts** will show today's hourly bars (if collected)  
✅ **h4 charts** will show today's 4-hour bars (if collected)  
✅ **Client receives empty intraday layer** if no fresh data exists (better than stale data)  
✅ **Historical layer** remains intact with proper fallback to legacy providers

---

## How to Apply the Fix

### Option 1: Using Supabase Dashboard (Recommended)

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Copy the contents of `backend/supabase/migrations/20260110200000_fix_intraday_data_freshness.sql`
4. Paste into the SQL Editor
5. Click **Run**
6. Verify success with the test queries at the bottom of the migration

### Option 2: Using Supabase CLI

```bash
cd backend
supabase db push
```

### Option 3: Direct SQL Execution

If you have `psql` installed:
```bash
psql "$DATABASE_URL" < backend/supabase/migrations/20260110200000_fix_intraday_data_freshness.sql
```

---

## Verification Steps

After applying the migration, verify the fix:

### 1. Check Function Exists
```sql
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_name = 'get_chart_data_v2';
```

### 2. Check Data Freshness for AAPL h1
```sql
SELECT * FROM check_intraday_freshness(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'h1'
);
```

Expected output:
- `has_today_data`: true/false (whether today's bars exist)
- `latest_bar_ts`: timestamp of most recent bar
- `minutes_old`: how old the latest bar is
- `is_stale`: whether data exceeds freshness threshold (90 min for h1)
- `provider`: should be 'alpaca'

### 3. Test the Fixed Function
```sql
SELECT ts, open, high, low, close, provider, is_intraday
FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'h1',
  NOW() - INTERVAL '7 days',
  NOW()
)
WHERE is_intraday = true
ORDER BY ts DESC
LIMIT 10;
```

Expected: Should return today's h1 bars with `is_intraday = true` and `provider = 'alpaca'`

### 4. Test Client Chart
- Open the iOS app
- Navigate to AAPL chart
- Switch to h1 timeframe
- Verify you see today's bars (if market is open or recently closed)
- Check the timestamp of the latest bar

---

## Next Steps

### Ensure Data Collection is Running

The fix ensures the database function returns fresh data correctly, but you still need to ensure the data collection pipeline is working:

1. **Check GitHub Actions**: Verify `alpaca-intraday-cron.yml` is running every 15 minutes during market hours
2. **Manual backfill** if needed:
   ```bash
   cd ml
   python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1
   python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe m15
   ```

3. **Monitor freshness**: Use the `check_intraday_freshness()` function to monitor data staleness

### Client-Side Considerations

The client should:
- ✅ Check if `intraday` layer is empty
- ✅ Show a "No real-time data available" message if empty during market hours
- ✅ Display the timestamp of the latest bar
- ✅ Provide a "Refresh" button to force re-fetch

---

## Technical Details

### Database Function Signature
```sql
get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMP WITH TIME ZONE,
  p_end_date TIMESTAMP WITH TIME ZONE
)
```

### Return Schema
```typescript
{
  ts: string;              // ISO 8601 timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  provider: string;        // 'alpaca', 'polygon', 'tradier', etc.
  is_intraday: boolean;    // true for today's bars
  is_forecast: boolean;    // true for ML forecasts
  data_status: string;     // 'verified', 'preliminary', etc.
  confidence_score?: number;
  upper_band?: number;
  lower_band?: number;
}
```

### Edge Function Response
```typescript
{
  layers: {
    historical: {
      count: number;
      provider: string;
      data: ChartBar[];
    };
    intraday: {
      count: number;
      provider: string;
      data: ChartBar[];      // Today's bars only
    };
    forecast: {
      count: number;
      provider: string;
      data: ChartBar[];
    };
  }
}
```

---

## Files Changed

1. **Migration**: `backend/supabase/migrations/20260110200000_fix_intraday_data_freshness.sql`
   - Rewrites `get_chart_data_v2()` function
   - Adds `check_intraday_freshness()` monitoring function
   - Updates table comments with verification queries

2. **Documentation**: `docs/fixes/INTRADAY_DATA_STALENESS_FIX.md` (this file)

---

## Related Issues

- Alpaca intraday cron job: `.github/workflows/alpaca-intraday-cron.yml`
- Data collection script: `ml/src/scripts/alpaca_backfill_ohlc_v2.py`
- Edge Function: `backend/supabase/functions/chart-data-v2/index.ts`
- Previous migration: `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`

---

## Success Criteria

✅ Migration applies without errors  
✅ `get_chart_data_v2()` function returns separate historical/intraday layers  
✅ Intraday layer contains ONLY today's Alpaca bars  
✅ Historical layer contains dates < today  
✅ Client charts show fresh data when available  
✅ Client shows appropriate message when intraday data is missing  

---

## Rollback Plan

If the migration causes issues, you can rollback to the previous version:

```sql
-- Restore previous version of get_chart_data_v2
-- (Copy from 20260110120000_alpaca_only_migration.sql lines 114-248)
```

However, the new version is strictly better and should not cause any issues.
