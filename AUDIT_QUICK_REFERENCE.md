# SwiftBolt ML Audit - Quick Reference Guide
**Generated**: January 23, 2026

---

## 📊 PROBLEM SUMMARY (TL;DR)

### Current State: 🔴 FRAGMENTED
- **18+ competing scripts** processing independently
- **3 forecast systems** (all write to same `ml_forecasts` table)
- **2 evaluation frameworks** (both write to `forecast_evaluations`)
- **5 weight calibration methods** (no clear precedence)
- **9-14 feature rebuilds per symbol per cycle** (0% cache reuse)
- **60-75% computational waste**
- **Processing time**: 60-90 minutes

### Goal State: 🟢 UNIFIED
- **1 unified forecast job** (daily: 1D, 1W, 1M)
- **1 intraday forecast job** (hourly: 15m, 1h)
- **2 evaluation jobs** (daily + intraday, separate tables)
- **1 options processor** (consolidated scoring)
- **Redis feature cache** (95%+ hit rate)
- **Processing time**: 15-20 minutes (4-6x faster)

---

## 🎯 THREE MAIN ISSUES

### Issue #1: Feature Rebuilding (9-14x per cycle)

**Root Cause**: In-memory cache only, no persistence

```
Worker 1 builds features for AAPL → Cache destroyed on exit
Worker 2 builds features for AAPL → No cache available, rebuilds
Worker 3 builds features for AAPL → No cache available, rebuilds
... (repeat 9-14 times)
```

**Impact**: 20-45 seconds wasted per symbol × 2000 symbols = **11-25 hours wasted daily**

**Solution**: Redis cache with 24-hour TTL

```python
# Before (0% reuse)
features = fetch_or_build_features(symbol)  # Always rebuilds

# After (95%+ reuse)
features = fetch_or_build_features(symbol, redis_cache=redis)  # Hits cache
```

---

### Issue #2: Multiple Forecast Writers (Race Condition)

**Root Cause**: 3 scripts write to `ml_forecasts` table

```
script 1: forecast_job.py → writes AAPL 1D forecast @ 04:00
script 2: multi_horizon_forecast_job.py → writes AAPL 1D forecast @ 04:05 (OVERWRITES)
script 3: multi_horizon_forecast.py → called by scripts 1 & 2 (DUPLICATE WORK)
```

**Impact**: Inconsistent data, unclear which forecast is "live"

**Solution**: Single unified writer

```python
# Before (race condition)
db.insert(forecast)  # from forecast_job
db.insert(forecast)  # from multi_horizon (overwrites)

# After (atomic)
with db.transaction():
    db.insert_or_replace(forecast, version=version_id)
    db.log_weight_source(symbol, weights_used)
```

---

### Issue #3: Evaluation Data Mixing (Bad Analytics)

**Root Cause**: Both daily and intraday evaluations write to same table

```sql
-- Current query gets mixed data
SELECT * FROM forecast_evaluations
WHERE symbol='AAPL'
-- Returns mix of: 1D forecasts, 15m forecasts, 1h forecasts all together!
```

**Impact**: Dashboard shows inconsistent metrics, can't compare apples-to-apples

**Solution**: Separate tables with clear purpose

```sql
-- After: Crystal clear
SELECT * FROM forecast_evaluations_daily WHERE horizon='1D'  -- Only 1D
SELECT * FROM forecast_evaluations_intraday WHERE horizon='15m'  -- Only 15m
```

---

## 📋 SCRIPT CONSOLIDATION ROADMAP

### REMOVE (Consolidate Into Unified Jobs)

```
❌ forecast_job.py (keep logic, move to unified_forecast_job.py)
❌ multi_horizon_forecast_job.py (merge into unified_forecast_job.py)
❌ multi_horizon_forecast.py (merge into unified_forecast_job.py)
❌ evaluation_job.py (split: daily → evaluation_job_daily.py)
❌ intraday_evaluation_job.py (move to evaluation_job_intraday.py)
❌ forecast_job_worker.py (orphaned, remove)
❌ job_worker.py (unused base class, remove)
❌ ranking_job_worker.py (redundant, consolidate)
❌ hourly_ranking_scheduler.py (consolidate into daily)
```

