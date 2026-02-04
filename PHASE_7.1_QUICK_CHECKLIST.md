# Phase 7.1 Quick Checklist

**Last Updated:** February 3, 2026  
**Canary Start:** TBD (after Must-Fix items complete)  
**Canary Duration:** 7 days  

---

## Pre-Launch Must-Fix (Do in Order)

### Critical Path - Complete Before Canary Launch

- [X] **MF-1: Look-Ahead Bias Audit** (2-3 hrs)
  - File: `ml/src/unified_forecast_job.py:150-300`
  - Task: Search for `[t]` patterns, change to `[t-1]`
  - Test: `grep -n "\[t\]" ml/src/unified_forecast_job.py`
  - **Cursor Prompt:** See PHASE_7.1_TESTING_AND_IMPROVEMENT_PLAN.md → "Phase 1: Feature Engineering Audit" → Task 1.1.1

- [X] **MF-2: TimeSeriesSplit Enforcement** (1-2 hrs)
  - File: `ml/src/training/walk_forward_optimizer.py:80-120`
  - Task: Verify using TimeSeriesSplit, not KFold
  - Test: Search for `from sklearn.model_selection import TimeSeriesSplit`
  - **Cursor Prompt:** See plan → "Phase 1" → Task 1.2.1

- [ ] **MF-3: Window Overlap Verification** (2-3 hrs)
  - File: `ml/src/training/walk_forward_optimizer.py:100-150`
  - Task: Print all window dates, verify no overlap
  - Test: Visual timeline of train/test windows
  - **Cursor Prompt:** See plan → "Phase 1" → Task 1.2.2

- [ ] **MF-4: Parameter Freezing** (1-2 hrs)
  - File: `ml/src/training/walk_forward_optimizer.py:150-200`
  - Task: Verify params frozen during OOS testing
  - Test: `assert model.get_params() unchanged after test`
  - **Cursor Prompt:** See plan → "Phase 2" → Task 2.1.2

**Total Est. Time:** 6-10 hours

---

## Pre-Launch Should-Fix (Recommended)

- [ ] **SF-1: Feature Variance Monitoring** (2 hrs)
  - Create: `tests/test_feature_variance_stability.py`
  - **Cursor Prompt:** See plan → "Phase 1" → Task 1.3.2

- [ ] **SF-2: Model Correlation Analysis** (2 hrs)
  - Create: `scripts/analyze_model_correlation.py`
  - Target: Correlation < 0.7
  - **Cursor Prompt:** See plan → "Phase 3" → Task 3.1.3

- [ ] **SF-3: Per-Model Divergence Tracking** (3 hrs)
  - File: `ml/src/monitoring/divergence_monitor.py:100-150`
  - Add: LSTM divergence + ARIMA divergence columns
  - **Cursor Prompt:** See plan → "Phase 3" → Task 3.3.2

- [ ] **SF-4: Distribution Shift Detection** (2-3 hrs)
  - Create: `scripts/check_feature_distribution_shift.py`
  - Test: KS test per feature, flag p < 0.05
  - **Cursor Prompt:** See plan → "Phase 1" → Task 1.3.3

- [ ] **SF-5: NaN Handling Documentation** (1-2 hrs)
  - File: `ml/src/unified_forecast_job.py:300-400`
  - Document current strategy, add limit to ffill
  - **Cursor Prompt:** See plan → "Phase 1" → Task 1.3.1

**Total Est. Time:** 10-12 hours

---

## Pre-Launch Final Checks

- [ ] **Database Ready**
  - Table `ensemble_validation_metrics` exists
  - Test query: `SELECT COUNT(*) FROM ensemble_validation_metrics;`

- [ ] **Integration Test**
  - Run: `python -m ml.src.unified_forecast_job --symbols AAPL,MSFT,SPY --horizon 1D --mode canary`
  - Expected: 3 forecasts, metrics logged, no errors

- [ ] **Rollback Tested**
  - Run: `bash scripts/rollback_to_legacy.sh --dry-run`
  - Verify 4-model still works

- [ ] **Monitoring Setup**
  - Script: `scripts/canary_daily_monitoring_supabase.js` works
  - Test: Generate sample report

---

## During Canary (Daily at 6 PM CST)

### Day 1-7 Checklist

