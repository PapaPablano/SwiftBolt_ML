# Deprecated Providers Audit & Cleanup

**Date**: 2026-01-10  
**Status**: ⚠️ CRITICAL - Multiple systems using deprecated providers

## Executive Summary

The Alpaca-only migration (20260110120000) established Alpaca as the sole provider for new OHLCV data. However, multiple GitHub Actions, Python scripts, and Edge Functions are still using deprecated providers (YFinance, Tradier, Polygon), causing data conflicts.

## Deprecated Providers

| Provider | Status | Last Valid Use | Notes |
|----------|--------|----------------|-------|
| `yfinance` | ❌ DEPRECATED | Read-only legacy | Free but unreliable, rate-limited |
| `tradier` | ❌ DEPRECATED | Read-only legacy | Requires brokerage account |
| `polygon` | ❌ DEPRECATED | Read-only legacy | Expensive, replaced by Alpaca |
| `alpaca` | ✅ ACTIVE | Primary provider | Free tier, reliable, real-time |

## Issues Found

### 🚨 GitHub Actions (High Priority)

#### 1. `backfill-ohlc.yml` - ACTIVE, NEEDS DISABLE
- **Status**: ❌ Still active on workflow_dispatch
- **Provider**: YFinance
- **Impact**: Overwrites Alpaca data with YFinance data
- **Lines**: 56, 72, 76
- **Action**: Disable or migrate to Alpaca

#### 2. `daily-historical-sync.yml` - DISABLED ✅
- **Status**: ✅ Schedule disabled (2026-01-10)
- **Provider**: YFinance
- **Note**: Can still be manually triggered

#### 3. `intraday-update-v2.yml` - DISABLED ✅
- **Status**: ✅ Schedule disabled (2026-01-10)
- **Provider**: Tradier
- **Note**: Can still be manually triggered

### 🔧 Python Scripts (Medium Priority)

#### 1. `ml/src/scripts/backfill_ohlc_yfinance.py`
- **Provider**: YFinance
- **Used by**: backfill-ohlc.yml, daily-historical-sync.yml
- **Action**: Deprecate or migrate to Alpaca

#### 2. `ml/src/data/tradier_client.py`
- **Provider**: Tradier
- **Used by**: options_historical_backfill.py, intraday services
- **Note**: Still needed for options data (not OHLCV)
- **Action**: Keep for options, remove OHLCV methods

#### 3. `ml/src/services/forecast_service_v2.py`
- **Lines**: 176, 196
- **Issue**: Hardcoded queries for `provider='tradier'` and `provider='polygon'`
- **Action**: Update to use Alpaca or remove provider filters

#### 4. `ml/src/scripts/backfill_ohlc.py`
- **Line**: 273
- **Issue**: Sets `provider='massive'` (Polygon wrapper)
- **Action**: Update to use Alpaca

### 🌐 Edge Functions (Medium Priority)

#### 1. `symbol-backfill/index.ts`
- **Lines**: 11, 67, 240
- **Provider**: YFinance
- **Impact**: Backfills use YFinance instead of Alpaca
- **Action**: Migrate to Alpaca API

#### 2. `orchestrator/index.ts`
- **Line**: 204-205
- **Issue**: Comments reference Polygon/Tradier routing
- **Action**: Update comments, verify uses Alpaca

#### 3. `backfill-intraday-worker/index.ts`
- **Lines**: 7, 25, 40-46, 76, 127, 200-258
- **Provider**: Polygon
- **Impact**: Intraday backfills use Polygon
- **Action**: Migrate to Alpaca or disable

#### 4. `refresh-data/index.ts`
- **Line**: 195
- **Provider**: YFinance
- **Action**: Migrate to Alpaca

#### 5. `options-scrape/index.ts`
- **Provider**: Tradier
- **Note**: ✅ OK - Tradier is still valid for options data (not OHLCV)
- **Action**: No change needed

#### 6. `_shared/massive-client.ts`
- **Lines**: 1-2
- **Provider**: Polygon wrapper
- **Action**: Deprecate or migrate to Alpaca

## Recommended Actions

### Phase 1: Immediate (Prevent Data Corruption)

1. ✅ **DONE**: Disable scheduled GitHub Actions
   - daily-historical-sync.yml
   - intraday-update-v2.yml
   - orchestrator-cron.yml

2. **TODO**: Disable remaining active workflows
   - [ ] backfill-ohlc.yml

3. **TODO**: Add warnings to deprecated scripts
   - [ ] Add deprecation notices to Python scripts
   - [ ] Add runtime warnings when deprecated providers are used

### Phase 2: Migration (Replace with Alpaca)

1. **TODO**: Create Alpaca-based replacements
   - [ ] Create `backfill_ohlc_alpaca.py` to replace YFinance script
   - [ ] Update `symbol-backfill` edge function to use Alpaca
   - [ ] Update `refresh-data` edge function to use Alpaca

2. **TODO**: Update forecast service
   - [ ] Remove hardcoded provider filters in forecast_service_v2.py
   - [ ] Query Alpaca data instead of Tradier/Polygon

3. **TODO**: Update edge functions
   - [ ] Migrate backfill-intraday-worker to Alpaca
   - [ ] Update orchestrator comments and logic

### Phase 3: Cleanup (Remove Legacy Code)

1. **TODO**: Archive deprecated code
   - [ ] Move YFinance scripts to `deprecated/` folder
   - [ ] Move Tradier OHLCV methods to `deprecated/`
   - [ ] Keep Tradier options methods (still valid)

2. **TODO**: Update documentation
   - [ ] Update README with Alpaca-only strategy
   - [ ] Document migration process
   - [ ] Update API documentation

## Testing Checklist

After migration, verify:

- [ ] All watchlist symbols load current data (within 24h)
- [ ] Charts display data from January 2026 (not June 2025)
- [ ] No new data written with `provider IN ('yfinance', 'tradier', 'polygon')`
- [ ] ML forecasts use Alpaca historical data
- [ ] Options scraping still works (Tradier is OK for options)

## SQL Verification Queries

```sql
-- Check for new writes with deprecated providers (should be 0)
SELECT provider, COUNT(*), MAX(created_at)
FROM ohlc_bars_v2
WHERE provider IN ('yfinance', 'tradier', 'polygon')
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY provider;

-- Verify Alpaca is primary provider for recent data
SELECT provider, COUNT(*), MAX(ts) as latest_bar
FROM ohlc_bars_v2
WHERE ts >= NOW() - INTERVAL '7 days'
GROUP BY provider
ORDER BY COUNT(*) DESC;
```

## Notes

- **Options data**: Tradier is still the primary provider for options chains. This is OK.
- **Legacy data**: Old Polygon/YFinance data can remain for historical analysis
- **Read-only**: Deprecated providers can still be read from database, just no new writes

## References

- Migration SQL: `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`
- Alpaca docs: https://alpaca.markets/docs/
- Database constraints: `ohlc_bars_v2_provider_check`
