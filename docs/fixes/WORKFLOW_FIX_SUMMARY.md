# Workflow Fix - Environment Variables

## Issue

The "Daily Data Refresh" workflow was failing because:

1. **Alpaca credentials not accessible**: The `.env` file was created but environment variables weren't exported to the Python scripts
2. **Validation script bug**: TypeError when calculating gap days (string vs datetime)

## Root Cause

The workflow had two steps:
1. "Configure environment" - Created `.env` file
2. "Run incremental data refresh" - Ran Python scripts

**Problem**: Python scripts using `os.getenv()` don't automatically read from `.env` files unless using `python-dotenv`. The scripts expected environment variables to be set directly.

## Solution

### Fix 1: Export Environment Variables to Backfill Step

Added `env:` block to the "Run incremental data refresh" step:

```yaml
- name: Run incremental data refresh
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
    ALPACA_API_SECRET: ${{ secrets.ALPACA_API_SECRET }}
  run: |
    cd ml
    python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe m15
    # ... etc
```

### Fix 2: Fix Validation Script TypeError

Updated `backfill_with_gap_detection.py` to handle string timestamps:

```python
if issue['largest_gap']:
    gap_start, gap_end = issue['largest_gap']
    # Convert string timestamps to datetime if needed
    if isinstance(gap_start, str):
        from datetime import datetime
        gap_start = datetime.fromisoformat(gap_start.replace('Z', '+00:00'))
        gap_end = datetime.fromisoformat(gap_end.replace('Z', '+00:00'))
    gap_days = (gap_end - gap_start).days
```

## Files Modified

1. `@/Users/ericpeterson/SwiftBolt_ML/.github/workflows/daily-data-refresh.yml`
   - Added `env:` block to backfill step
   
2. `@/Users/ericpeterson/SwiftBolt_ML/ml/src/scripts/backfill_with_gap_detection.py`
   - Fixed TypeError in gap calculation

## Expected Behavior After Fix

When the workflow runs:
1. ✅ Alpaca credentials will be accessible to Python scripts
2. ✅ All timeframes (m15, h1, h4, d1, w1) will backfill successfully
3. ✅ Validation script will run without errors
4. ✅ Fresh intraday data will be available in the app

## Testing

Re-run the "Daily Data Refresh" workflow:
1. Go to Actions → Daily Data Refresh
2. Click "Run workflow"
3. Monitor logs for successful backfill
4. Check app for fresh h1 data

## Why This Happened

The initial workflow setup assumed `.env` files would be automatically loaded. However:
- GitHub Actions doesn't automatically source `.env` files
- Python scripts using `os.getenv()` only read from actual environment variables
- The `python-dotenv` library would load `.env` files, but scripts use direct `os.getenv()`

The fix ensures environment variables are set at the step level, making them available to all commands in that step.
