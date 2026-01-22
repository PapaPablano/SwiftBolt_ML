# SwiftBolt Validation Framework: Implementation Checklist

**Objective**: Integrate UnifiedValidator with dashboard to resolve metric confusion  
**Status**: Phase 1 Complete ✅ - Ready for Phase 2  
**Est. Time**: 6-8 hours total (Phase 1: 1 hour complete)  
**Last Updated**: January 22, 2026

---

## 📃 Complete Task Breakdown

### Phase 0: Setup & Verification (30 minutes)

- [ ] **Verify existing validator code**
  - [ ] Check `ml/src/validation/unified_framework.py` exists
  - [ ] Run: `python -m src.validation.unified_framework`
  - [ ] Verify output shows AAPL example with 58% unified confidence
  - [ ] Document command in local notes

- [ ] **Check database tables**
  - [ ] Connect to Supabase
  - [ ] Verify tables exist:
    - [ ] `ml_model_metrics` (backtesting scores)
    - [ ] `rolling_evaluation` (walk-forward scores)
    - [ ] `live_predictions` (current predictions + realized outcomes)
    - [ ] `indicator_values` (multi-TF scores)
  - [ ] For missing tables, create schemas
  - [ ] Document table schemas in `DATABASE_SCHEMA.md`

- [ ] **Test Python environment**
  - [ ] Python 3.9+ installed
  - [ ] All requirements in `ml/requirements.txt`
  - [ ] Run: `python -c "from src.validation import UnifiedValidator; print('OK')"`
  - [ ] No import errors

### Phase 1: Data Pipeline (2 hours) ✅ COMPLETE

**Status**: ✅ Deployed and tested (January 22, 2026)  
**Files Created**: 
- `ml/src/services/validation_service.py` ✅
- `ml/src/services/test_validation_service.py` ✅
- `supabase/migrations/20260122000000_create_validation_results.sql` ✅

- [x] **Create ValidationService class** ✅
  - [x] `__init__` method connects to database
  - [x] Imports UnifiedValidator
  - [x] Sets up logging

- [x] **Implement metric fetching methods** ✅
  - [x] `_get_backtesting_score(symbol)` - Query 90-day window from `model_validation_stats`
  - [x] `_get_walkforward_score(symbol)` - Query 13-week rolling window from `model_validation_stats`
  - [x] `_get_live_score(symbol)` - Query last 30 predictions from `live_predictions`
  - [x] `_get_multi_tf_scores(symbol)` - Query M15, H1, H4, D1, W1 from `indicator_values`
  - [x] All methods have proper error handling
  - [x] All methods have logging
  - [x] All methods have default fallback values

- [x] **Implement main validation method** ✅
  - [x] `get_live_validation(symbol, direction)` calls all fetchers
  - [x] Creates ValidationScores object
  - [x] Calls validator.validate()
  - [x] Stores result via `_store_validation_result()`
  - [x] Returns UnifiedPrediction

- [x] **Implement database storage** ✅
  - [x] `_store_validation_result()` inserts into `validation_results` table
  - [x] Handles insert errors gracefully
  - [x] Logs successful storage

- [x] **Test ValidationService locally** ✅
  - [x] Create `test_validation_service.py` in `ml/src/services/`
  - [x] Test each fetcher method independently
  - [x] Test `get_live_validation()` end-to-end
  - [x] Run: `python ml/src/services/test_validation_service.py`
  - [x] Verify output shows unified prediction (47.2% confidence, drift detection working)

**Test Results**: ✅ PASSED - All database tables verified, validation pipeline working end-to-end

### Phase 2: API Integration (1.5 hours)

**Files Created**: `ml/src/api/validation_api.py` ✅

- [ ] **Create validation API router**
  - [ ] Import FastAPI, APIRouter
  - [ ] Create router with `/api/validation` prefix
  - [ ] Create ValidationResponse helper class

- [ ] **Implement unified validation endpoint**
  - [ ] `GET /api/validation/unified/{symbol}/{direction}`
  - [ ] Validate direction is BULLISH/BEARISH/NEUTRAL
  - [ ] Call ValidationService.get_live_validation()
  - [ ] Convert result to ValidationResponse
  - [ ] Return JSON with proper error handling
  - [ ] Add comprehensive docstring with example