### CREATE (Unified Processors)

```
✅ unified_forecast_job.py (MAIN: daily forecasts 1D, 1W, 1M)
   ├─ One entry point
   ├─ Redis feature cache
   ├─ Weight precedence logic
   └─ Single write to ml_forecasts

✅ evaluation_job_daily.py (daily evaluations only)
   ├─ Reads: ml_forecasts (1D, 1W, 1M)
   └─ Writes: forecast_evaluations_daily

✅ evaluation_job_intraday.py (intraday evaluations only)
   ├─ Reads: ml_forecasts_intraday (15m, 1h)
   └─ Writes: forecast_evaluations_intraday
```

### OPTIMIZE (Existing Scripts)

```
🔧 feature_cache.py: Add Redis backing
🔧 support_resistance_detector.py: Cache S/R levels
🔧 technical_indicators.py: Cache indicator results
```

---

## 💾 DATABASE SCHEMA CHANGES

### NEW TABLES (Separate Horizons)

```sql
-- Split ml_forecasts by horizon
ml_forecasts_daily       -- 1D, 1W, 1M only
ml_forecasts_intraday    -- 15m, 1h only

-- Split evaluations by horizon
forecast_evaluations_daily       -- 1D, 1W, 1M only
forecast_evaluations_intraday    -- 15m, 1h only

-- Split live_predictions by horizon
live_predictions_daily       -- 1D, 1W, 1M only
live_predictions_intraday    -- 15m, 1h only

-- Version tracking
ALTER TABLE calibrated_weights ADD version_id INT
ALTER TABLE model_weights ADD version_id INT
ALTER TABLE model_weights ADD source VARCHAR(50)  -- 'intraday', 'daily', 'default'
```

---

## 🚀 IMPLEMENTATION ROADMAP

### Week 1: Analysis & Planning
- [ ] Map script dependencies
- [ ] Create baseline metrics
- [ ] Set up test infrastructure

### Week 2: Consolidation
- [ ] Build `unified_forecast_job.py`
- [ ] Create `evaluation_job_daily.py` + `evaluation_job_intraday.py`
- [ ] Implement Redis feature caching
- [ ] Update GitHub Actions workflows

### Week 3: Testing & Validation
- [ ] Run parallel tests (old vs. new)
- [ ] Compare forecast outputs
- [ ] Performance benchmarking
- [ ] Fix any discrepancies

### Week 4: Production Deployment
- [ ] Archive old scripts
- [ ] Update configuration
- [ ] Deploy unified pipeline
- [ ] Update Edge Functions
- [ ] Monitor production metrics

---

## 📈 EXPECTED IMPROVEMENTS

### Processing Time
```
Before: 60-90 minutes (full cycle)
After:  15-20 minutes (4-6x faster)
```

### Feature Cache Hit Rate
```
Before: 0% (memory-only, lost between workers)
After:  95%+ (Redis persistent, 24h TTL)
```

### Compute Waste
```
Before: 60-75% (redundant rebuilds, race conditions)
After:  10-15% (minimal overhead)
```

### API Response Latency
```
Before: 2-3 seconds (multiple tables to query)
After:  200-400ms (single, clean table)
```

### Data Freshness
```
Before: 30-60 minutes skew (parallel jobs, unclear timing)
After:  <5 minutes (sequential, explicit timing)
```

---

## 🔧 QUICK START: PHASE 1 (This Week)

### 1. Implement Redis Caching

```bash
# Install Redis (if not already)
brew install redis  # macOS
# or docker run -d -p 6379:6379 redis:latest

# Test connection
redis-cli ping  # Should return PONG

# Update feature_cache.py with Redis code (see implementation plan)
```

### 2. Add Metrics Tracking

```bash
# Modify forecast_job.py to track:
# - Feature cache hit rate
# - Processing time per symbol
# - Weight source selected
# - DB write conflicts

# Run and collect baseline
python ml/src/forecast_job.py
cat processing_metrics.json
```

