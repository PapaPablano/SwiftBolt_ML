# Watchlist Data Reload Guide (Post-Spec8)

## Overview

With spec8 disabled, watchlist data loading now uses a direct Alpaca-only strategy via the `chart-data-v2` edge function. This guide explains how to reset and reload watchlist data.

## Architecture

### Data Flow (Without Spec8)
```
Client → reload-watchlist-data → symbol-init → chart-data-v2 → ohlc_bars_v2
                                                                      ↓
                                                                  Alpaca API
```

### Key Components

1. **`chart-data-v2` Edge Function**: Queries `ohlc_bars_v2` directly with Alpaca-only strategy
2. **`symbol-init` Edge Function**: Initializes symbols and triggers data loads
3. **`reload-watchlist-data` Edge Function**: Batch reloads all watchlist symbols
4. **`get_chart_data_v2()` Function**: Database function with Alpaca preference

## How to Reload Watchlist Data

### Option 1: Via Swift Client (Recommended)

```swift
// In your WatchlistViewModel or any view
await watchlistViewModel.reloadAllData(
    forceRefresh: true,      // Force reload even if data exists
    timeframes: ["d1", "h1"]  // Timeframes to load
)
```

### Option 2: Via SQL Script

1. Open Supabase SQL Editor
2. Run the script: `backend/scripts/reset_watchlist_data.sql`
3. This will show current watchlist and prepare for reload
4. Then call the edge function (see Option 3)

### Option 3: Via Edge Function Directly

```bash
curl -X POST \
  https://your-project.supabase.co/functions/v1/reload-watchlist-data \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "forceRefresh": true,
    "timeframes": ["d1", "h1", "m15"],
    "symbols": ["AAPL", "MSFT"]  // Optional: specific symbols only
  }'
```

## Deployment Steps

### 1. Deploy Edge Function

```bash
cd backend/supabase/functions
supabase functions deploy reload-watchlist-data
```

### 2. Test the Function

```bash
# Test with a single symbol
curl -X POST \
  https://your-project.supabase.co/functions/v1/reload-watchlist-data \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "forceRefresh": false,
    "timeframes": ["d1"],
    "symbols": ["AAPL"]
  }'
```

### 3. Verify Data Loaded

```sql
-- Check data for a specific symbol
SELECT 
  timeframe,
  COUNT(*) as bars,
  MIN(ts) as earliest,
  MAX(ts) as latest,
  STRING_AGG(DISTINCT provider, ', ') as providers
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY timeframe
ORDER BY timeframe;
```

## What Gets Loaded

### Timeframes
- **d1**: 730 days (2 years) of daily data
- **h1**: 60 days of hourly data
- **m15**: 60 days of 15-minute data (optional)

### Data Sources
- **Primary**: Alpaca (high-quality, 7+ years history)
- **Fallback**: Legacy providers (polygon, tradier) - read-only

### Data Layers
- **Historical**: All data before today
- **Intraday**: Today's real-time data
- **Forecast**: ML predictions (future dates)

## Monitoring

### Check Reload Status

```swift
// In Swift client
let response = try await apiClient.reloadWatchlistData(
    forceRefresh: false,
    timeframes: ["d1", "h1"]
)

print("Success: \(response.summary.success)/\(response.summary.total)")
for result in response.results {
    print("\(result.symbol): \(result.status)")
    if let bars = result.barsLoaded {
        print("  d1: \(bars.d1 ?? 0), h1: \(bars.h1 ?? 0)")
    }
}
```

### Check Data Health

```sql
-- Overall watchlist data health
SELECT 
  s.ticker,
  COUNT(DISTINCT CASE WHEN o.timeframe = 'd1' THEN o.ts END) as d1_bars,
  COUNT(DISTINCT CASE WHEN o.timeframe = 'h1' THEN o.ts END) as h1_bars,
  MAX(CASE WHEN o.timeframe = 'd1' THEN o.ts END) as d1_latest,
  MAX(CASE WHEN o.timeframe = 'h1' THEN o.ts END) as h1_latest,
  STRING_AGG(DISTINCT o.provider, ', ' ORDER BY o.provider) as providers
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
GROUP BY s.ticker
ORDER BY s.ticker;
```

## Differences from Spec8

| Feature | Spec8 | New System |
|---------|-------|------------|
| **Orchestration** | Background cron jobs | On-demand via edge function |
| **Data Source** | Multiple providers | Alpaca-only (with legacy fallback) |
| **Job Tracking** | `job_runs` table | Direct API response |
| **Progress Updates** | Realtime subscriptions | Synchronous response |
| **Complexity** | High (orchestrator + workers) | Low (direct calls) |

## Troubleshooting

### No Data Loaded

1. Check if symbol exists in `symbols` table
2. Verify Alpaca API key is configured
3. Check edge function logs in Supabase dashboard
4. Try with `forceRefresh: true`

### Partial Data

1. Check provider availability in logs
2. Verify timeframe is supported (d1, h1, m15)
3. Check for rate limiting errors
4. Review `ohlc_bars_v2` for existing data

### Slow Performance

1. Reduce number of timeframes
2. Reload specific symbols instead of all
3. Check Alpaca API rate limits
4. Consider running during off-peak hours

## Best Practices

1. **Initial Load**: Use `forceRefresh: false` to avoid unnecessary API calls
2. **Daily Updates**: Data automatically updates via `chart-data-v2` when accessed
3. **Batch Operations**: Reload all symbols at once rather than individually
4. **Timeframe Selection**: Start with d1, add h1 only if needed for intraday analysis
5. **Monitoring**: Check data health weekly using SQL queries above

## Migration from Spec8

If you were using spec8 previously:

1. **Disable spec8**: Already done via `Config.ensureCoverageEnabled = false`
2. **Remove spec8 client code**: See main analysis for code to remove
3. **Deploy new edge function**: `supabase functions deploy reload-watchlist-data`
4. **Run initial reload**: Use `reloadAllData(forceRefresh: true)`
5. **Verify data**: Check using SQL queries above

## Related Files

- **Edge Function**: `backend/supabase/functions/reload-watchlist-data/index.ts`
- **SQL Script**: `backend/scripts/reset_watchlist_data.sql`
- **Swift Client**: `client-macos/SwiftBoltML/Services/APIClient.swift`
- **ViewModel**: `client-macos/SwiftBoltML/ViewModels/WatchlistViewModel.swift`
- **Response Model**: `client-macos/SwiftBoltML/Models/ReloadWatchlistResponse.swift`

## Support

For issues or questions:
1. Check edge function logs in Supabase dashboard
2. Review SQL query results for data verification
3. Check Swift console logs for client-side errors
4. Verify Alpaca API key and rate limits