**Every Day:**

- [ ] Run monitoring script:
  ```bash
  cd /Users/ericpeterson/SwiftBolt_ML
  SUPABASE_URL=$SUPABASE_URL SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY \
  node scripts/canary_daily_monitoring_supabase.js
  ```

- [ ] Review report: `canary_monitoring_reports/YYYYMMDD_canary_report.md`

- [ ] Check metrics:
  - [ ] Avg divergence < 10% ✅
  - [ ] Max divergence < 15% ✅
  - [ ] Overfitting alerts = 0 ✅
  - [ ] RMSE stable (±5%) ✅

- [ ] Log daily notes in `canary_monitoring_reports/DAILY_LOG.md`

**If Any Threshold Violated:**
1. Document in DAILY_LOG.md
2. Investigate root cause
3. If critical (divergence >20% or 3+ alerts), consider rollback

---

## End of Canary (Day 7)

- [ ] Run weekly summary:
  ```bash
  python scripts/weekly_performance_summary.py
  ```

- [ ] Apply GO/NO-GO Framework:

  **GO Criteria (ALL must pass):**
  - [ ] Avg divergence < 10% ✅
  - [ ] Max divergence < 15% ✅
  - [ ] <3 total overfitting alerts ✅
  - [ ] RMSE stable (±10%) ✅
  - [ ] All 7 reports generated ✅
  - [ ] Zero critical errors ✅

  **If GO:** Proceed to Phase 7.2 (full deployment)
  **If NO-GO:** Rollback or extend canary with fixes

- [ ] Document decision and rationale

- [ ] Update stakeholders

---

## Emergency Procedures

### Rollback Triggers:
- Divergence > 20% on any symbol
- 3+ overfitting alerts in one day
- Critical pipeline errors
- Database performance degradation

### Rollback Command:
```bash
bash scripts/rollback_to_legacy.sh
# Reverts to 4-model ensemble in ~5 minutes
```

### Emergency Contacts:
- [Add contacts here]

---

## Post-Canary Actions

### If Successful:
- [ ] Deploy to all symbols (Phase 7.2)
- [ ] Expand to 5D, 1W horizons
- [ ] Switch to weekly monitoring
- [ ] Archive canary reports
- [ ] Update documentation

### If Not Successful:
- [ ] Root cause analysis
- [ ] Document lessons learned
- [ ] Rollback or hybrid approach
- [ ] Schedule retrospective
- [ ] Plan fixes for next attempt

---

## Quick File Finder

**Main Files:**
- Testing Plan: `PHASE_7.1_TESTING_AND_IMPROVEMENT_PLAN.md`
- Schedule: `1_27_Phase_7.1_Schedule.md`
- Status: `PHASE_7_CANARY_DEPLOYMENT_STATUS.md`
- This Checklist: `PHASE_7.1_QUICK_CHECKLIST.md`

**Code Files:**
- Forecast Job: `ml/src/unified_forecast_job.py`
- Walk-Forward: `ml/src/training/walk_forward_optimizer.py`
- Divergence Monitor: `ml/src/monitoring/divergence_monitor.py`
- Forecast Synthesizer: `ml/src/forecast_synthesizer.py`

**Scripts:**
- Daily Monitoring: `scripts/canary_daily_monitoring_supabase.js`
- Rollback: `scripts/rollback_to_legacy.sh`
- Deployment: `scripts/deploy_phase_7_canary.sh`

**Database:**
- Migration: `backend/supabase/migrations/20260127_ensemble_validation_metrics.sql`
- Queries: `scripts/canary_monitoring_queries.sql`

---

## Current Status

**As of Feb 3, 2026:**
- Tests: 104/104 passing ✅
- Current divergence: 3.66% avg (target <10%) ✅
- Must-Fix items: **Not yet audited** ⚠️
- Should-Fix items: **Not yet implemented** ⚠️
- Canary launch: **BLOCKED until Must-Fix complete** 🛑

**Next Steps:**
1. Start with MF-1 (look-ahead bias audit)
2. Complete all Must-Fix items (6-10 hours)
3. Run integration test
4. Launch canary

---

**Document Version:** 1.0  
**Owner:** Eric Peterson  
**Review Date:** After Phase 7.1 Canary (7 days post-launch)  