- [ ] **Implement history endpoint**
  - [ ] `GET /api/validation/history/{symbol}?days=7&limit=100`
  - [ ] Query validation_results table
  - [ ] Calculate trend statistics (avg, min, max confidence)
  - [ ] Determine drift trend (increasing/decreasing/stable)
  - [ ] Return formatted history with trend summary

- [ ] **Implement drift alerts endpoint**
  - [ ] `GET /api/validation/drift-alerts?min_severity=moderate&limit=50`
  - [ ] Query all symbols with detected drift
  - [ ] Filter by severity threshold
  - [ ] Sort by drift magnitude (highest first)
  - [ ] Return alerts with context

- [ ] **Test API endpoints**
  - [ ] Create simple test script or Postman collection
  - [ ] Test each endpoint with curl
  - [ ] Verify response format matches spec
  - [ ] Test error handling (invalid symbol, bad direction, etc.)
  - [ ] Test with various severity filters

### Phase 3: Dashboard Integration (3 hours)

**Files Created**: `ml/src/dashboard/validation_reconciliation.py` (NEW)

- [ ] **Create validation_reconciliation.py module**
  - [ ] Import necessary libraries (streamlit, plotly, pandas, requests)
  - [ ] Implement `fetch_unified_validation()` function
  - [ ] Implement `fetch_validation_history()` function
  - [ ] Implement `render_validation_reconciliation()` main render function

- [ ] **Implement top metrics section**
  - [ ] Display unified confidence (hero metric)
  - [ ] Display status emoji (🟢/🟡/🟠/🔴)
  - [ ] Display drift severity badge
  - [ ] Display retraining alert if needed

- [ ] **Implement component breakdown section**
  - [ ] Create horizontal bar chart (backtesting vs walk-forward vs live)
  - [ ] Show weights (40%, 35%, 25%)
  - [ ] Add unified confidence reference line
  - [ ] Color code by confidence level

- [ ] **Implement drift analysis section**
  - [ ] Show drift detected status
  - [ ] Show drift magnitude percentage
  - [ ] Show severity level
  - [ ] Display drift explanation text

- [ ] **Implement multi-TF consensus section**
  - [ ] Show consensus direction (BULLISH/BEARISH/NEUTRAL)
  - [ ] Show conflict detection status
  - [ ] Display timeframe breakdown bar chart
  - [ ] Show hierarchy weights explanation
  - [ ] List which timeframes agree/disagree

- [ ] **Implement confidence adjustments section**
  - [ ] List all adjustments applied
  - [ ] Color code by type (penalty = warning, bonus = success)
  - [ ] Show percentages

- [ ] **Implement trading recommendation section**
  - [ ] Color-coded by confidence level
  - [ ] Display actionable text
  - [ ] Link to retraining status

- [ ] **Implement historical trend section**
  - [ ] Fetch 7-day validation history
  - [ ] Create line chart of confidence over time
  - [ ] Show 4 trend metrics (avg, min, max, drift_trend)
  - [ ] Detect if trending up/down/stable

- [ ] **Test dashboard rendering locally**
  - [ ] Run: `streamlit run ml/src/dashboard/validation_reconciliation.py`
  - [ ] Verify all sections render
  - [ ] Verify charts display correctly
  - [ ] Test symbol selection dropdown
  - [ ] Test direction selection dropdown
  - [ ] Verify color coding works
  - [ ] Test export functionality

### Phase 4: Forecast Pipeline Integration (1.5 hours)

**Files Modified**: `ml/src/intraday_forecast_job.py`, `ml/src/forecast_job.py`

- [ ] **Modify intraday_forecast_job.py**
  - [ ] Import ValidationService
  - [ ] After forecast generation, call validator
  - [ ] Store validation result with forecast
  - [ ] Return combined forecast + validation result
  - [ ] Update database insert to include validation fields
  - [ ] Add logging for validation calls
  - [ ] Test locally with sample data

