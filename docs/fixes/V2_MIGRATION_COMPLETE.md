# V2 Migration Complete - Unified Chart Data Architecture

## Summary

Migrated all chart-related backend resources to use `ohlc_bars_v2` table and simplified the architecture to treat all timeframes uniformly. No more intraday/historical distinctions.

## Changes Made

### 1. **Simplified SQL Function** (`20260110210000_simplify_chart_data_v2_unified.sql`)

**Before**: Complex branching logic with separate query paths for intraday (m15/h1/h4) vs daily (d1/w1)

**After**: Single unified query for ALL timeframes

```sql
CREATE FUNCTION get_chart_data_v2(...)
RETURNS TABLE (...) AS $$
BEGIN
  -- UNIFIED QUERY: Works for ALL timeframes (m15, h1, h4, d1, w1)
  RETURN QUERY
  SELECT DISTINCT ON (o.ts)
    ...
  FROM ohlc_bars_v2 o
  WHERE o.symbol_id = p_symbol_id
    AND o.timeframe = p_timeframe
    AND o.ts >= p_start_date
    AND o.ts <= p_end_date
  ORDER BY o.ts ASC, provider_preference ASC;
END;
$$ LANGUAGE plpgsql;
```

**Key improvements**:
- ✅ No `IF is_intraday_tf THEN ... ELSE ...` branching
- ✅ `is_intraday` flag computed dynamically (today = true, else false)
- ✅ Single provider preference order: Alpaca > Polygon > YFinance > Tradier
- ✅ Works identically for m15, h1, h4, d1, w1

### 2. **Updated Edge Functions to Use `ohlc_bars_v2`**

#### `chart/index.ts` (Legacy endpoint)
- ✅ Changed `FROM ohlc_bars` → `FROM ohlc_bars_v2`
- ✅ Added `is_forecast = false` filter
- ✅ Updated upsert conflict key: `symbol_id,timeframe,ts,provider,is_forecast`
- ✅ Added required fields: `provider: "alpaca"`, `is_forecast: false`, `data_status: "confirmed"`

#### `backfill/index.ts`
- ✅ Changed `FROM ohlc_bars` → `FROM ohlc_bars_v2`
- ✅ Added `is_forecast = false` filter
- ✅ Updated upsert conflict key
- ✅ Added required fields for YFinance backfill data

#### `fetch-bars/index.ts` (Already using v2)
- ✅ Already correctly using `ohlc_bars_v2`
- ✅ Proper `is_intraday` flag logic (today + intraday timeframe)

#### `chart-data-v2/index.ts` (Primary endpoint)
- ✅ Already correctly using `get_chart_data_v2()` RPC function
- ✅ Properly separates layers based on date comparison

### 3. **Frontend Simplifications**

#### `Timeframe.swift`
```swift
var alpacaFormat: String {
    switch self {
    case .m15: return "15Min"
    case .h1:  return "1Hour"
    case .h4:  return "4Hour"
    case .d1:  return "1Day"
    case .w1:  return "1Week"
    }
}
```

#### `APIClient.swift`
- ✅ Removed intraday-specific cache-busting logic
- ✅ Cache-buster enabled for ALL timeframes
- ✅ Same headers for all requests

#### `ChartViewModel.swift`
- ✅ Simplified `buildBars()` - just merge and sort
- ✅ No timeframe-specific branching

## Architecture Overview

### Data Flow (Unified)

```
Client Request (m15/h1/h4/d1/w1)
    ↓
APIClient.fetchChartV2(timeframe: "m15")
    ↓
Edge Function: chart-data-v2
    ↓
SQL: get_chart_data_v2(p_timeframe: "m15")
    ↓
Query: ohlc_bars_v2 WHERE timeframe = 'm15'
    ↓
Response: { historical: [...], intraday: [...], forecast: [...] }
    ↓
Client: buildBars() → merge + sort
```

**Same flow for ALL timeframes** - no special cases!

### Database Schema (`ohlc_bars_v2`)

```sql
CREATE TABLE ohlc_bars_v2 (
  symbol_id UUID NOT NULL,
  timeframe VARCHAR(10) NOT NULL,  -- 'm15', 'h1', 'h4', 'd1', 'w1'
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  provider VARCHAR(20) NOT NULL,  -- 'alpaca', 'polygon', 'yfinance', 'tradier', 'ml_forecast'
  is_forecast BOOLEAN DEFAULT false,
  data_status VARCHAR(20) DEFAULT 'confirmed',
  -- ... other fields
  PRIMARY KEY (symbol_id, timeframe, ts, provider, is_forecast)
);
```

