# Data Source Audit - Real Data vs Deprecated Tables

**Date:** 2026-01-10  
**Status:** ⚠️ CRITICAL - Multiple systems using deprecated `ohlc_bars` table

---

## ✅ Systems Using REAL DATA (ohlc_bars_v2)

### ML Production Systems
1. **`ml/src/data/supabase_db.py`** - ✅ `fetch_ohlc_bars()` uses `ohlc_bars_v2`
2. **`ml/src/job_worker.py`** - ✅ Uses `db.fetch_ohlc_bars()` → `ohlc_bars_v2`
3. **`ml/src/forecast_job.py`** - ✅ Uses `db.fetch_ohlc_bars()` → `ohlc_bars_v2`
4. **`ml/src/services/forecast_service_v2.py`** - ✅ Writes forecasts to `ohlc_bars_v2`
5. **`ml/src/intraday_forecast_job.py`** - ✅ Uses `db.fetch_ohlc_bars()` → `ohlc_bars_v2`

### Backfill Scripts (V2)
6. **`ml/src/scripts/deep_backfill_ohlc_v2.py`** - ✅ Writes to `ohlc_bars_v2` with provider='polygon'
7. **`ml/src/scripts/backfill_ohlc_yfinance.py`** - ✅ Writes to `ohlc_bars_v2`
8. **`ml/src/scripts/backfill_with_gap_detection.py`** - ✅ Queries `ohlc_bars_v2`

---

## ❌ Systems Using DEPRECATED DATA (ohlc_bars v1)

### Legacy Backfill Scripts - NEED MIGRATION
1. **`ml/src/scripts/backfill_ohlc.py`** - ❌ Writes to `ohlc_bars`
2. **`ml/src/scripts/deep_backfill_ohlc.py`** - ❌ Writes to `ohlc_bars`
3. **`ml/src/scripts/process_backfill_queue.py`** - ❌ Writes to `ohlc_bars`

### Database Access Layer - NEED MIGRATION
4. **`ml/src/data/db.py`** - ❌ `fetch_ohlc_bars()` queries `ohlc_bars` (legacy Postgres client)

### Monitoring/Dashboard - NEED MIGRATION
5. **`ml/src/monitoring/price_monitor.py`** - ❌ Queries `ohlc_bars`
6. **`ml/src/dashboard/forecast_dashboard.py`** - ❌ Queries `ohlc_bars`

### Validation Scripts - NEED MIGRATION
7. **`scripts/validation/debug_nvda_forecast.py`** - ❌ Queries `ohlc_bars`
8. **`scripts/validation/verify_database_prices.py`** - ❌ Queries `ohlc_bars`

---

## 🔍 Analysis

### Critical Findings

1. **Dual Database Clients**:
   - `ml/src/data/supabase_db.py` (Supabase client) → ✅ Uses `ohlc_bars_v2`
   - `ml/src/data/db.py` (Postgres client) → ❌ Uses `ohlc_bars`

2. **ML Job Worker Status**: ✅ **SAFE**
   - Uses `SupabaseDatabase` class which correctly queries `ohlc_bars_v2`
   - All production ML jobs are using real data

3. **Legacy Scripts**: ❌ **DANGEROUS**
   - Old backfill scripts still write to `ohlc_bars`
   - Could cause data inconsistency if run

4. **Monitoring/Dashboards**: ❌ **SHOWING STALE DATA**
   - Dashboard and monitoring tools query old table
   - Users may see outdated information

---

## 📋 Migration Plan

### Phase 1: Immediate (Critical)
- [ ] **Disable legacy backfill scripts** (add deprecation warnings)
- [ ] **Update `ml/src/data/db.py`** to use `ohlc_bars_v2`
- [ ] **Update price monitor** to use `ohlc_bars_v2`

### Phase 2: Dashboard Migration
- [ ] **Update forecast dashboard** to use `ohlc_bars_v2`
- [ ] **Update validation scripts** to use `ohlc_bars_v2`

### Phase 3: Cleanup
- [ ] **Archive deprecated scripts** to `ml/src/scripts/deprecated/`
- [ ] **Add README** explaining migration
- [ ] **Consider dropping `ohlc_bars` table** after verification

---

## ⚠️ Risk Assessment

**HIGH RISK:**
- Legacy scripts could overwrite/corrupt data if accidentally run
- Monitoring shows stale data, could mislead operations
- Database client inconsistency could cause confusion

**MITIGATION:**
- ML production systems are safe (using v2)
- Migration is straightforward (table schema compatible)
- Can verify data consistency before dropping old table

---

## 🎯 Recommended Actions

1. **Immediately**: Add deprecation warnings to legacy scripts
2. **This Week**: Migrate db.py, price_monitor.py, dashboard
3. **Next Week**: Archive deprecated code, verify data consistency
4. **Future**: Consider dropping `ohlc_bars` table after 30-day verification period
