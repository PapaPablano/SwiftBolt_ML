# JavaScript/TypeScript V2 Migration Audit

## Executive Summary

Comprehensive audit of all JavaScript/TypeScript files for v2 migration. Found **15 files** using legacy tables that need migration.

## Web Chart Applications - ✅ NO MIGRATION NEEDED

### `chart.js` (WebChart Component)
**Location**: `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Resources/WebChart/chart.js`

**Status**: ✅ **V2 COMPATIBLE - NO CHANGES NEEDED**

**Analysis**:
- Pure client-side JavaScript for TradingView Lightweight Charts
- Does NOT make direct database calls
- Receives data from Swift via `evaluateJavaScript`
- Data format is provider-agnostic (just OHLC + time)
- Works with ANY backend data structure

**Data Flow**:
```
Swift (ChartViewModel) 
    ↓ fetchChartV2()
Edge Function (chart-data-v2)
    ↓ get_chart_data_v2()
ohlc_bars_v2 table
    ↓ JSON response
Swift processes layers
    ↓ evaluateJavaScript
chart.js renders
```

**Key Methods**:
- `setCandles(data)` - Receives OHLC array, no table dependency
- `updateLiveBar(bar)` - Updates single bar, no table dependency
- `addIndicator()` - Client-side calculations only

**Conclusion**: Web chart is **already v2 compatible** because it's decoupled from database layer.

---

## Edge Functions - MIGRATION REQUIRED

### Priority 1: Critical (User-Facing)

#### 1. `symbol-backfill/index.ts` ❌
**Lines**: 113, 126, 194
**Issue**: Uses `ohlc_bars` table
**Impact**: HIGH - Backfill system won't populate v2 table
**Migration**:
```typescript
// BEFORE
.from("ohlc_bars")

// AFTER
.from("ohlc_bars_v2")
.eq("is_forecast", false)

// Add to inserts
provider: "yfinance",
is_forecast: false,
data_status: "confirmed"
```

#### 2. `user-refresh/index.ts` ❌
**Lines**: 127, 197, 230, 327
**Issue**: Uses `ohlc_bars` table
**Impact**: HIGH - User refresh won't update v2 table
**Migration**: Same as above

#### 3. `symbol-init/index.ts` ❌
**Lines**: 96
**Issue**: Uses `ohlc_bars` table
**Impact**: MEDIUM - Symbol initialization check
**Migration**: Same as above

### Priority 2: Data Pipeline

#### 4. `backfill-intraday-worker/index.ts` ❌
**Lines**: 3, 8, 130-133
**Issue**: Uses `intraday_bars` table (separate table)
**Impact**: HIGH - Intraday backfill writes to wrong table
**Migration**:
```typescript
// BEFORE
.from('intraday_bars')
.upsert(barsToInsert, {
  onConflict: 'symbol_id,timeframe,ts'
})

// AFTER
.from('ohlc_bars_v2')
.upsert(barsToInsert, {
  onConflict: 'symbol_id,timeframe,ts,provider,is_forecast'
})

// Add to inserts
provider: 'polygon',
is_forecast: false,
data_status: 'confirmed'
```

#### 5. `intraday-update/index.ts` ❌
**Lines**: 252, 277, 289
**Issue**: Uses both `intraday_bars` AND `ohlc_bars`
**Impact**: HIGH - Live intraday updates go to wrong tables
**Migration**: Consolidate ALL writes to `ohlc_bars_v2`

#### 6. `_shared/intraday-service-v2.ts` ❌
**Lines**: 225, 240
**Issue**: Uses `intraday_bars` table
**Impact**: MEDIUM - Shared service writes to wrong table
**Migration**: Same as above

### Priority 3: ML & Analytics

#### 7. `enhanced-prediction/index.ts` ❌
**Lines**: 154
**Issue**: Uses `ohlc_bars` table for ML features
**Impact**: MEDIUM - ML predictions use wrong data source
**Migration**: Change to `ohlc_bars_v2` with `is_forecast = false`

#### 8. `scanner-watchlist/index.ts` ❌
**Lines**: 110
**Issue**: Uses `ohlc_bars` for latest quote
**Impact**: LOW - Scanner uses stale data
**Migration**: Same as above

#### 9. `support-resistance/index.ts` ❌
**Lines**: 647
**Issue**: Uses `ohlc_bars` for S&R calculation
**Impact**: MEDIUM - S&R levels calculated from wrong data
**Migration**: Same as above

### Priority 4: Legacy Functions

#### 10. `apply-h1-fix/index.ts` ❌
**Lines**: 64, 98, 128
**Issue**: Uses `intraday_bars` for h1 aggregation
**Impact**: LOW - Legacy fix, may be obsolete
**Action**: Consider deprecating entirely (replaced by simplified get_chart_data_v2)

---

## Validation Scripts - MIGRATION RECOMMENDED

These are development/testing scripts, not production code. Lower priority but should be updated for consistency.

#### 11. `scripts/database/diagnose-db.js` ❌
**Lines**: 70, 73, 82
**Issue**: Checks `ohlc_bars` table
**Action**: Update to check `ohlc_bars_v2` for accurate diagnostics

#### 12. `scripts/validation/test_db_insert.ts` ❌
**Lines**: 40, 56
**Issue**: Tests insert to `ohlc_bars`
**Action**: Update to test `ohlc_bars_v2` inserts

