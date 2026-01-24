# Manual Workflow Testing Guide
**Date**: January 23, 2026  
**Purpose**: Test actual production workflows with Priority 1 fixes

---

## ⚠️ Important Update

**Validation Logic Updated**: The OHLC validation step now distinguishes between:
- **Critical failures** (fails workflow): Invalid OHLC relationships, negative prices/volume
- **Warnings** (allows workflow to continue): Outliers and gaps (common in real market data)

This prevents false failures from legitimate market volatility.

---

## Overview

This guide helps you test the actual workflows that were modified with Priority 1 fixes:
1. **ML Orchestration** - OHLC validation before training + unified validation
2. **Intraday Ingestion** - OHLC integrity validation
3. **Daily Data Refresh** - OHLC validation after refresh
4. **Intraday Forecast** - OHLC validation before forecasting

---

## 🎯 Workflow 1: ML Orchestration

### What to Test
- ✅ OHLC validation before ML training (new step)
- ✅ Unified validation with real database scores (fixed step)

### How to Test

1. **Navigate to Workflow**:
   - Go to: https://github.com/PapaPablano/SwiftBolt_ML/actions/workflows/ml-orchestration.yml
   - Or: Actions → "ML Orchestration"

2. **Run Workflow**:
   - Click **"Run workflow"** button
   - Select branch: `fix/alpaca-cron-db-test` (or your branch)
   - Optionally select specific job: `ml-forecast` or `model-health`
   - Click **"Run workflow"**

3. **Monitor Execution**:

   **Job: `ml-forecast`**
   - Look for step: **"Validate OHLC data quality before training"**
   - **Expected Output**:
     ```
     ✅ SPY: OHLC validation passed (252 bars)
     ✅ AAPL: OHLC validation passed (252 bars)
     ...
     ✅ OHLC validation passed for all checked symbols
     ```
   - **If validation fails**: Workflow should stop with error message

   **Job: `model-health`**
   - Look for step: **"Run unified validation"**
   - **Expected Output**:
     ```
     📊 Running unified validation with real database scores...
     ============================================================
     UNIFIED VALIDATION REPORT (Real Database Scores)
     ============================================================
     ✅ AAPL: 47.2% confidence
        Drift: none (0%)
        Consensus: NEUTRAL
     ...
     ============================================================
     ✅ Unified validation complete
     ```
   - **Should NOT see**: "Using placeholder values" or hardcoded scores

4. **What to Verify**:
   - ✅ OHLC validation step executes before ML training
   - ✅ Validation fails workflow if critical issues found
   - ✅ Unified validation shows real confidence percentages
   - ✅ No "placeholder" or hardcoded values
   - ✅ Drift detection uses real database scores

---

## 🎯 Workflow 2: Intraday Ingestion

### What to Test
- ✅ OHLC integrity validation after data fetch

### How to Test

1. **Navigate to Workflow**:
   - Go to: https://github.com/PapaPablano/SwiftBolt_ML/actions/workflows/intraday-ingestion.yml
   - Or: Actions → "Intraday Ingestion"

2. **Run Workflow**:
   - Click **"Run workflow"** button
   - Select branch: `fix/alpaca-cron-db-test`
   - Optionally specify symbols: `SPY,AAPL` (comma-separated)
   - Click **"Run workflow"**

3. **Monitor Execution**:
   - Look for step: **"Validate OHLC integrity"**
   - **Expected Output**:
     ```
     ✅ SPY/m15: Valid (100 bars, latest: 2026-01-23 15:00:00)
     ✅ SPY/h1: Valid (100 bars, latest: 2026-01-23 15:00:00)
     ✅ AAPL/m15: Valid (100 bars, latest: 2026-01-23 15:00:00)
     ...
     ✅ OHLC integrity validated for all checked symbols/timeframes
     ```
   - **If issues found**: Should show warnings (non-blocking):
     ```
     ⚠️ OHLC validation issues detected (non-blocking):
       - SPY/m15: [issue description]
     ::warning::Some OHLC data quality issues detected. Review data quality.
     ```

4. **What to Verify**:
   - ✅ Validation step executes after data fetch
   - ✅ Shows validation results for each symbol/timeframe
   - ✅ Issues generate warnings (not failures)
   - ✅ Workflow continues even if warnings present

---

## 🎯 Workflow 3: Daily Data Refresh

### What to Test
- ✅ OHLC validation after data refresh

### How to Test

1. **Navigate to Workflow**:
   - Go to: https://github.com/PapaPablano/SwiftBolt_ML/actions/workflows/daily-data-refresh.yml
   - Or: Actions → "Daily Data Refresh"

2. **Run Workflow**:
   - Click **"Run workflow"** button
   - Select branch: `fix/alpaca-cron-db-test`
   - Optionally specify:
     - `full_backfill`: `false` (for faster test)
     - `symbol`: `AAPL` (to test single symbol)
   - Click **"Run workflow"**

3. **Monitor Execution**:
   - Look for step: **"Validate data quality and OHLC integrity"**
   - **Expected Output**:
     ```
     🔍 Validating data quality and OHLC integrity...
     [Gap detection output]
     
     🔍 Validating OHLC consistency...
     ✅ SPY/d1: OHLC valid
     ✅ SPY/h4: OHLC valid
     ✅ AAPL/d1: OHLC valid
     ...
     ✅ OHLC consistency validated
     ```
   - **If issues found**: Should show warnings:
     ```
     ⚠️ OHLC validation issues detected:
       - SPY/d1: [issue description]
     ::warning::OHLC data quality issues detected
     ```

