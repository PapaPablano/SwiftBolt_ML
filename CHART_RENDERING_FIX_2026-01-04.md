# Chart Rendering Fix - ML Forecasts Overlaying Historical Data

## Issue Summary
Charts were showing ML forecast data overlaying on top of historical price bars, making it appear as if there were spikes or anomalies in the real price data. The user clarified that **only real OHLC data should be displayed as price bars**, and **ML forecasts should only appear as future projections beyond the current date**.

## Root Cause
ML forecasts were being generated with timestamps that overlapped with historical price data:

1. **Forecast generation issue** (`forecast_job.py` line 955):
   - Used `df["ts"].iloc[-1]` as starting timestamp
   - This is the timestamp of the **last historical bar**
   - Forecasts started from day 1 = last bar date, not next trading day
   - Example: If last bar is 2026-01-02, forecast points started at 2026-01-03 (only 1 day ahead)

2. **Chart endpoint had no filtering**:
   - ML forecast points were sent to frontend without checking timestamps
   - Frontend displayed all forecast points, including those overlapping historical data
   - This caused visual "spikes" where forecasts overlaid on real price bars

3. **Mixed timestamp formats**:
   - Some forecasts used Unix timestamps (integers like `1767474000`)
   - Others used ISO strings (`2026-01-03T00:00:00+00:00`)
   - Inconsistent handling could cause display issues

## Fix Applied

### 1. Chart Endpoint Filtering (`chart/index.ts`)
Added filtering logic to ensure ML forecasts only show future predictions:

```typescript
// 7. Filter ML forecast points to only show FUTURE predictions
// Forecasts should NOT overlay on historical price data
if (mlSummary && bars.length > 0) {
  const latestBarTs = new Date(bars[bars.length - 1].ts).getTime();
  
  // Filter each horizon's points to only include future timestamps
  mlSummary.horizons = mlSummary.horizons.map(horizon => ({
    ...horizon,
    points: horizon.points.filter((point) => {
      const pointTs = typeof point.ts === 'number' 
        ? point.ts * 1000  // Unix timestamp in seconds -> milliseconds
        : new Date(point.ts).getTime();
      return pointTs > latestBarTs;
    }),
  }));
}
```

**Key features**:
- Gets the latest historical bar timestamp
- Filters each forecast horizon's points
- Handles both Unix timestamps and ISO strings
- Only returns points with timestamps **after** the latest bar

### 2. Data Quality Fixes
Also fixed corrupted OHLC data that was causing visual anomalies:
- NVDA June 10, 2024: high $195.95 → $122.50 (was 60% above close)
- NVDA June 1, 2024: high $140.76 → $124.50 (was 14% above close)

### 3. Data Quality Monitoring
Created `detect_ohlc_anomalies()` function and validation trigger to prevent future bad data.

## Expected Behavior After Fix

### Historical Price Bars (OHLC)
- Display real market data only
- Show open, high, low, close, volume
- No ML forecast overlay
- Clean, accurate price history

### ML Forecast Display
- **Only appears beyond the latest bar timestamp**
- Shows as future projection lines/bands
- Includes confidence intervals (upper/lower bands)
- Separate visual treatment from historical bars

### Example Timeline
```
Historical Bars:     [============================] 2026-01-02
                                                    ^
                                                    Latest bar
ML Forecast:                                        [---------->] 2026-01-03+
                                                    Future only
```

## Remaining Work

### Short-term (Immediate)
1. ✅ Filter forecasts in chart endpoint
2. ⏳ Verify frontend correctly displays filtered forecasts
3. ⏳ Test across multiple symbols and timeframes

### Medium-term (Next Sprint)
1. Fix forecast generation to start from next trading day
   - Update `forecast_result_to_points()` to add 1 day to start_ts
   - Ensure forecasts never overlap with historical data at generation time
2. Standardize timestamp format (prefer ISO strings)
3. Add validation in forecast job to reject overlapping timestamps

### Long-term (Future Enhancement)
1. Add visual distinction between historical and forecast data in frontend
2. Implement forecast accuracy tracking by comparing predictions to actual outcomes
3. Add user controls for showing/hiding forecasts on charts

## Testing Checklist
- [ ] NVDA chart shows clean historical data without spikes
- [ ] ML forecasts only appear beyond latest bar
- [ ] Works for all timeframes (d1, w1, m1)
- [ ] Works for all symbols in watchlist
- [ ] Forecast confidence bands display correctly
- [ ] No console errors in chart endpoint logs

## Files Modified
- `backend/supabase/functions/chart/index.ts` - Added forecast filtering
- `backend/supabase/migrations/20260105000000_ohlc_data_quality_checks.sql` - Data quality monitoring
- Database: Fixed NVDA OHLC anomalies

## Related Issues
- Data quality issue: OHLC bars with anomalous high/low values
- Forecast generation: Starting timestamps overlap with historical data
- Timestamp format inconsistency: Unix vs ISO strings