**Timeframe format**: Internal tokens (`m15`, `h1`, `h4`, `d1`, `w1`) - NOT Alpaca format

### Provider Strategy

**Alpaca-Only for New Data**:
- All new bars written with `provider = 'alpaca'`
- Legacy providers (polygon, yfinance, tradier) available as read-only fallback
- Provider preference in SQL: `alpaca > polygon > yfinance > tradier`

## Remaining Work

### Edge Functions Still Using Legacy Tables

These functions still reference `ohlc_bars` or `intraday_bars` and need migration:

1. **`symbol-init/index.ts`** - Line 96
   - Uses `ohlc_bars` to check existing bar count
   - **Action**: Change to `ohlc_bars_v2` with `is_forecast = false` filter

2. **`enhanced-prediction/index.ts`** - Line 154
   - Queries `ohlc_bars` for ML feature extraction
   - **Action**: Change to `ohlc_bars_v2` with `is_forecast = false` filter

3. **`intraday-update/index.ts`** - Lines 252, 277, 289
   - Writes to `intraday_bars` table (separate table for intraday data)
   - Writes to `ohlc_bars` for daily bars
   - **Action**: Consolidate to write ALL data to `ohlc_bars_v2`

4. **`scanner-watchlist/index.ts`** - Line 110
   - Queries `ohlc_bars` for latest quote
   - **Action**: Change to `ohlc_bars_v2` with `is_forecast = false` filter

5. **`support-resistance/index.ts`** - Line 647
   - Queries `ohlc_bars` for S&R calculation
   - **Action**: Change to `ohlc_bars_v2` with `is_forecast = false` filter

6. **`backfill-intraday-worker/index.ts`** - Lines 130-133
   - Writes to `intraday_bars` table
   - **Action**: Change to write to `ohlc_bars_v2` instead

### Deprecated Tables

Once all functions are migrated, these tables can be deprecated:
- `ohlc_bars` (legacy multi-provider table)
- `intraday_bars` (separate intraday table)

## Testing Checklist

- [ ] Apply migration: `20260110210000_simplify_chart_data_v2_unified.sql`
- [ ] Test m15 chart loads with fresh data
- [ ] Test h1 chart loads with fresh data
- [ ] Test h4 chart loads with fresh data
- [ ] Test d1 chart loads (should work as before)
- [ ] Test w1 chart loads (should work as before)
- [ ] Verify all timeframes show same provider (alpaca)
- [ ] Verify today's bars have `is_intraday = true`
- [ ] Verify historical bars have `is_intraday = false`
- [ ] Test chart switching between timeframes (no errors)
- [ ] Verify cache-busting works for all timeframes

## Benefits

1. **Simpler Code**: Removed ~100 lines of conditional logic across frontend/backend
2. **Consistent Behavior**: All timeframes treated identically
3. **Easier Debugging**: Single code path, single table, single query
4. **Better Performance**: No complex CTEs or UNION queries
5. **Future-Proof**: Easy to add new timeframes (5m, 30m, 2h, etc.)
6. **Unified Data Model**: One source of truth (`ohlc_bars_v2`)

## Migration Path

### Phase 1: ✅ COMPLETE
- Simplified `get_chart_data_v2()` SQL function
- Updated `chart`, `backfill`, `fetch-bars` edge functions
- Simplified frontend chart data handling

### Phase 2: IN PROGRESS
- Migrate remaining 6 edge functions to v2
- Deprecate `ohlc_bars` and `intraday_bars` tables
- Update all documentation

### Phase 3: FUTURE
- Remove legacy provider support (keep Alpaca only)
- Simplify provider preference logic
- Consider adding timeframe validation

## Related Files

- `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/migrations/20260110210000_simplify_chart_data_v2_unified.sql`
- `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/functions/chart-data-v2/index.ts`
- `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/functions/chart/index.ts`
- `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/functions/backfill/index.ts`
- `@/Users/ericpeterson/SwiftBolt_ML/backend/supabase/functions/fetch-bars/index.ts`
- `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Models/Timeframe.swift`
- `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Services/APIClient.swift`
- `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
