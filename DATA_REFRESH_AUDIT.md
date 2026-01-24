# Data Refresh & Edge Functions Audit

**Date**: 2026-01-23  
**Issue**: MU (Micron) data not current  
**Scope**: Edge functions, refresh rates, and data ingestion workflows

---

## Executive Summary

The data refresh system uses multiple layers:
1. **Scheduled GitHub Actions** for bulk OHLC updates (every 15 min during market hours)
2. **Edge Functions** for on-demand quotes and user-triggered refreshes
3. **Watchlist-based symbol selection** for automated processing

**Key Finding**: MU data staleness likely due to:
- MU may not be in watchlist (only watchlist symbols are auto-refreshed)
- Quotes edge function is real-time but OHLC data depends on scheduled jobs
- No automatic refresh for non-watchlist symbols during market hours

---

## 1. Edge Functions Audit

### 1.1 Quotes Edge Function (`quotes/index.ts`)

**Status**: ✅ **WORKING CORRECTLY**

- **Purpose**: Real-time quotes from Alpaca snapshots API
- **Refresh Rate**: On-demand (no caching, always fresh)
- **Data Source**: Alpaca `/v2/stocks/snapshots` endpoint
- **Cache Headers**: `no-cache, no-store, must-revalidate`
- **Limitations**: 
  - Only fetches quotes, not OHLC bars
  - Requires symbols to be passed in request
  - Max batch size: 50 symbols

**Recommendation**: ✅ No changes needed - this is working as designed

---

### 1.2 User Refresh Edge Function (`user-refresh/index.ts`)

**Status**: ✅ **COMPREHENSIVE BUT MANUAL**

- **Purpose**: Orchestrates all data updates for a symbol
- **Steps**:
  1. Checks if backfill needed (< 100 d1 bars)
  2. Fetches latest OHLC bars from Alpaca (d1, h1, h4, m15)
  3. Queues ML forecast job
  4. Queues options ranking job
  5. Calculates support/resistance levels
- **Refresh Rate**: Manual trigger only
- **Data Source**: Alpaca via `getProviderRouter()`

**Issues**:
- ⚠️ **Manual trigger only** - not automatically called for watchlist symbols
- ⚠️ **No automatic refresh** during market hours for non-watchlist symbols
- ✅ Fetches all timeframes (d1, h1, h4, m15) when triggered

**Recommendation**: 
- Consider adding a scheduled job that calls `user-refresh` for watchlist symbols every 15-30 minutes during market hours
- Or enhance `intraday-ingestion.yml` to also update quotes table

---

### 1.3 Chart Data V2 Edge Function

**Status**: ⚠️ **NOT FOUND IN CURRENT CODEBASE**

- **Expected Location**: `supabase/functions/chart-data-v2/index.ts`
- **Issue**: File not found in search results
- **Impact**: Unknown - may be using database functions directly

**Recommendation**: 
- Verify if this function exists or if chart data comes directly from database
- Check `client-macos/SwiftBoltML/Services/APIClient.swift` for `fetchChartV2()` implementation

---

## 2. Scheduled Refresh Mechanisms

### 2.1 Intraday Ingestion Workflow (`.github/workflows/intraday-ingestion.yml`)

**Status**: ✅ **ACTIVE AND WORKING**

- **Schedule**: Every 15 minutes during market hours (9:00 AM - 5:00 PM ET)
- **Cron**: `*/15 13-22 * * 1-5` (UTC)
- **Symbol Selection**: 
  - Uses `resolve_universe.py` → `universe_utils.py`
  - **Fetches from watchlist** via `get_all_watchlist_symbols` RPC
  - Falls back to DEFAULT_SYMBOLS if no watchlist
- **Timeframes**: m15, h1 (default)
- **Script**: `alpaca_backfill_ohlc_v2.py`
- **Data Written**: `ohlc_bars_v2` table with `provider='alpaca'`

**Critical Finding**: 
- ⚠️ **Only processes watchlist symbols**
- ⚠️ **If MU is not in watchlist, it won't be refreshed automatically**
- ✅ Updates OHLC bars but **does not update quotes table**

**Recommendation**:
1. Verify MU is in watchlist: Check `watchlist_items` table
2. If not in watchlist, add it or use manual refresh
3. Consider adding quotes table update to this workflow

---

### 2.2 Daily Data Refresh Workflow (`.github/workflows/daily-data-refresh.yml`)

**Status**: ✅ **ACTIVE**

- **Schedule**: Daily at 6:00 AM UTC (12:00 AM CST)
- **Purpose**: Incremental refresh for all timeframes
- **Symbol Selection**: Same as intraday (watchlist → defaults)
- **Timeframes**: m15, h1, h4, d1, w1

