# Timeframe Mismatch Fix

## Problem Summary

The workflow health check revealed a **timeframe mismatch** between the indicator persistence system and the forecast generation system:

### Issue 1: Missing Indicators (timeframe="legacy")
- **Symptoms**: Forecasts exist with `timeframe="legacy"` but no corresponding indicators
- **Affected Records**: All symbols (AAPL, AMD, CRWD, GOOG, MSFT, MU, NVDA, PLTR, SPY, TSLA)
- **Root Cause**: `unified_forecast_job.py` was not passing the `timeframe` parameter to `db.upsert_forecast()`, causing it to default to "legacy"

### Issue 2: Missing Forecasts (modern timeframes)
- **Symptoms**: Indicators exist for modern timeframes (m15, h1, h4, h8, d1) but no forecasts
- **Affected Timeframes**: m15, h1, h4, h8, d1
- **Root Cause**: Same as Issue 1 - forecasts were being written to "legacy" instead of the actual timeframe

## Root Cause Analysis

### Code Location
`@/Users/ericpeterson/SwiftBolt_ML/ml/src/data/supabase_db.py:801`

```python
timeframe_value = timeframe or "legacy"
```

When `timeframe` parameter is `None` or not provided, it defaults to `"legacy"`.

### Missing Parameter
`@/Users/ericpeterson/SwiftBolt_ML/ml/src/unified_forecast_job.py:575`

The `upsert_forecast()` call was missing the `timeframe` parameter:

```python
db.upsert_forecast(
    symbol_id=symbol_id,
    horizon=forecast["horizon"],
    overall_label=forecast["label"],
    confidence=forecast["confidence"],
    points=forecast["points"],
    forecast_return=forecast.get("forecast_return"),
    supertrend_data=supertrend_data,
    quality_score=quality_score,
    quality_issues=quality_issues,
    synthesis_data=forecast.get("synthesis"),
    # timeframe parameter was MISSING
)
```

## Solution

Added `timeframe="d1"` parameter to the `upsert_forecast()` call in `unified_forecast_job.py`:

```python
db.upsert_forecast(
    symbol_id=symbol_id,
    horizon=forecast["horizon"],
    overall_label=forecast["label"],
    confidence=forecast["confidence"],
    points=forecast["points"],
    forecast_return=forecast.get("forecast_return"),
    supertrend_data=supertrend_data,
    quality_score=quality_score,
    quality_issues=quality_issues,
    synthesis_data=forecast.get("synthesis"),
    timeframe="d1",  # ✅ ADDED
)
```

### Why "d1"?

The `unified_forecast_job.py` uses daily (d1) data as the primary source for forecast generation:

```python
# Line 235
df = features_by_tf.get("d1", pd.DataFrame())
```

All forecasts are generated from this daily timeframe data, so `timeframe="d1"` correctly reflects the data source.

## Expected Outcome

After this fix and the next forecast run:

1. **New forecasts** will be written with `timeframe="d1"`
2. **Indicators** already exist for `timeframe="d1"` 
3. **Pipeline status** will change from `MISSING_FORECAST` → `OK`
4. **Legacy forecasts** with `timeframe="legacy"` will remain but won't be updated

## Verification Query

Run this query after the next forecast job completes:

```sql
-- Check pipeline health after fix
WITH latest_indicators AS (
    SELECT 
        s.ticker,
        iv.timeframe,
        MAX(iv.created_at) as latest_indicator_time
    FROM indicator_values iv
    JOIN symbols s ON s.id = iv.symbol_id
    WHERE iv.created_at > NOW() - INTERVAL '2 hours'
    GROUP BY s.ticker, iv.timeframe
),
latest_forecasts AS (
    SELECT 
        s.ticker,
        mf.timeframe,
        MAX(mf.run_at) as latest_forecast_time
    FROM ml_forecasts mf
    JOIN symbols s ON s.id = mf.symbol_id
    WHERE mf.run_at > NOW() - INTERVAL '2 hours'
    GROUP BY s.ticker, mf.timeframe
)
SELECT 
    COALESCE(li.ticker, lf.ticker) as symbol,
    COALESCE(li.timeframe, lf.timeframe) as timeframe,
    li.latest_indicator_time,
    lf.latest_forecast_time,
    CASE 
        WHEN li.latest_indicator_time IS NULL THEN 'MISSING_INDICATORS'
        WHEN lf.latest_forecast_time IS NULL THEN 'MISSING_FORECAST'
        WHEN lf.latest_forecast_time < li.latest_indicator_time THEN 'FORECAST_STALE'
        ELSE 'OK'
    END as pipeline_status
FROM latest_indicators li
FULL OUTER JOIN latest_forecasts lf 
    ON li.ticker = lf.ticker AND li.timeframe = lf.timeframe
WHERE COALESCE(li.timeframe, lf.timeframe) = 'd1'
ORDER BY symbol;
```

Expected result: All records should show `pipeline_status = 'OK'`

## Cleanup (Optional)

To remove old legacy forecasts:

```sql
-- Delete legacy forecasts (optional cleanup)
DELETE FROM ml_forecasts 
WHERE timeframe = 'legacy' 
AND run_at < NOW() - INTERVAL '7 days';
```

## Related Files

- `@/Users/ericpeterson/SwiftBolt_ML/ml/src/unified_forecast_job.py:586` - Fixed
- `@/Users/ericpeterson/SwiftBolt_ML/ml/src/data/supabase_db.py:801` - Default behavior
- `@/Users/ericpeterson/SwiftBolt_ML/scripts/verify_workflow_data.sql:337` - Diagnostic query

## Date
2026-01-26