#### 13. `scripts/validation/check_symbols.ts` ❌
**Lines**: 12, 17
**Issue**: Counts bars in `ohlc_bars`
**Action**: Update to count `ohlc_bars_v2`

#### 14. `scripts/validation/check_data.ts` ❌
**Lines**: 20, 29, 37, 49
**Issue**: Queries `ohlc_bars`
**Action**: Update to query `ohlc_bars_v2`

#### 15. `scripts/validation/cleanup_future_data.ts` ❌
**Lines**: 15, 31
**Issue**: Deletes from `ohlc_bars`
**Action**: Update to delete from `ohlc_bars_v2`

#### 16. `scripts/validation/test_chart_query.ts` ❌
**Lines**: 29
**Issue**: Queries `ohlc_bars`
**Action**: Update to query `ohlc_bars_v2`

---

## Migration Priority Order

### Phase 1: Critical Path (Do First)
1. ✅ `chart-data-v2/index.ts` - Already using v2
2. ✅ `fetch-bars/index.ts` - Already using v2
3. ✅ `chart/index.ts` - Migrated
4. ✅ `backfill/index.ts` - Migrated
5. ❌ `symbol-backfill/index.ts` - **NEEDS MIGRATION**
6. ❌ `user-refresh/index.ts` - **NEEDS MIGRATION**

### Phase 2: Data Pipeline
7. ❌ `backfill-intraday-worker/index.ts` - **NEEDS MIGRATION**
8. ❌ `intraday-update/index.ts` - **NEEDS MIGRATION**
9. ❌ `_shared/intraday-service-v2.ts` - **NEEDS MIGRATION**

### Phase 3: Analytics
10. ❌ `enhanced-prediction/index.ts` - **NEEDS MIGRATION**
11. ❌ `scanner-watchlist/index.ts` - **NEEDS MIGRATION**
12. ❌ `support-resistance/index.ts` - **NEEDS MIGRATION**
13. ❌ `symbol-init/index.ts` - **NEEDS MIGRATION**

### Phase 4: Cleanup
14. ❌ All validation scripts - **UPDATE FOR CONSISTENCY**
15. ❌ `apply-h1-fix/index.ts` - **CONSIDER DEPRECATING**

---

## Standard Migration Pattern

### For `ohlc_bars` → `ohlc_bars_v2`

```typescript
// READ operations
const { data } = await supabase
  .from("ohlc_bars_v2")  // Changed from ohlc_bars
  .select("ts, open, high, low, close, volume")
  .eq("symbol_id", symbolId)
  .eq("timeframe", timeframe)
  .eq("is_forecast", false)  // NEW: Filter out forecasts
  .order("ts", { ascending: true });

// WRITE operations
const barsToInsert = bars.map(bar => ({
  symbol_id: symbolId,
  timeframe: timeframe,
  ts: bar.timestamp,
  open: bar.open,
  high: bar.high,
  low: bar.low,
  close: bar.close,
  volume: bar.volume,
  provider: "alpaca",           // NEW: Required
  is_forecast: false,           // NEW: Required
  data_status: "confirmed",     // NEW: Required
}));

const { error } = await supabase
  .from("ohlc_bars_v2")  // Changed from ohlc_bars
  .upsert(barsToInsert, {
    onConflict: "symbol_id,timeframe,ts,provider,is_forecast",  // NEW: Updated conflict key
    ignoreDuplicates: false,
  });
```

### For `intraday_bars` → `ohlc_bars_v2`

```typescript
// Same as above, but consolidate into ohlc_bars_v2
// No separate intraday_bars table needed with Alpaca

// Set is_intraday flag based on date
const today = new Date().toISOString().split('T')[0];
const barDate = new Date(bar.timestamp).toISOString().split('T')[0];
const is_intraday = barDate === today;

// But this is computed by SQL function, not stored
// Just write to ohlc_bars_v2 with provider/timeframe
```

---

## Testing Checklist

After each migration:

- [ ] Function deploys without errors
- [ ] Database writes succeed
- [ ] Data appears in `ohlc_bars_v2` table
- [ ] Charts load correctly with new data
- [ ] No duplicate data in legacy tables
- [ ] Logs show correct table usage

---

## Deprecation Plan

Once all functions migrated:

### Tables to Deprecate
1. `ohlc_bars` (legacy multi-provider table)
2. `intraday_bars` (separate intraday table)

### Migration SQL
```sql
-- After confirming all functions use v2
-- Optionally migrate old data
INSERT INTO ohlc_bars_v2 (
  symbol_id, timeframe, ts, open, high, low, close, volume,
  provider, is_forecast, data_status
)
SELECT 
  symbol_id, timeframe, ts, open, high, low, close, volume,
  COALESCE(provider, 'unknown') as provider,
  false as is_forecast,
  'confirmed' as data_status
FROM ohlc_bars
ON CONFLICT (symbol_id, timeframe, ts, provider, is_forecast) DO NOTHING;

-- Then drop old tables
DROP TABLE ohlc_bars CASCADE;
DROP TABLE intraday_bars CASCADE;
```

---

## Summary

- **Web Chart (chart.js)**: ✅ Already compatible, no changes needed
- **Edge Functions**: ❌ 10 functions need migration
- **Validation Scripts**: ❌ 6 scripts need updates
- **Total Files**: 16 files identified, 4 already migrated

**Next Action**: Migrate Priority 1 functions (`symbol-backfill`, `user-refresh`, `symbol-init`)
