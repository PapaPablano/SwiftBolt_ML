# Historical Data Backfill System

## Overview

The backfill system progressively fetches maximum historical data from APIs while respecting rate limits, storing all data in Supabase for rich charting and analysis.

## Architecture

### Components

1. **Backfill Edge Function** (`functions/backfill/index.ts`)
   - POST endpoint for triggering backfills
   - Intelligent chunked pagination
   - Rate limit awareness
   - Market hours filtering for intraday data

2. **Chart Endpoint** (updated `functions/chart/index.ts`)
   - Returns up to 1000 cached bars (vs previous 100)
   - Fetches from database in descending order (most recent first)
   - Falls back to live API only if cache is stale

3. **Database** (`ohlc_bars` table)
   - Stores all historical bars
   - Indexed by symbol_id, timeframe, timestamp
   - Unique constraint prevents duplicates

## API Limits & Strategy

### Finnhub Free Tier
- **Intraday windowing**: ~1 month per request
- **Rate limit**: 60 requests/min
- **Total**: Can backfill 12 months hourly data in ~12 requests

### Massive (Polygon.io) Free Tier
- **Historical depth**: Up to 2 years
- **Rate limit**: 5 requests/min (strict)
- **Windowing**: Flexible, but paginate to be safe

### Our Approach
- **Chunk size**: 1 month for intraday, 6 months for daily+
- **Delay between chunks**: 12 seconds (respects Massive's 5 req/min)
- **Market hours filtering**: Applied to all intraday data
- **Deduplication**: Database handles via unique constraints

## Default Backfill Targets

```typescript
const defaultMonths = {
  m1:  1,   // 1 minute: 1 month
  m5:  2,   // 5 minute: 2 months
  m15: 3,   // 15 minute: 3 months
  m30: 6,   // 30 minute: 6 months
  h1:  12,  // 1 hour: 1 year
  h4:  24,  // 4 hour: 2 years
  d1:  24,  // Daily: 2 years
  w1:  24,  // Weekly: 2 years
  mn1: 24,  // Monthly: 2 years
};
```

## Usage

### Manual Backfill

```bash
# Backfill 1 year of hourly data for AAPL
curl -X POST 'https://YOUR_PROJECT.supabase.co/functions/v1/backfill' \
  -H 'Content-Type: application/json' \
  -d '{
    "symbol": "AAPL",
    "timeframe": "h1",
    "targetMonths": 12
  }'

# Response:
{
  "symbol": "AAPL",
  "timeframe": "h1",
  "totalBarsInserted": 1234,
  "chunksProcessed": 12,
  "startDate": "2024-01-15T00:00:00.000Z",
  "endDate": "2025-01-15T00:00:00.000Z",
  "durationMs": 150000
}
```

### Auto-Backfill (Future)

Future enhancement: Trigger backfill automatically when:
1. New symbol is added to watchlist
2. User requests a timeframe with insufficient data
3. Scheduled nightly backfill job for active symbols

## Benefits

1. **Maximum historical data**: Charts can show years of data instead of just 100 bars
2. **Fast loading**: Most requests served from cache, not API
3. **Rate limit friendly**: Backfill runs slowly, respecting API limits
4. **Rich analysis**: More data = better patterns, indicators, ML training
5. **Cost effective**: Maximizes free tier usage without hitting limits

## Database Storage

### Estimated Storage per Symbol

- **1 year hourly** (~1,600 bars): ~80 KB
- **2 years daily** (~500 bars): ~25 KB
- **3 months 15min** (~5,000 bars): ~250 KB

Supabase free tier: 500 MB database
- Can store ~6,000 symbol-timeframe combinations
- Or ~100 symbols with full backfill across all timeframes

## Example: Full Backfill for AAPL

```bash
# Backfill all timeframes for AAPL
for tf in m15 m30 h1 h4 d1 w1; do
  curl -X POST 'https://YOUR_PROJECT.supabase.co/functions/v1/backfill' \
    -H 'Content-Type: application/json' \
    -d "{\"symbol\":\"AAPL\",\"timeframe\":\"$tf\"}"

  # Wait between requests to avoid rate limits
  sleep 30
done
```

## Monitoring

Check backfill progress:

```sql
-- Count bars per symbol/timeframe
SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) as bar_count,
  MIN(o.ts) as oldest_bar,
  MAX(o.ts) as newest_bar
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;
```

## Future Enhancements

1. **Incremental backfill**: Only fetch missing date ranges
2. **Auto-trigger**: Backfill on watchlist add or first chart view
3. **Progress tracking**: Store backfill status in database
4. **Webhook notifications**: Alert when backfill completes
5. **Batch backfill**: Process multiple symbols in parallel
6. **Gap detection**: Identify and fill missing data ranges
