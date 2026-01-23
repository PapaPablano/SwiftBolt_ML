# Quick Start Testing Guide
**Date**: January 23, 2026  
**Purpose**: Fast testing guide for workflow validation fixes

---

## 🚀 Quick Test (5 minutes)

### Step 1: Test Locally (Recommended First) ✅ **PASSED**

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Test all components
python scripts/test_workflow_validation.py --test-type all

# Or test individually
python scripts/test_workflow_validation.py --test-type ohlc
python scripts/test_workflow_validation.py --test-type service
python scripts/test_workflow_validation.py --test-type integration
```

**Result**: ✅ All local tests PASSED (January 23, 2026)
- OHLC Validator: ✅ Working correctly (detects outliers in real data)
- ValidationService: ✅ Import fixed, async methods working
- Integration: ✅ Workflow validation steps execute correctly

---

### Step 2: Test in GitHub Actions

1. Go to **GitHub Actions** tab
2. Select **"Test Workflow Fixes"** workflow
3. Click **"Run workflow"**
4. Select **test-type: `all`**
5. Click **"Run workflow"**

**Expected**: All jobs should pass ✅

---

### Step 3: Test Actual Workflows

#### Test ML Orchestration

1. Go to **GitHub Actions** → **ML Orchestration**
2. Click **"Run workflow"**
3. Select:
   - `job_filter`: `ml-forecast`
   - `symbol`: (leave empty)
4. Click **"Run workflow"**
5. Watch for step: **"Validate OHLC data quality before training"**

**Expected**: 
- ✅ Step executes
- ✅ Shows validation results
- ✅ Workflow continues if validation passes

---

#### Test Unified Validation

1. Same workflow, select:
   - `job_filter`: `model-health`
2. Watch for step: **"Run unified validation"**

**Expected**:
- ✅ Uses real database scores (not placeholders)
- ✅ Shows actual confidence percentages
- ✅ No "placeholder values" messages

---

## ✅ Success Criteria

### OHLC Validation ✅ **PASSED**
- [x] Validator imports without errors
- [x] Validates real database data
- [x] Detects invalid OHLC relationships
- [x] Shows quality scores
- [x] Handles outliers appropriately (warnings, not failures)

### ValidationService ✅ **PASSED**
- [x] Service imports without errors (fixed import issue)
- [x] Async methods work
- [x] Fetches real scores from database
- [x] Returns UnifiedPrediction objects
- [x] Handles missing data gracefully

### Integration ✅ **PASSED**
- [x] Workflow steps execute
- [x] No import errors
- [x] Real data used (not placeholders)
- [x] Validation errors handled correctly

---

## 🐛 Quick Troubleshooting

**"ModuleNotFoundError"**:
```bash
cd ml
python -c "from src.data.data_validator import OHLCValidator; print('OK')"
```

**"Async/await errors"**:
- Check Python version: `python --version` (need 3.7+)
- Verify asyncio.run() is used

**"Database connection errors"**:
- Check `.env` file exists in `ml/` directory
- Verify `SUPABASE_URL` and `SUPABASE_KEY` are set

---

## 📚 Full Documentation

- **Complete Testing Guide**: `docs/TESTING_WORKFLOW_FIXES.md`
- **Implementation Details**: `docs/WORKFLOW_FIXES_IMPLEMENTED.md`

---

---

## 🎉 Test Results (January 23, 2026)

**Status**: ✅ **ALL TESTS PASSED**

**Local Test Run**:
```
OHLC: ✅ PASSED
SERVICE: ✅ PASSED
INTEGRATION: ✅ PASSED
✅ All tests PASSED
```

**Key Findings**:
- ✅ OHLC Validator working correctly (detects outliers and gaps in real data)
- ✅ ValidationService import fixed and working
- ✅ Unified validation uses real database scores (47.2% confidence for test symbols)
- ⚠️ Some database schema columns missing - handled gracefully with fallbacks

**Next**: Run GitHub Actions test workflow to verify in CI environment

---

**Last Updated**: January 23, 2026
