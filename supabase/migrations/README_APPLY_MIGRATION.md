# How to Apply the Intraday Data Freshness Fix

## Quick Start

Apply the migration `20260110200000_fix_intraday_data_freshness.sql` using **Supabase Dashboard SQL Editor**:

1. Open your Supabase project dashboard
2. Go to **SQL Editor** (left sidebar)
3. Click **New Query**
4. Copy the entire contents of `20260110200000_fix_intraday_data_freshness.sql`
5. Paste into the editor
6. Click **Run** (or press Cmd/Ctrl + Enter)
7. Wait for "Success" message

## What This Fixes

✅ h1 and m15 charts will show **today's fresh Alpaca data** instead of stale historical bars  
✅ Explicit separation of historical vs intraday data layers  
✅ Proper `is_intraday` flag for today's bars  
✅ New `check_intraday_freshness()` function to monitor data staleness

## Verification

After applying, run this in SQL Editor to verify:

```sql
-- Check if function was updated
SELECT routine_name, last_altered 
FROM information_schema.routines 
WHERE routine_name = 'get_chart_data_v2';

-- Test with AAPL h1 data
SELECT ts, open, close, provider, is_intraday
FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'h1',
  NOW() - INTERVAL '7 days',
  NOW()
)
WHERE is_intraday = true
ORDER BY ts DESC
LIMIT 5;
```

Expected: Should return today's h1 bars with `is_intraday = true` and `provider = 'alpaca'`

## Full Documentation

See `docs/fixes/INTRADAY_DATA_STALENESS_FIX.md` for complete details.