4. **What to Verify**:
   - ✅ Validation step executes after data refresh
   - ✅ Checks both gap detection and OHLC consistency
   - ✅ Shows validation results for test symbols
   - ✅ Issues generate warnings (not failures)

---

## 🎯 Workflow 4: Intraday Forecast

### What to Test
- ✅ OHLC validation before forecasting

### How to Test

1. **Navigate to Workflow**:
   - Go to: https://github.com/PapaPablano/SwiftBolt_ML/actions/workflows/intraday-forecast.yml
   - Or: Actions → "Intraday Forecast"

2. **Run Workflow**:
   - Click **"Run workflow"** button
   - Select branch: `fix/alpaca-cron-db-test`
   - Click **"Run workflow"**

3. **Monitor Execution**:
   - Look for step: **"Validate OHLC data quality before forecasting"**
   - **Expected Output**:
     ```
     ✅ SPY/m15: Valid (100 bars)
     ✅ SPY/h1: Valid (100 bars)
     ✅ AAPL/m15: Valid (100 bars)
     ...
     ✅ OHLC validation passed for all checked symbols/timeframes
     ```
   - **If issues found**: Should show warnings (non-blocking):
     ```
     ⚠️ OHLC validation issues detected (non-blocking):
       - SPY/m15: [issue description]
     ::warning::Some OHLC data quality issues detected. Forecasts may be less reliable.
     ```

4. **What to Verify**:
   - ✅ Validation step executes before forecast generation
   - ✅ Checks intraday timeframes (m15, h1)
   - ✅ Issues generate warnings (not failures)
   - ✅ Workflow continues to generate forecasts

---

## 📊 Testing Checklist

### For Each Workflow

- [ ] **Workflow runs successfully**
- [ ] **Validation step appears in logs**
- [ ] **Validation output shows expected format**
- [ ] **No import errors**
- [ ] **No database connection errors**
- [ ] **Validation uses real data (not placeholders)**
- [ ] **Appropriate behavior on validation issues**:
  - ML Orchestration: Should fail on critical issues
  - Other workflows: Should warn but continue

---

## 🔍 What to Look For

### ✅ Success Indicators

1. **OHLC Validation**:
   - Shows "✅ [symbol]: OHLC validation passed"
   - Displays number of bars validated
   - Quality scores or validation status shown

2. **Unified Validation**:
   - Shows "UNIFIED VALIDATION REPORT (Real Database Scores)"
   - Displays actual confidence percentages (not 0.0 or 1.0)
   - Shows real drift severity (not "placeholder")
   - No "Using placeholder values" messages

3. **Workflow Execution**:
   - All steps complete
   - No errors or failures
   - Appropriate warnings for non-critical issues

### ⚠️ Warning Signs

1. **Import Errors**:
   - "ModuleNotFoundError: No module named 'src'"
   - **Fix**: Check Python path setup

2. **Database Errors**:
   - "Connection refused"
   - "Authentication failed"
   - **Fix**: Check GitHub secrets

3. **Placeholder Data**:
   - "Using placeholder values"
   - Hardcoded scores (0.0, 1.0, 0.5)
   - **Fix**: Verify ValidationService is being used

4. **Validation Not Running**:
   - Step doesn't appear in logs
   - Workflow skips validation
   - **Fix**: Check workflow YAML syntax

---

## 📝 Test Results Template

Document your test results:

```markdown
## Manual Workflow Test Results - [Date]

### ML Orchestration
- **Status**: ✅ PASSED / ❌ FAILED
- **OHLC Validation**: ✅ / ❌
- **Unified Validation**: ✅ / ❌
- **Issues Found**: [List any issues]

### Intraday Ingestion
- **Status**: ✅ PASSED / ❌ FAILED
- **OHLC Validation**: ✅ / ❌
- **Issues Found**: [List any issues]

### Daily Data Refresh
- **Status**: ✅ PASSED / ❌ FAILED
- **OHLC Validation**: ✅ / ❌
- **Issues Found**: [List any issues]

### Intraday Forecast
- **Status**: ✅ PASSED / ❌ FAILED
- **OHLC Validation**: ✅ / ❌
- **Issues Found**: [List any issues]

### Overall
- **All Workflows**: ✅ PASSED / ❌ FAILED
- **Notes**: [Any observations]
```

---

## 🚀 Quick Test Order

**Recommended order** (fastest to most comprehensive):

1. **Intraday Ingestion** (5-10 min) - Quickest, tests basic validation
2. **Intraday Forecast** (10-15 min) - Tests validation before forecasting
3. **Daily Data Refresh** (15-20 min) - Tests post-insertion validation
4. **ML Orchestration** (20-30 min) - Most comprehensive, tests both validations

**Total Time**: ~50-75 minutes for all workflows

---

## 📚 Related Documentation

- **Testing Summary**: `docs/TESTING_SUMMARY.md`
- **Implementation Details**: `docs/WORKFLOW_FIXES_IMPLEMENTED.md`
- **Deep Review**: `docs/GITHUB_WORKFLOWS_DEEP_REVIEW.md`

---

**Ready to test!** Start with the quickest workflow (Intraday Ingestion) and work your way up.

**Last Updated**: January 23, 2026
