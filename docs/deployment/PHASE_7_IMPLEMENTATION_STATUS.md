# Phase 7.1 Implementation Status & Recommendations

**Date:** January 27, 2026
**Current State:** Infrastructure built, but data pipeline not connected
**Risk:** Planned 6-day canary (Jan 28-Feb 4) will monitor empty data

---

## What We've Actually Implemented

### Phase 1: Model Simplification ✅ COMPLETE
- Updated ensemble to 2-model config (LSTM + ARIMA-GARCH)
- Modified `enhanced_ensemble_integration.py` with `ENSEMBLE_MODEL_COUNT=2`
- Backward compatible with legacy 4-model ensemble
- **Status:** Deployed in commit fe376cf, 195 tests passing

### Phase 2: Walk-Forward Validation ✅ COMPLETE
- Created `walk_forward_optimizer.py` (470 lines)
- Implements per-window hyperparameter tuning
- Tracks divergence between validation and test RMSE
- **Status:** Code exists, tested, integrated into forecast job logic
- **Reality:** Generates metrics internally but doesn't persist them

### Phase 3: Calibrator Divergence Monitoring ✅ COMPLETE
- Updated `intraday_weight_calibrator.py` with 3-way split (train 60% / val 20% / test 20%)
- Detects overfitting when divergence > 15%
- Reverts to equal weights on overfitting
- **Status:** Functional, tested
- **Reality:** Monitors locally but doesn't log to database

### Phase 4: Synthesis Simplification ✅ COMPLETE
- Simplified `forecast_synthesizer.py` from 6-model to 2-3 model logic
- Updated ensemble agreement calculations
- Removed RF/Prophet/Transformer logic
- **Status:** Deployed and working

### Phase 5: Database & Monitoring ⚠️ PARTIAL
- Created `ensemble_validation_metrics` table (24 fields, 5 indexes)
- Created views: `vw_overfitting_symbols`, `vw_divergence_trends`
- Created function: `get_ensemble_stats()`
- **Status:** Schema exists, migration executed
- **ISSUE:** Table is **empty** - no data being inserted

### Phase 6: Testing ✅ COMPLETE
- 104 new tests created (total 195 passing)
- Database operations tested
- Walk-forward validation tested
- Backward compatibility verified
- **Status:** All tests passing, but tests don't verify data flow

### Phase 7.1: Canary Monitoring Infrastructure ✅ COMPLETE
- Created `canary_daily_monitoring_supabase.js` (Supabase-compatible)
- Generates daily reports: `canary_monitoring_reports/YYYYMMDD_canary_report.md`
- Reports format: Divergence Summary | RMSE Comparison | Overfitting Status
- **Status:** Script works perfectly with Supabase connection
- **ISSUE:** Reports show "(no data)" because the table is empty

---

## The Critical Gap: Data Pipeline Not Connected

### What's Missing

The forecast pipeline runs and generates predictions, but:

1. **Walk-forward optimizer generates divergence metrics internally** (in memory)
   - ✅ Calculates divergence correctly
   - ❌ Doesn't persist to database
   - File: `ml/src/training/walk_forward_optimizer.py`

2. **Divergence monitor exists** with `log_window_result()` method
   - ✅ Ready to receive metrics
   - ❌ Never called by forecast pipeline
   - File: `ml/src/monitoring/divergence_monitor.py`

3. **Forecast job doesn't integrate the monitor**
   - ❌ `intraday_forecast_job.py` doesn't instantiate DivergenceMonitor
   - ❌ Walk-forward results not passed to monitor
   - ❌ No database writes happening
   - File: `ml/src/intraday_forecast_job.py`

### Current Data Flow

```
Forecast Pipeline Runs
  ↓
Walk-Forward Optimizer calculates divergence
  ↓
Metrics exist in memory
  ↓
Divergence Monitor never called
  ↓
ensemble_validation_metrics table stays empty
  ↓
Monitoring script shows: (no data)
```

---

## What a 6-Day Empty Canary Would Look Like

