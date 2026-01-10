# Data Flow Migration Plan: Polygon → Yahoo Finance

## Current State Analysis

### ✅ Completed
1. **Python Scripts**
   - Created `backfill_ohlc_yfinance.py` - Yahoo Finance backfill script
   - Backfilled all 7 watchlist symbols (3,500 bars)
   - Database now has clean Yahoo Finance data

2. **Database Layer**
   - Added 'yfinance' to allowed providers
   - Updated `get_chart_data_v2()` to prefer yfinance over polygon
   - Deleted corrupted Polygon data

3. **Swift Client**
   - All timestamp conversions fixed
   - Charts rendering correctly with Yahoo Finance data

### ⚠️ Needs Migration

#### 1. Edge Functions (Supabase)
**Location:** `/backend/supabase/functions/`

**Files to Update:**

**A. `symbol-backfill/index.ts`**
- **Current:** Uses Polygon API for deep backfill when symbol added to watchlist
- **Issue:** Still hardcoded to Polygon, marks data as `provider: "massive"`
- **Action Required:** 
  - Replace Polygon API calls with Yahoo Finance
  - Update provider tag to `"yfinance"`
  - Remove Polygon API key dependency
  - Update rate limiting (Yahoo Finance is free, no rate limits)

**B. `refresh-data/index.ts`**
- **Current:** Uses provider router, marks data as `provider: "massive"`
- **Issue:** Provider router may still route to Polygon for historical
- **Action Required:**
  - Update provider router to use Yahoo Finance for historical data
  - Keep Tradier for intraday (working well)
  - Update provider tag to `"yfinance"` for historical

**C. Provider Abstraction Layer**
**Location:** `/backend/supabase/functions/_shared/providers/`
- **Current:** Has Finnhub, Polygon (Massive), Tradier clients
- **Action Required:**
  - Create `yfinance-client.ts` - Yahoo Finance provider implementation
  - Update `factory.ts` to route historical requests to Yahoo Finance
  - Keep Tradier for intraday data

#### 2. GitHub Actions Workflows
**Location:** `/.github/workflows/`

**Files to Update:**

**A. `daily-historical-sync.yml`**
- **Current:** Runs `deep_backfill_ohlc_v2.py` with Polygon (MASSIVE_API_KEY)
- **Line 46:** `MASSIVE_API_KEY: ${{ secrets.MASSIVE_API_KEY }}`
- **Line 58:** Calls `deep_backfill_ohlc_v2.py` (Polygon script)
- **Action Required:**
  - Replace with `backfill_ohlc_yfinance.py`
  - Remove MASSIVE_API_KEY dependency
  - Remove rate limiting delays (Yahoo Finance is free)
  - Update to: `python src/scripts/backfill_ohlc_yfinance.py --all --days 730`

**B. `backfill-ohlc.yml`**
- **Current:** Runs `backfill_ohlc.py` with Polygon
- **Lines 53-54, 66-67:** Uses MASSIVE_API_KEY
- **Action Required:**
  - Update to use `backfill_ohlc_yfinance.py`
  - Remove MASSIVE_API_KEY from env vars
  - Simplify (no rate limiting needed)

**C. `symbol-backfill.yml`** (if exists)
- **Action Required:** Update to use Yahoo Finance script

#### 3. Python Scripts (Legacy)
**Location:** `/ml/src/scripts/`

**Files to Deprecate/Update:**

**A. `deep_backfill_ohlc_v2.py`**
- **Status:** Legacy Polygon script
- **Action:** Mark as deprecated, update docs to use `backfill_ohlc_yfinance.py`

**B. `process_backfill_queue.py`**
- **Status:** Uses Polygon API
- **Action:** Update to use Yahoo Finance or deprecate

**C. `backfill_ohlc.py`**
- **Status:** Generic backfill (may use Polygon)
- **Action:** Update to route to Yahoo Finance for historical

---

## Migration Steps

### Phase 1: Edge Functions (High Priority)
**Impact:** New symbols added to watchlist will still use Polygon

1. **Create Yahoo Finance Provider Client**
   ```typescript
   // /backend/supabase/functions/_shared/providers/yfinance-client.ts
   export class YFinanceClient implements DataProviderAbstraction {
     async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
       // Implement Yahoo Finance API calls
       // No API key needed (free)
       // No rate limiting needed
     }
   }
   ```

2. **Update Provider Factory**
   ```typescript
   // /backend/supabase/functions/_shared/providers/factory.ts
   export function getProviderRouter(): DataProviderRouter {
     return {
       historical: new YFinanceClient(),  // Changed from Polygon
       intraday: new TradierClient(),     // Keep Tradier
       news: new FinnhubClient()          // Keep Finnhub
     }
   }
   ```

3. **Update symbol-backfill/index.ts**
   - Replace `fetchPolygonBars()` with Yahoo Finance calls
   - Update provider tag: `provider: "yfinance"`
   - Remove rate limiting delays
   - Remove POLYGON_API_KEY dependency

4. **Update refresh-data/index.ts**
   - Change provider tag from `"massive"` to `"yfinance"`
   - Verify router uses Yahoo Finance for historical

### Phase 2: GitHub Actions (Medium Priority)
**Impact:** Automated daily syncs still use Polygon

