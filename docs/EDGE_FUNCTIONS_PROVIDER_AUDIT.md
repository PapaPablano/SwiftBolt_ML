# Edge Functions Provider Audit - Comprehensive Sweep

**Date**: 2026-01-10  
**Issue**: 1hr chart still showing old data despite backfill

## 🚨 Critical Findings

### Sweep 1: Deprecated Provider References

#### **HIGH PRIORITY - Active Data Fetching**

1. **`backfill/index.ts`** - Line 112
   - Uses `YFinanceClient` for backfills
   - Status: ❌ ACTIVE
   - Impact: Writes `provider='yfinance'` data
   - Action: Migrate to Alpaca or disable

2. **`symbol-backfill/index.ts`** 
   - Uses Yahoo Finance API directly
   - Status: ❌ ACTIVE (from earlier audit)
   - Impact: Writes `provider='yfinance'` data
   - Action: Migrate to Alpaca

3. **`backfill-intraday-worker/index.ts`** - Lines 76, 202-242
   - Uses `fetchPolygonIntraday()` function
   - Status: ❌ ACTIVE
   - Impact: Writes `provider='polygon'` intraday data
   - Action: Migrate to Alpaca or disable

4. **`_shared/intraday-service-v2.ts`** - Lines 6, 97-182
   - Uses `fetchTradierBars()` for intraday updates
   - Writes with `provider='tradier'`
   - Status: ❌ ACTIVE
   - Impact: May be called by other functions
   - Action: Migrate to Alpaca

5. **`refresh-data/index.ts`**
   - Uses YFinance (from earlier audit)
   - Status: ❌ ACTIVE
   - Action: Migrate to Alpaca

#### **MEDIUM PRIORITY - Provider Infrastructure**

6. **`_shared/providers/factory.ts`** - Lines 8-9, 68-74, 107-113
   - Creates `MassiveClient` (Polygon wrapper)
   - Creates `TradierClient`
   - Status: ⚠️ Infrastructure still exists
   - Impact: Other functions can use these clients
   - Action: Remove or deprecate client creation

7. **`_shared/providers/router.ts`** - Line 128
   - References `tradierProvider` in routing logic
   - Status: ⚠️ May route to Tradier
   - Action: Verify routing prioritizes Alpaca

8. **`_shared/providers/types.ts`** - Line 4
   - Defines `ProviderId` including deprecated providers
   - Type: `"finnhub" | "massive" | "yahoo" | "alpaca" | "tradier"`
   - Status: ⚠️ Type system allows deprecated providers
   - Action: Update type to Alpaca-only

9. **`_shared/data-validation.ts`** - Lines 40-93, 279-283
   - Validation rules for `PolygonHistoricalRule`
   - Validation rules for `TradierIntradayRule`
   - Validation rules for `YFinanceHistoricalRule`
   - Status: ⚠️ Still validates deprecated providers
   - Action: Remove or mark as legacy-only

#### **LOW PRIORITY - Helper Functions**

10. **`_shared/services/bar-fetcher.ts`** - Lines 6, 70-73, 121-125
    - References `MassiveClient` for resampling
    - Function: `getMassiveClientFromRouter()`
    - Status: ⚠️ Infrastructure for Polygon
    - Action: Migrate to Alpaca-based resampling

### Sweep 2: Functions That Write OHLC Data

Functions that INSERT/UPDATE `ohlc_bars_v2`:

1. ❌ `backfill/index.ts` - YFinance
2. ❌ `symbol-backfill/index.ts` - YFinance  
3. ❌ `backfill-intraday-worker/index.ts` - Polygon
4. ❌ `_shared/intraday-service-v2.ts` - Tradier
5. ❌ `refresh-data/index.ts` - YFinance
6. ✅ `chart-data-v2/index.ts` - Uses database function (Alpaca)
7. ✅ `symbol-init/index.ts` - Calls chart-data-v2 (Alpaca)

### Sweep 3: Provider Router Analysis

**`_shared/providers/router.ts`** routing logic:
```typescript
const alpacaProvider = this.providers.get("alpaca");
const tradierProvider = this.providers.get("tradier");  // ❌ Still references Tradier

let primary: ProviderId;
let fallback: ProviderId | undefined;
```

**Issue**: Router may still route to Tradier as fallback for intraday data.

### Sweep 4: Database Query Patterns

**No hardcoded provider filters found** in edge functions (good!).
All queries use database function `get_chart_data_v2` which handles provider logic.

## 🎯 Root Cause Analysis

### Why 1hr Chart Still Shows Old Data

1. **`_shared/intraday-service-v2.ts`** is actively writing Tradier data
   - This service may be called by scheduled jobs or other functions
   - Writes with `provider='tradier'` for intraday timeframes (m15, h1, h4)

2. **Provider Router** may fallback to Tradier
   - Even if Alpaca is primary, router has Tradier as fallback
   - If Alpaca fails or is unavailable, Tradier data is used

3. **Multiple backfill functions** can overwrite Alpaca data
   - `backfill/index.ts` (YFinance)
   - `symbol-backfill/index.ts` (YFinance)
   - `backfill-intraday-worker/index.ts` (Polygon)

## 📋 Action Plan

### Phase 1: Immediate (Stop Data Corruption)

1. **Disable intraday-service-v2** Tradier writes
   - [ ] Comment out Tradier fetch in `_shared/intraday-service-v2.ts`
   - [ ] Or migrate to Alpaca API

2. **Update Provider Router** to Alpaca-only
   - [ ] Remove Tradier fallback from `_shared/providers/router.ts`
   - [ ] Ensure Alpaca is only provider for intraday

3. **Disable deprecated backfill functions**
   - [ ] Add runtime checks to reject deprecated provider usage
   - [ ] Or migrate all to Alpaca

### Phase 2: Migration

1. **Migrate intraday-service-v2** to Alpaca
   - Replace `fetchTradierBars()` with Alpaca API
   - Update provider to `'alpaca'`

2. **Migrate backfill functions** to Alpaca
   - `backfill/index.ts`
   - `symbol-backfill/index.ts`
   - `backfill-intraday-worker/index.ts`

3. **Update provider infrastructure**
   - Remove Tradier/Polygon client creation from factory
   - Update types to Alpaca-only
   - Remove deprecated validation rules

### Phase 3: Cleanup

1. **Delete deprecated client files**
   - `_shared/providers/tradier-client.ts`
   - `_shared/providers/massive-client.ts`
   - `_shared/providers/yfinance-client.ts`

2. **Remove deprecated validation rules**
   - `PolygonHistoricalRule`
   - `TradierIntradayRule`
   - `YFinanceHistoricalRule`

## 🔍 Verification

After fixes, verify:

```sql
-- No new writes with deprecated providers in last hour
SELECT provider, COUNT(*), MAX(created_at)
FROM ohlc_bars_v2
WHERE provider IN ('yfinance', 'tradier', 'polygon')
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY provider;

-- Should return 0 rows
```

## Summary

**Total Issues Found**: 10 edge functions/modules using deprecated providers  
**Critical**: 5 functions actively writing deprecated provider data  
**Root Cause**: `intraday-service-v2.ts` writing Tradier data for h1 timeframe  
**Solution**: Migrate all to Alpaca or disable deprecated functions