**Issue**: 
- ⚠️ Only runs once per day
- ⚠️ Won't catch intraday updates during market hours

---

## 3. Symbol Selection Logic

### 3.1 Universe Resolution (`ml/src/scripts/universe_utils.py`)

**Flow**:
1. Check `INPUT_SYMBOLS` environment variable (manual override)
2. Fetch from watchlist via `get_all_watchlist_symbols` RPC
3. Fall back to `DEFAULT_FALLBACK_SYMBOLS` if no watchlist

**DEFAULT_FALLBACK_SYMBOLS**:
```python
["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ"]
```

**Critical Finding**:
- ⚠️ **MU is NOT in default fallback list**
- ⚠️ **MU must be in watchlist to be auto-refreshed**
- ✅ Watchlist symbols are fetched via `watchlist_items` table join

**Recommendation**:
1. **Immediate**: Check if MU is in watchlist
   ```sql
   SELECT wi.*, s.ticker 
   FROM watchlist_items wi
   JOIN symbols s ON s.id = wi.symbol_id
   WHERE s.ticker = 'MU';
   ```

2. **If MU is not in watchlist**: Add it or use manual refresh via `user-refresh` edge function

3. **Long-term**: Consider adding a "priority symbols" list that always gets refreshed regardless of watchlist

---

## 4. Quotes vs OHLC Data

### 4.1 Quotes Table

**Refresh Mechanism**:
- ✅ Real-time via `quotes` edge function (on-demand)
- ❌ No automatic scheduled refresh
- ⚠️ **Not updated by intraday-ingestion workflow**

**Data Source**: Alpaca snapshots API (real-time)

**Issue**: 
- Quotes are separate from OHLC bars
- Quotes table may be stale if not explicitly refreshed
- App may be showing stale quotes for MU

---

### 4.2 OHLC Bars Table

**Refresh Mechanism**:
- ✅ Scheduled every 15 min during market hours (intraday-ingestion)
- ✅ Daily refresh at 6 AM UTC (daily-data-refresh)
- ✅ Manual refresh via `user-refresh` edge function

**Data Source**: Alpaca historical bars API

**Status**: ✅ Working correctly for watchlist symbols

---

## 5. Root Cause Analysis for MU Data Staleness

### Likely Causes (in order of probability):

1. **MU not in watchlist** (HIGH PROBABILITY)
   - Intraday ingestion only processes watchlist symbols
   - MU not in DEFAULT_FALLBACK_SYMBOLS
   - Result: No automatic refresh during market hours

2. **Quotes table not updated** (MEDIUM PROBABILITY)
   - Quotes edge function is on-demand only
   - No scheduled job updates quotes table
   - App may be showing stale quotes

3. **Market hours timing** (LOW PROBABILITY)
   - Intraday ingestion only runs during market hours
   - If checked outside market hours, data may appear stale
   - But this should affect all symbols equally

---

## 6. Recommendations

### Immediate Actions

1. **Verify MU in Watchlist**
   ```sql
   -- Check if MU is in watchlist
   SELECT wi.*, s.ticker 
   FROM watchlist_items wi
   JOIN symbols s ON s.id = wi.symbol_id
   WHERE s.ticker = 'MU';
   ```

2. **Manual Refresh for MU** (if not in watchlist)
   - Use `user-refresh` edge function:
     ```bash
     curl -X POST https://<supabase-url>/functions/v1/user-refresh \
       -H "Authorization: Bearer <token>" \
       -H "Content-Type: application/json" \
       -d '{"symbol": "MU"}'
     ```

3. **Add MU to Watchlist** (if missing)
   - Use watchlist-sync edge function or add via UI

---

### Short-Term Improvements

1. **Add Quotes Table Refresh to Intraday Ingestion**
   - Modify `intraday-ingestion.yml` to also call `quotes` edge function
   - Or add quotes update to `alpaca_backfill_ohlc_v2.py`

2. **Enhance User-Refresh to be Scheduled**
   - Create a new scheduled job that calls `user-refresh` for watchlist symbols
   - Run every 15-30 minutes during market hours
   - This would ensure quotes + OHLC + forecasts are all updated

3. **Add Priority Symbols List**
   - Create a `priority_symbols` table or config
   - Always refresh these symbols regardless of watchlist status
   - Include high-volume symbols like MU

---

### Long-Term Improvements

1. **Unified Refresh Service**
   - Create a single edge function that handles:
     - OHLC bars (all timeframes)
     - Quotes (real-time)
     - Forecasts (queued)
     - Options rankings (queued)
   - Replace multiple separate refresh mechanisms

2. **Symbol Refresh Priority System**
   - Tier 1: Watchlist symbols (refresh every 15 min)
   - Tier 2: Priority symbols (refresh every 30 min)
   - Tier 3: Default symbols (refresh daily)