- [ ] **Modify forecast_job.py**
  - [ ] Same changes as intraday_forecast_job.py
  - [ ] Ensure consistency between both files
  - [ ] Test with sample data

- [ ] **Verify database storage**
  - [ ] Check ml_forecasts table now includes validation fields
  - [ ] Verify validation_results table populated
  - [ ] Check for any constraint violations
  - [ ] Monitor for performance impact

- [ ] **Test end-to-end pipeline**
  - [ ] Trigger forecast generation
  - [ ] Verify validation runs
  - [ ] Check database contains both forecast + validation
  - [ ] Verify no errors in logs

### Phase 5: Streamlit Dashboard Integration (1 hour)

**Files Modified**: `ml/src/dashboard/forecast_dashboard.py`

- [ ] **Add import**
  - [ ] `from src.dashboard.validation_reconciliation import render_validation_reconciliation`

- [ ] **Update sidebar view selection**
  - [ ] Add "🔄 Validation Reconciliation" to radio button options
  - [ ] Maintain order: Overview, Forecast Details, Validation, Performance, Features

- [ ] **Update main view router**
  - [ ] Add condition: `if view == "🔄 Validation Reconciliation":`
  - [ ] Call `render_validation_reconciliation(symbols)`
  - [ ] Ensure symbols list passed correctly

- [ ] **Test dashboard navigation**
  - [ ] Run: `streamlit run ml/src/dashboard/forecast_dashboard.py`
  - [ ] Verify all tabs load
  - [ ] Click between tabs
  - [ ] Verify Validation Reconciliation tab opens
  - [ ] Verify data loads without errors

### Phase 6: Testing & Validation (2 hours)

- [ ] **Unit Tests**
  - [ ] Create `ml/src/services/test_validation_service.py`
  - [ ] Test each fetcher method
  - [ ] Test validation service end-to-end
  - [ ] Run: `python -m pytest ml/src/services/test_validation_service.py -v`
  - [ ] All tests pass

- [ ] **Integration Tests**
  - [ ] Create `ml/src/tests/test_forecast_with_validation.py`
  - [ ] Test forecast generation + validation pipeline
  - [ ] Verify database storage
  - [ ] Run: `python -m pytest ml/src/tests/test_forecast_with_validation.py -v`
  - [ ] All tests pass

- [ ] **API Tests**
  - [ ] Create `ml/src/tests/test_validation_api.py`
  - [ ] Test each endpoint
  - [ ] Test error conditions
  - [ ] Run: `python -m pytest ml/src/tests/test_validation_api.py -v`
  - [ ] All tests pass

- [ ] **Manual Dashboard Testing**
  - [ ] Start API server: `python -m src.api.server`
  - [ ] Start dashboard: `streamlit run ml/src/dashboard/forecast_dashboard.py`
  - [ ] Select each symbol
  - [ ] Verify metrics reconcile correctly
  - [ ] Verify charts render
  - [ ] Verify drift alerts show when appropriate
  - [ ] Test export functionality
  - [ ] Test 7-day historical trend

- [ ] **Performance Testing**
  - [ ] Measure API response time (target: <500ms)
  - [ ] Measure dashboard load time (target: <2s)
  - [ ] Check for memory leaks (run for 10+ minutes)
  - [ ] Monitor database query performance

- [ ] **Browser Compatibility**
  - [ ] Test in Chrome
  - [ ] Test in Safari
  - [ ] Test in Firefox
  - [ ] Verify charts render correctly
  - [ ] Verify responsive layout on tablet/mobile

### Phase 7: Documentation & Deployment (1 hour)

- [ ] **Update README.md**
  - [ ] Add section: "Validation Reconciliation Dashboard"
  - [ ] Explain three-metric reconciliation
  - [ ] Link to VALIDATION_IMPLEMENTATION_ROADMAP.md
  - [ ] Add screenshot or GIF of dashboard

- [ ] **Create DEPLOYMENT.md**
  - [ ] Document how to deploy changes
  - [ ] Include database migration steps
  - [ ] Document environment variables needed
  - [ ] Include rollback procedure