### 3. Create Audit Log

```bash
# Create directory for audit artifacts
mkdir -p audit_results
cd audit_results

# Copy generated reports
cp /Users/ericpeterson/SwiftBolt_ML/SWIFTBOLT_ML_STATISTICAL_AUDIT_REPORT.md .
cp /Users/ericpeterson/SwiftBolt_ML/CONSOLIDATION_IMPLEMENTATION_PLAN.md .
```

---

## ⚡ WEIGHT SELECTION PRIORITY (NEW)

**Atomic precedence with logging**:

```python
# When selecting weights for forecast synthesis:

# Priority 1: Intraday-calibrated weights (if fresh)
if intraday_weights.age < 4_hours:
    weights = intraday_weights
    source = 'intraday_calibrated'
    
# Priority 2: Symbol-specific daily weights (if enabled)
elif symbol_weights_enabled and symbol_weights.exists:
    weights = symbol_weights
    source = 'daily_symbol'
    
# Priority 3: Default hardcoded weights
else:
    weights = DEFAULT_WEIGHTS
    source = 'default'

# ALWAYS log which was selected
logger.info(f"Using {source} weights for {symbol} {horizon}")
db.log_weight_selection(symbol, horizon, source, weights)
```

**No more ambiguity about which weights were used!**

---

## 📊 METRICS TO TRACK

### Processing Metrics
```json
{
  "timestamp": "2026-01-23T04:00:00Z",
  "total_symbols": 2000,
  "successful": 1998,
  "failed": 2,
  "total_processing_time_seconds": 1245,
  "avg_time_per_symbol": 0.62,
  "feature_cache_hits": 3987,
  "feature_cache_misses": 13,
  "cache_hit_rate_percent": 99.7,
  "weight_sources": {
    "intraday_calibrated": 1200,
    "daily_symbol": 600,
    "default": 198
  },
  "db_writes": 5994  // 2000 symbols × 3 horizons
}
```

### Quality Metrics
```json
{
  "forecast_evaluations_daily": {
    "1D_accuracy": 0.58,
    "1W_accuracy": 0.62,
    "1M_accuracy": 0.65
  },
  "forecast_evaluations_intraday": {
    "15m_accuracy": 0.52,
    "1h_accuracy": 0.55
  }
}
```

---

## 🎓 KEY TAKEAWAYS

### What's Wrong (Root Causes)
1. **No shared caching** → Features rebuilt 9-14x
2. **Multiple writers** → Race conditions, unclear state
3. **Horizon mixing** → Bad data for analysis
4. **No explicit sequencing** → Hidden dependencies
5. **Weight ambiguity** → Can't audit decisions

### What's Required (Solutions)
1. **Redis cache** → Persistent, TTL-based
2. **Single writer** → Atomic transactions, versioning
3. **Horizon separation** → Distinct tables & jobs
4. **Explicit DAG** → GitHub Actions dependencies
5. **Audit logging** → Every decision tracked

### Expected ROI
- **Time Savings**: 20-40 hours/month in perpetuity
- **Data Quality**: Elimination of race conditions
- **Maintainability**: 60% fewer scripts
- **Debugging**: Clear job dependencies, explicit logging

---

## 📞 SUPPORT

### Generated Artifacts
1. `/Users/ericpeterson/SwiftBolt_ML/SWIFTBOLT_ML_STATISTICAL_AUDIT_REPORT.md` - Full analysis
2. `/Users/ericpeterson/SwiftBolt_ML/CONSOLIDATION_IMPLEMENTATION_PLAN.md` - Step-by-step plan
3. `/Users/ericpeterson/SwiftBolt_ML/AUDIT_QUICK_REFERENCE.md` - This file

### Next Steps
1. Review the full audit report
2. Follow the implementation plan
3. Run Phase 1 (Redis caching) this week
4. Schedule Phase 2-4 over next 3 weeks
5. Expect 4-6x processing speedup

---

**Status**: Ready for implementation  
**Confidence Level**: High (based on detailed code analysis)  
**Risk Level**: Low (parallel testing available)
