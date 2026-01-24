# Testing Workflow Fixes Guide
**Date**: January 23, 2026  
**Purpose**: Guide for testing the validation fixes implemented in GitHub workflows

---

## Overview

This guide provides instructions for testing the Priority 1 fixes implemented in:
- `ml-orchestration.yml`
- `intraday-ingestion.yml`
- `daily-data-refresh.yml`
- `intraday-forecast.yml`

---

## 🧪 Test Methods

### Method 1: Local Python Script (Recommended First)

**Script**: `scripts/test_workflow_validation.py`

**Run all tests**:
```bash
cd /Users/ericpeterson/SwiftBolt_ML
python scripts/test_workflow_validation.py --test-type all
```

**Run specific tests**:
```bash
# Test OHLC Validator only
python scripts/test_workflow_validation.py --test-type ohlc

# Test ValidationService only
python scripts/test_workflow_validation.py --test-type service

# Test integration
python scripts/test_workflow_validation.py --test-type integration
```

**What it tests**:
- ✅ OHLC Validator import and functionality
- ✅ OHLC Validator edge cases (invalid data)
- ✅ ValidationService import and async methods
- ✅ Real database queries
- ✅ Workflow validation step integration

---

### Method 2: GitHub Actions Test Workflow

**Workflow**: `.github/workflows/test-workflow-fixes.yml`

**How to run**:
1. Go to GitHub Actions tab
2. Select "Test Workflow Fixes" workflow
3. Click "Run workflow"
4. Choose test type:
   - `all` - Run all tests
   - `ohlc-validation` - Test OHLC Validator
   - `validation-service` - Test ValidationService
   - `integration` - Test integration

**What it tests**:
- Same as local script but in GitHub Actions environment
- Verifies workflows can access required modules
- Tests in production-like environment

---

### Method 3: Manual Workflow Testing

#### Test 1: ML Orchestration OHLC Validation

**Workflow**: `ml-orchestration.yml`  
**Job**: `ml-forecast`

**Steps**:
1. Go to GitHub Actions
2. Run `ML Orchestration` workflow manually
3. Select `job_filter: ml-forecast`
4. Watch for step: "Validate OHLC data quality before training"
5. Verify:
   - ✅ Step executes without errors
   - ✅ Shows validation results for symbols
   - ✅ Fails if critical issues detected

**Expected Output**:
```
✅ SPY: OHLC validation passed (252 bars)
✅ AAPL: OHLC validation passed (252 bars)
...
✅ OHLC validation passed for all checked symbols
```

**If validation fails**:
```
❌ AAPL: High < max(Open,Close) in 5 rows
::error::OHLC data quality issues detected. ML training may produce unreliable results.
```

---

#### Test 2: ML Orchestration Unified Validation

**Workflow**: `ml-orchestration.yml`  
**Job**: `model-health`

**Steps**:
1. Run `ML Orchestration` workflow
2. Select `job_filter: model-health`
3. Watch for step: "Run unified validation"
4. Verify:
   - ✅ Uses real database scores (not placeholders)
   - ✅ Shows actual confidence scores
   - ✅ Detects drift if present

**Expected Output**:
```
UNIFIED VALIDATION REPORT (Real Database Scores)
============================================================
✅ AAPL: 72.5% confidence
   Drift: none (0.0%)
   Consensus: BULLISH
...
✅ No drift alerts
```

**If using placeholders (BAD)**:
```
⚠️ Using placeholder values that trigger validation logic
```

---

#### Test 3: Intraday Ingestion OHLC Validation

**Workflow**: `intraday-ingestion.yml`  
**Job**: `ingest-data`

**Steps**:
1. Run `Intraday Ingestion` workflow manually
2. Watch for step: "Validate OHLC integrity"
3. Verify:
   - ✅ Validates OHLC consistency
   - ✅ Shows warnings for issues (non-blocking)
   - ✅ Continues workflow even with warnings

**Expected Output**:
```
✅ SPY/m15: Valid (100 bars, latest: 2026-01-23 16:00:00)
✅ SPY/h1: Valid (25 bars, latest: 2026-01-23 16:00:00)
...
✅ OHLC integrity validated for all checked symbols/timeframes
```

---

#### Test 4: Daily Data Refresh Validation

**Workflow**: `daily-data-refresh.yml`  
**Job**: `validate-data`

**Steps**:
1. Run `Daily Data Refresh` workflow
2. Watch for step: "Validate data quality and OHLC integrity"
3. Verify:
   - ✅ Runs gap detection
   - ✅ Validates OHLC consistency
   - ✅ Shows warnings for issues