**Jan 28-Feb 4:** Running monitoring script daily would show:
- ✅ Script executes successfully
- ✅ Report format is correct
- ❌ All metrics are zero
- ❌ No divergence data
- ❌ No overfitting alerts
- ❌ No actual validation happening

**Result:** Meaningless canary that proves "the infrastructure works" but not "the system works"

---

## Recommended Next Steps (In Order)

### Option A: Fix Before Canary (Recommended)
**Time: ~2-3 hours, ensures data-driven decision**

1. **Integrate DivergenceMonitor into forecast pipeline** (1 hour)
   - Update `intraday_forecast_job.py` to instantiate DivergenceMonitor
   - Connect walk_forward_optimizer output to monitor.log_window_result()
   - Test that data flows to database

2. **Verify data population** (30 min)
   - Run forecast job manually
   - Check ensemble_validation_metrics table has rows
   - Confirm monitoring script shows real data

3. **Update canary dates** (15 min)
   - Adjust checklist to reflect actual start date (when data flows)
   - Run first real monitoring report
   - Confirm it shows real AAPL/MSFT/SPY metrics

4. **Start canary with real data** (Jan 28+)
   - 6 trading days of actual divergence monitoring
   - Make informed PASS/FAIL decision

### Option B: Start Canary Now (Not Recommended)
**Pros:**
- Starts on schedule (Jan 28)
- Monitoring infrastructure is "working"

**Cons:**
- 6 days of empty data collection
- Can't evaluate actual 2-model ensemble performance
- Decision on Feb 4 is meaningless (no data to decide on)
- Have to integrate pipeline mid-canary anyway

### Option C: Hybrid Approach (Compromise)
**Time: ~4-5 hours, provides quick validation**

1. Integrate DivergenceMonitor into pipeline (1 hour)
2. Run quick 1-2 day validation (Feb 1-2) with real data
3. Verify system works end-to-end
4. Run 6-trading-day canary (Feb 4-13)
5. Make decision Feb 14

---

## My Strong Recommendation

**Go with Option A.** Here's why:

1. **We've already done 90% of the work** - just need to wire the last 10%
2. **The integration is straightforward** - just 3-4 method calls in the forecast job
3. **Cost of delay:** ~2 hours vs **cost of meaningless canary:** 6 days of wasted time
4. **Confidence in the system:** You'll know the 2-model ensemble actually works
5. **Better decision-making:** Feb 5 decision will be based on real performance data

The alternative is running a canary on infrastructure that's never actually been tested end-to-end, which defeats the purpose of a canary.

---

## Summary Table

| Component | Status | Ready? | Blocker |
|-----------|--------|--------|---------|
| 2-model ensemble | Deployed | ✅ | None |
| Walk-forward optimizer | Implemented | ✅ | Not connected to DB |
| Divergence monitor | Created | ✅ | Not called by pipeline |
| Database schema | Created | ✅ | Empty - no inserts |
| Monitoring script | Working | ✅ | No data to report |
| Canary infrastructure | Complete | ✅ | Missing data connection |
| **Data pipeline integration** | **Missing** | ❌ | **BLOCKER** |

---

## Files That Need Modification

To implement Option A (recommended):

1. **`ml/src/intraday_forecast_job.py`**
   - Import DivergenceMonitor
   - Instantiate monitor with Supabase client
   - Call monitor.log_window_result() after walk-forward optimization
   - ~15-20 lines of code

2. **Environment setup**
   - Ensure Supabase credentials available to forecast job
   - May need to update GitHub Actions if running in CI

---

## Next Decision Point

**What do you want to do?**

1. **Integrate the monitor now** (Option A) - delay canary start by 2-3 hours but get real data
2. **Keep scheduled canary** (Option B) - start Jan 28 with empty data
3. **Hybrid approach** (Option C) - quick validation run first, then full canary

My professional recommendation: **Option A** - the monitoring infrastructure is elegant and ready, just needs the data connection. 2-3 hours to do it right beats 6 days of watching zeros.