1. **Update daily-historical-sync.yml**
   ```yaml
   - name: Sync historical data
     env:
       SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
       SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
       # MASSIVE_API_KEY removed - no longer needed
     run: |
       cd ml
       python src/scripts/backfill_ohlc_yfinance.py --all --days 730
   ```

2. **Update backfill-ohlc.yml**
   - Replace script calls with `backfill_ohlc_yfinance.py`
   - Remove MASSIVE_API_KEY from env
   - Remove rate limiting delays

3. **Test workflows**
   - Trigger manually via GitHub Actions UI
   - Verify data lands in database with `provider='yfinance'`

### Phase 3: Cleanup (Low Priority)
**Impact:** Code hygiene, documentation

1. **Deprecate old scripts**
   - Add deprecation notices to `deep_backfill_ohlc_v2.py`
   - Update README to point to `backfill_ohlc_yfinance.py`

2. **Remove Polygon dependencies**
   - Can remove MASSIVE_API_KEY from secrets (after testing)
   - Remove Polygon client code (optional, keep for reference)

3. **Update documentation**
   - Update data flow diagrams
   - Document Yahoo Finance as primary historical source
   - Document Tradier as intraday source

---

## Data Flow Architecture (After Migration)

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources                             │
├─────────────────────────────────────────────────────────────┤
│  Yahoo Finance (yfinance)  │  Tradier API  │  Finnhub API   │
│  - Historical (d1, w1)     │  - Intraday   │  - News        │
│  - FREE, no rate limits    │  - Real-time  │  - Sentiment   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Ingestion Layer                             │
├─────────────────────────────────────────────────────────────┤
│  Python Scripts:                                             │
│  - backfill_ohlc_yfinance.py (historical)                   │
│  - intraday scripts (Tradier)                               │
│                                                              │
│  Edge Functions:                                             │
│  - symbol-backfill (Yahoo Finance)                          │
│  - refresh-data (Yahoo Finance + Tradier)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Supabase Database                           │
├─────────────────────────────────────────────────────────────┤
│  ohlc_bars_v2 table:                                        │
│  - provider='yfinance' (historical, <today)                 │
│  - provider='tradier' (intraday, =today)                    │
│  - provider='ml_forecast' (forecasts, >today)               │
│                                                              │
│  get_chart_data_v2() function:                              │
│  - Prefers yfinance over polygon                            │
│  - Deduplicates by date                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  API Layer                                   │
├─────────────────────────────────────────────────────────────┤
│  Edge Function: chart-data-v2                               │
│  - Returns layered data (historical/intraday/forecast)      │
│  - Automatically selects yfinance for historical            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Swift macOS Client                          │
├─────────────────────────────────────────────────────────────┤
│  - Fetches from chart-data-v2                               │
│  - Renders with Lightweight Charts                          │
│  - SuperTrend AI with K-means clustering                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Benefits Summary

### Cost Savings
- **$200/month** saved (can cancel Polygon subscription)
- Yahoo Finance is completely free

### Data Quality
- ✅ No more corrupted bars with extreme ranges
- ✅ No more date anomalies (1933, 1937 errors)
- ✅ Reliable, clean historical data

### Operational
- ✅ No rate limiting delays needed
- ✅ Simpler codebase (one less provider)
- ✅ No API key management for historical data

### Performance
- ✅ Faster backfills (no rate limit waits)
- ✅ Can backfill all symbols in parallel

---

## Testing Checklist

### Database Layer ✅
- [x] Yahoo Finance data in database
- [x] `get_chart_data_v2()` returns yfinance data
- [x] Charts render correctly

### Python Scripts ✅
- [x] `backfill_ohlc_yfinance.py` works
- [x] All watchlist symbols backfilled
- [x] Data validation working

### Edge Functions ⏳
- [ ] Create YFinanceClient
- [ ] Update provider factory
- [ ] Update symbol-backfill function
- [ ] Update refresh-data function
- [ ] Test with new symbol addition

### GitHub Actions ⏳
- [ ] Update daily-historical-sync.yml
- [ ] Update backfill-ohlc.yml
- [ ] Test manual workflow trigger
- [ ] Test scheduled run

### Swift Client ✅
- [x] Charts render with yfinance data
- [x] SuperTrend AI working correctly
- [x] All indicators aligned

---

## Rollback Plan

If issues arise:

1. **Database:** Polygon data still exists (not deleted)
2. **Edge Functions:** Can revert to Polygon by updating provider factory
3. **GitHub Actions:** Can revert workflow files from git history
4. **Database Function:** Can update `get_chart_data_v2()` to prefer polygon

**Note:** Keep Polygon data for 30 days as backup before final cleanup.

---

## Next Actions (Priority Order)

1. **Create Edge Function Yahoo Finance client** (1-2 hours)
2. **Update symbol-backfill Edge Function** (30 mins)
3. **Update refresh-data Edge Function** (30 mins)
4. **Update GitHub Actions workflows** (30 mins)
5. **Test end-to-end flow** (1 hour)
6. **Monitor for 1 week** before removing Polygon completely

**Estimated Total Time:** 4-5 hours of development + 1 week monitoring