- [ ] **Update CHANGELOG.md**
  - [ ] Add entry: "Added Validation Reconciliation Dashboard"
  - [ ] List files modified/created
  - [ ] Document breaking changes (if any)

- [ ] **Create runbook**
  - [ ] Document how to start API server
  - [ ] Document how to start dashboard
  - [ ] Document how to troubleshoot common issues
  - [ ] Document monitoring/alerting setup

- [ ] **Deploy to staging**
  - [ ] Merge all changes to staging branch
  - [ ] Run full test suite
  - [ ] Deploy to staging environment
  - [ ] Test in staging for 24 hours
  - [ ] Monitor logs for errors

- [ ] **Deploy to production**
  - [ ] Create production deployment PR
  - [ ] Get code review
  - [ ] Merge to main branch
  - [ ] Deploy during low-trading hours
  - [ ] Monitor for 24 hours
  - [ ] Be prepared to rollback

---

## ⚠️ Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|--------|
| Database tables missing | Medium | High | Pre-flight check in Phase 0 |
| API endpoint timeout | Low | Medium | Add request timeout, async handling |
| Streamlit performance degrades | Medium | Medium | Test with 1000+ records |
| Model scores not in database | High | High | Fallback to 0.50-0.60 defaults |
| Breaking change to forecast job | Low | High | Feature flag to enable validation |
| Dashboard doesn't load | Low | High | Add error boundary, fallback UI |

---

## 😟 Debugging Commands

```bash
# Test validator
python -m src.validation.unified_framework

# Test validation service
python ml/src/services/validation_service.py

# Run unit tests
python -m pytest ml/src/services/test_validation_service.py -v

# Start API server
cd ml && python -m src.api.server

# Test API endpoint
curl http://localhost:8000/api/validation/unified/AAPL/BULLISH

# Start dashboard
cd ml && streamlit run src/dashboard/forecast_dashboard.py

# View API docs
http://localhost:8000/docs (Swagger UI)
```

---

## 📈 Progress Tracking

### Week 1
- [ ] Phase 0: Setup (Jan 21)
- [ ] Phase 1: Data Pipeline (Jan 22-23)
- [ ] Phase 2: API Integration (Jan 23-24)

### Week 2
- [ ] Phase 3: Dashboard (Jan 27-29)
- [ ] Phase 4: Forecast Pipeline (Jan 29-30)
- [ ] Phase 5: Streamlit Integration (Jan 30-31)

### Week 3
- [ ] Phase 6: Testing (Feb 3-4)
- [ ] Phase 7: Documentation & Deploy (Feb 4-5)

---

## ✅ Definition of Done

All of the following must be true:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] API endpoints tested with curl
- [ ] Dashboard renders all tabs correctly
- [ ] Validation metrics reconcile as expected
- [ ] Drift detection works (severity levels show)
- [ ] Multi-TF consensus shows weighted voting
- [ ] Retraining alerts trigger correctly
- [ ] Historical trend chart displays
- [ ] Export functionality works
- [ ] Documentation complete and accurate
- [ ] Code reviewed and approved
- [ ] Staging deployment successful
- [ ] Production deployment successful
- [ ] Monitor alerts configured
- [ ] Team trained on new features

---

## 🗣️ Questions?

**Q: Can I deploy incrementally?**  
A: Yes. Deploy validation_service + API first (Phase 1-2), then dashboard (Phase 3) separately.

**Q: What if live_predictions table doesn't exist?**  
A: Live score defaults to 0.50. You'll still see backtesting + walk-forward weighted score.

**Q: Should I update existing forecasts?**  
A: Only new forecasts include validation. Historical forecasts use defaults.

**Q: How do I roll back?**  
A: Revert to previous commit, restart dashboard. Validation optional, doesn't break forecast flow.

**Q: Can I disable validation during high-volume trading?**  
A: Yes, add feature flag: `ENABLE_VALIDATION=false` in `.env`

---

**Status**: Ready to start Phase 0  
**Next Step**: Verify existing validator code runs successfully