**Expected Output**:
```
🔍 Validating data quality and OHLC integrity...
[Gap detection output]
...
✅ SPY/d1: OHLC valid
✅ AAPL/d1: OHLC valid
...
✅ OHLC consistency validated
```

---

#### Test 5: Intraday Forecast Validation

**Workflow**: `intraday-forecast.yml`  
**Job**: `intraday-forecast`

**Steps**:
1. Run `Intraday Forecast` workflow manually
2. Watch for step: "Validate OHLC data quality before forecasting"
3. Verify:
   - ✅ Validates before generating forecasts
   - ✅ Non-blocking (warnings only)

**Expected Output**:
```
✅ SPY/m15: Valid (100 bars)
✅ SPY/h1: Valid (25 bars)
...
✅ OHLC validation passed for all checked symbols/timeframes
```

---

## 🔍 Validation Checklist

### OHLC Validation Tests

- [ ] OHLC Validator imports successfully
- [ ] Validates OHLC consistency (High >= max(Open,Close))
- [ ] Detects invalid OHLC relationships
- [ ] Detects negative volume
- [ ] Detects zero/negative prices
- [ ] Calculates data quality score
- [ ] Works with real database data

### ValidationService Tests

- [ ] ValidationService imports successfully
- [ ] Async methods work correctly
- [ ] Fetches backtesting scores from database
- [ ] Fetches walk-forward scores from database
- [ ] Fetches live scores from database
- [ ] Fetches multi-timeframe scores
- [ ] Returns UnifiedPrediction with real data

### Integration Tests

- [ ] Workflow validation steps execute
- [ ] OHLC validation runs before ML training
- [ ] Unified validation uses real scores
- [ ] Validation errors fail workflows appropriately
- [ ] Warnings don't block workflows unnecessarily

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution**:
- Ensure you're running from the `ml/` directory
- Or set `PYTHONPATH`:
  ```bash
  export PYTHONPATH=/Users/ericpeterson/SwiftBolt_ML/ml:$PYTHONPATH
  ```

### Issue: "ValidationService.get_live_validation() returns placeholder data"

**Solution**:
- Check that database has actual validation data
- Verify `ml_model_metrics`, `rolling_evaluation`, `live_predictions` tables have data
- Check database connection in workflow

### Issue: "OHLC validation always passes even with bad data"

**Solution**:
- Verify `OHLCValidator.validate()` is being called with `fix_issues=False`
- Check that validation result is being checked: `if not result.is_valid`
- Review validation logic in `src/data/data_validator.py`

### Issue: "Async/await errors in workflow"

**Solution**:
- Ensure using `asyncio.run()` wrapper for async functions
- Check Python version (3.7+ required for asyncio.run)
- Verify ValidationService methods are properly async

---

## 📊 Expected Test Results

### Successful Test Run

```
🧪 Workflow Validation Fixes Test Suite
============================================================
🧪 Testing OHLC Validator...
============================================================

📊 Testing SPY...
  ✅ Fetched 100 bars
  ✅ Validation PASSED
     Quality score: 98.50%

📊 Testing AAPL...
  ✅ Fetched 100 bars
  ✅ Validation PASSED
     Quality score: 97.20%

============================================================
✅ All OHLC validation tests PASSED

🧪 Testing ValidationService...
============================================================
✅ ValidationService imported and instantiated

📊 Testing AAPL...
  ✅ Validation completed
     Unified confidence: 72.5%
     Drift severity: none
     Consensus: BULLISH

============================================================
✅ ValidationService tests completed

============================================================
📊 Test Summary
============================================================
OHLC: ✅ PASSED
SERVICE: ✅ PASSED
INTEGRATION: ✅ PASSED
============================================================
✅ All tests PASSED
```

---

## 🚀 Next Steps After Testing

1. **If all tests pass**:
   - ✅ Deploy to production
   - ✅ Monitor first production runs
   - ✅ Review workflow logs for any warnings

2. **If tests fail**:
   - ❌ Review error messages
   - ❌ Check database connectivity
   - ❌ Verify module imports
   - ❌ Fix issues and re-test

3. **After successful deployment**:
   - 📊 Monitor workflow runs for 1 week
   - 📊 Review validation results
   - 📊 Check for any false positives/negatives
   - 📊 Adjust validation thresholds if needed

---

## 📚 Related Documents

- **Implementation Summary**: `docs/WORKFLOW_FIXES_IMPLEMENTED.md`
- **Deep Review**: `docs/GITHUB_WORKFLOWS_DEEP_REVIEW.md`
- **Audit Report**: `docs/GITHUB_ACTIONS_AUDIT.md`

---

**Last Updated**: January 23, 2026  
**Status**: Ready for Testing