3. **Data Freshness Monitoring**
   - Add alerts when data is stale (> 30 min old during market hours)
   - Dashboard showing refresh status per symbol
   - Automatic retry for failed refreshes

---

## 7. Testing & Verification

### Verify MU Data Freshness

1. **Check OHLC Bars**:
   ```sql
   SELECT ts, open, high, low, close, volume, provider
   FROM ohlc_bars_v2
   WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'MU')
     AND timeframe = 'm15'
     AND is_forecast = false
   ORDER BY ts DESC
   LIMIT 10;
   ```

2. **Check Quotes**:
   ```sql
   SELECT * FROM quotes
   WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'MU')
   ORDER BY updated_at DESC
   LIMIT 1;
   ```

3. **Check Last Refresh Time**:
   - Look at GitHub Actions runs for `intraday-ingestion.yml`
   - Check if MU was included in the symbol list
   - Verify bars were inserted in the last run

---

## 8. Summary

**Current State**:
- ✅ OHLC bars refresh every 15 min for watchlist symbols
- ✅ Quotes available on-demand via edge function
- ⚠️ MU likely not in watchlist → no automatic refresh
- ⚠️ Quotes table not automatically updated
- ✅ **NEW**: Multi-leg strategy symbols automatically queue options ranking jobs (migration: `20260123000000_multi_leg_options_ranking_trigger.sql`)

**Immediate Fix**:
1. Add MU to watchlist OR
2. Manually trigger `user-refresh` for MU
3. **NEW**: Create a multi-leg strategy on MU → automatically queues options ranking

**Long-Term Fix**:
1. Add quotes refresh to scheduled jobs
2. Create priority symbols list
3. Unified refresh service
4. ✅ **COMPLETED**: Multi-leg strategy symbols auto-queue options ranking

---

## Appendix: Edge Functions Reference

| Function | Purpose | Refresh Rate | Status |
|----------|---------|--------------|--------|
| `quotes` | Real-time quotes | On-demand | ✅ Working |
| `user-refresh` | Comprehensive refresh | Manual | ✅ Working |
| `chart-data-v2` | Chart data | Unknown | ⚠️ Not found |
| `watchlist-sync` | Watchlist management | On-demand | ✅ Working |

---

## Appendix: Scheduled Jobs Reference

| Job | Schedule | Symbols | Timeframes | Status |
|-----|----------|---------|------------|--------|
| `intraday-ingestion` | Every 15 min (market hours) | Watchlist | m15, h1 | ✅ Active |
| `daily-data-refresh` | Daily 6 AM UTC | Watchlist | All | ✅ Active |

---

**Next Steps**:
1. ✅ **COMPLETED**: Create trigger to auto-queue options ranking for multi-leg strategy symbols
2. Verify MU watchlist status
3. Add MU to watchlist if missing (or create multi-leg strategy on MU)
4. Test manual refresh via `user-refresh`
5. Monitor data freshness for 24 hours
6. Implement quotes refresh in scheduled jobs

---

## 9. Multi-Leg Strategy Options Ranking Integration

### 9.1 New Feature: Auto-Queue Options Ranking

**Migration**: `20260123000000_multi_leg_options_ranking_trigger.sql`

**Problem Solved**: 
- Multi-leg strategies require current options data for P&L calculations
- Previously, symbols used in multi-leg strategies weren't automatically added to options ranking refresh
- Users had to manually add symbols to watchlist or trigger ranking jobs

**Solution**:
- **Trigger on Strategy Create**: When a new multi-leg strategy is created with status='open', automatically queue an options ranking job for the underlying symbol
- **Trigger on Strategy Reopen**: When a closed/expired strategy is reopened, queue ranking job
- **Helper Functions**: 
  - `get_multi_leg_strategy_symbols()` - Get all symbols with active strategies
  - `queue_multi_leg_strategy_ranking_jobs()` - Queue ranking for all active multi-leg symbols

**Benefits**:
- ✅ Automatic options data refresh for multi-leg strategy symbols
- ✅ No need to manually add symbols to watchlist
- ✅ Ensures options data is current for P&L calculations
- ✅ Works even if symbol is not in watchlist

**Usage**:
1. Create a multi-leg strategy on any symbol (e.g., MU)
2. Options ranking job is automatically queued
3. Options data will be refreshed within the next ranking job cycle
4. Multi-leg strategy evaluation will have current options prices

**Integration with Existing Systems**:
- Uses existing `queue_ranking_job()` function
- Respects existing job deduplication (won't queue if job already pending/running)
- Priority 2 (higher than watchlist default priority 1)
- Can be called by scheduled jobs via `queue_multi_leg_strategy_ranking_jobs()`
