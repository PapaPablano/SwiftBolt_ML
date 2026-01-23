# GitHub Workflows Deep Review
**Date**: January 23, 2026  
**Repository**: SwiftBolt_ML  
**Scope**: All active workflows against ML, SQL, and Data Accuracy standards

---

## Executive Summary

This review evaluates all GitHub Actions workflows against three critical standards:
1. **ML Pipeline Standards** - Data validation, walk-forward analysis, model monitoring
2. **SQL Optimization Patterns** - N+1 queries, batch operations, indexing
3. **Data Accuracy Standards** - OHLC validation, cross-source validation, quality checks

**Overall Assessment**: ⚠️ **Needs Improvement** - Several critical gaps identified

---

## 🔍 ML Pipeline Standards Compliance

### Standard Requirements
Based on `ml-pipeline-standards.mdc`:
- ✅ Data validation at ingestion (OHLC consistency, outliers)
- ✅ Walk-forward analysis for time-series
- ✅ Model monitoring and drift detection
- ✅ Feature engineering documentation
- ✅ Error handling with graceful degradation

### Workflow Analysis

#### ✅ `ml-orchestration.yml` - **GOOD**
**Compliance Score**: 8/10

**Strengths**:
- ✅ Runs unified validation (line 253-317)
- ✅ Checks data staleness (line 328-351)
- ✅ Data quality validation (line 353-365)
- ✅ Model evaluation feedback loop (line 247-251)
- ✅ Drift detection with thresholds (line 378)

**Gaps**:
- ❌ **Missing**: OHLC validation before ML training
  - **Issue**: No explicit OHLCValidator call before `forecast_job`
  - **Standard**: ML standards require validation at ingestion
  - **Fix**: Add validation step before `ml-forecast` job
  ```yaml
  - name: Validate OHLC data quality
    run: |
      cd ml
      python -c "
      from src.data.data_validator import OHLCValidator
      from src.data.supabase_db import db
      
      validator = OHLCValidator()
      for symbol in ['AAPL', 'NVDA', 'MSFT']:
          df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=252)
          df, result = validator.validate(df, fix_issues=False)
          if not result.is_valid:
              print(f'❌ {symbol}: {result.issues}')
              exit(1)
      print('✅ OHLC validation passed')
      "
  ```

- ⚠️ **Placeholder Data**: Unified validation uses hardcoded scores (line 277-285)
  - **Issue**: Not fetching real scores from database
  - **Standard**: Should use `ValidationService` to fetch actual metrics
  - **Fix**: Replace with actual service call
  ```python
  from src.services.validation_service import ValidationService
  service = ValidationService()
  result = service.get_live_validation(symbol, direction)
  ```

#### ⚠️ `intraday-ingestion.yml` - **PARTIAL**
**Compliance Score**: 6/10

**Strengths**:
- ✅ Quick validation after fetch (line 191-216)
- ✅ Checks data existence and freshness

**Gaps**:
- ❌ **Missing**: OHLC consistency validation
  - **Issue**: Only checks if data exists, not if it's valid
  - **Standard**: ML standards require OHLC relationship checks
  - **Fix**: Add OHLCValidator check
  ```yaml
  - name: Validate OHLC integrity
    run: |
      cd ml
      python -c "
      from src.data.data_validator import OHLCValidator
      from src.data.supabase_db import db
      
      validator = OHLCValidator()
      df = db.fetch_ohlc_bars('SPY', timeframe='m15', limit=100)
      df, result = validator.validate(df, fix_issues=False)
      if not result.is_valid:
          print(f'❌ OHLC validation failed: {result.issues}')
          exit(1)
      print('✅ OHLC integrity validated')
      "
  ```

- ❌ **Missing**: Outlier detection
  - **Issue**: No statistical outlier checks (Z-score > 4)
  - **Standard**: ML standards require outlier detection
  - **Fix**: Add to validation step

#### ❌ `daily-data-refresh.yml` - **POOR**
**Compliance Score**: 4/10

**Gaps**:
- ❌ **Missing**: Pre-ingestion validation
  - **Issue**: No validation before data is inserted
  - **Standard**: ML standards require validation at ingestion
  - **Fix**: Add validation step before backfill
  ```yaml
  - name: Validate data before ingestion
    run: |
      cd ml
      # Validate OHLC data from Alpaca before inserting
      python -c "
      from src.data.data_validator import OHLCValidator
      # Fetch sample and validate before bulk insert
      "
  ```

- ⚠️ **Post-hoc Validation Only**: Validation runs after data is already inserted (line 148-196)
  - **Issue**: Bad data may already be in database
  - **Standard**: Should validate before insertion
  - **Fix**: Move validation to pre-insertion step

- ❌ **Missing**: Gap detection before training
  - **Issue**: Gap detection runs but doesn't block ML training
  - **Standard**: ML standards require gap detection
  - **Fix**: Add gap detection as blocking step

#### ⚠️ `intraday-forecast.yml` - **PARTIAL**
**Compliance Score**: 5/10

**Gaps**:
- ❌ **Missing**: Data quality check before forecasting
  - **Issue**: No validation that ingested data is valid
  - **Standard**: ML standards require validation before model use
  - **Fix**: Add validation step

- ❌ **Missing**: Minimum bars check
  - **Issue**: No check for `MIN_BARS_FOR_TRAINING` (50 bars)
  - **Standard**: ML standards require minimum data threshold
  - **Fix**: Add check before forecast generation

---

## 🗄️ SQL Optimization Standards Compliance

### Standard Requirements
Based on `sql-optimization-patterns.mdc`:
- ✅ Eliminate N+1 queries (use JOINs or batch loading)
- ✅ Use batch operations (INSERT, UPDATE)
- ✅ Proper indexing strategies
- ✅ Avoid SELECT * (fetch only needed columns)
- ✅ Optimize pagination (cursor-based)

### Workflow Analysis

#### ⚠️ `ml-orchestration.yml` - **NEEDS IMPROVEMENT**
**Compliance Score**: 6/10

**Issues**:
- ⚠️ **Potential N+1**: Unified validation loops over symbols (line 274)
  - **Issue**: Each symbol may trigger separate DB queries
  - **Standard**: Should batch fetch all scores in one query
  - **Fix**: Use `ValidationService` which should batch queries
  ```python
  # Current (potentially N+1):
  for symbol in SYMBOLS:
      scores = get_scores(symbol)  # Separate query per symbol
  
  # Should be:
  all_scores = get_scores_batch(SYMBOLS)  # Single query
  ```

- ⚠️ **No Query Optimization**: Provider coverage check makes individual API calls (line 444-491)
  - **Issue**: Sequential API calls per timeframe
  - **Standard**: Should batch or parallelize
  - **Fix**: Use parallel execution or batch API calls

#### ⚠️ `intraday-ingestion.yml` - **NEEDS IMPROVEMENT**
**Compliance Score**: 5/10

**Issues**:
- ⚠️ **Sequential Processing**: Loops over timeframes sequentially (line 164-180)
  - **Issue**: Could be parallelized
  - **Standard**: SQL/batch operations should be parallel when possible
  - **Fix**: Use matrix strategy or parallel jobs

- ⚠️ **No Batch Validation**: Validates symbols one at a time (line 206-216)
  - **Issue**: N queries for N symbols
  - **Standard**: Should batch validate
  - **Fix**: Batch fetch and validate

#### ❌ `daily-data-refresh.yml` - **POOR**
**Compliance Score**: 4/10

**Issues**:
- ❌ **No Batch Optimization**: Matrix strategy processes timeframes separately (line 66-69)
  - **Issue**: Each timeframe runs in separate job (good for parallelization, but may cause N+1)
  - **Standard**: Should ensure batch operations within each job
  - **Fix**: Verify `alpaca_backfill_ohlc_v2.py` uses batch INSERTs

- ❌ **Missing**: No verification of batch operations
  - **Issue**: Can't confirm scripts use batch INSERTs
  - **Standard**: Should document/verify batch operations
  - **Fix**: Add comment or verification step

#### ✅ `intraday-forecast.yml` - **GOOD**
**Compliance Score**: 7/10

**Strengths**:
- ✅ Uses existing scripts that likely batch operations
- ✅ No obvious N+1 patterns

**Minor Issues**:
- ⚠️ Could verify batch operations in forecast job

---

## 📊 Data Accuracy Standards Compliance

### Standard Requirements
Based on `DATA_VALIDATION_STRATEGY.md` and codebase:
- ✅ OHLC consistency (High >= max(Open,Close), Low <= min(Open,Close))
- ✅ Price positivity (all prices > 0)
- ✅ Volume validation (volume >= 0)
- ✅ Gap detection (gaps > 3 ATR flagged)
- ✅ Outlier detection (Z-score > 4)
- ✅ Cross-source validation (optional but recommended)

### Workflow Analysis

#### ⚠️ `ml-orchestration.yml` - **PARTIAL**
**Compliance Score**: 6/10

**Strengths**:
- ✅ Data quality validation script (line 353-365)
- ✅ Staleness checks (line 328-351)

**Gaps**:
- ❌ **Missing**: OHLC consistency checks
  - **Issue**: No explicit OHLC relationship validation
  - **Standard**: Data accuracy requires OHLC consistency
  - **Fix**: Add OHLCValidator step

- ❌ **Missing**: Outlier detection
  - **Issue**: No Z-score analysis
  - **Standard**: Data accuracy requires outlier detection
  - **Fix**: Add outlier detection to validation

#### ❌ `intraday-ingestion.yml` - **POOR**
**Compliance Score**: 4/10

**Gaps**:
- ❌ **Missing**: OHLC consistency validation
  - **Issue**: Only checks data existence, not validity
  - **Standard**: Data accuracy requires OHLC checks
  - **Fix**: Add comprehensive OHLC validation

- ❌ **Missing**: Gap detection
  - **Issue**: No gap detection after ingestion
  - **Standard**: Data accuracy requires gap detection
  - **Fix**: Add gap detection step

- ❌ **Missing**: Outlier detection
  - **Issue**: No statistical outlier checks
  - **Standard**: Data accuracy requires outlier detection
  - **Fix**: Add Z-score analysis

#### ❌ `daily-data-refresh.yml` - **POOR**
**Compliance Score**: 3/10

**Gaps**:
- ❌ **Missing**: Pre-insertion validation
  - **Issue**: No validation before data enters database
  - **Standard**: Data accuracy requires validation at ingestion
  - **Fix**: Add validation before backfill scripts run

- ⚠️ **Post-hoc Only**: Validation runs after insertion (line 148-196)
  - **Issue**: Bad data may already be stored
  - **Standard**: Should validate before insertion
  - **Fix**: Move validation earlier in pipeline

- ❌ **Missing**: OHLC consistency checks in validation
  - **Issue**: Gap detection doesn't check OHLC relationships
  - **Standard**: Data accuracy requires OHLC checks
  - **Fix**: Add OHLCValidator to validation step

#### ⚠️ `intraday-forecast.yml` - **PARTIAL**
**Compliance Score**: 5/10

**Gaps**:
- ❌ **Missing**: Data quality validation before forecasting
  - **Issue**: Assumes ingested data is valid
  - **Standard**: Data accuracy requires validation before use
  - **Fix**: Add validation step

---

## 🔄 Competing Logic Analysis

### Duplicate Functionality

#### 1. **Data Validation**
- `ml-orchestration.yml` (line 353-365): Runs `validate_data_quality.sh`
- `daily-data-refresh.yml` (line 167-186): Runs `backfill_with_gap_detection.py`
- **Issue**: Two different validation approaches
- **Fix**: Standardize on one validation method or clearly separate concerns

#### 2. **Backfill Operations**
- `daily-data-refresh.yml`: Main backfill workflow
- `intraday-ingestion.yml`: Intraday backfill (line 170)
- **Issue**: Both use `alpaca_backfill_ohlc_v2.py` but with different parameters
- **Status**: ✅ **OK** - Different use cases (daily vs intraday)

#### 3. **Forecast Generation**
- `ml-orchestration.yml` (line 126-139): Nightly forecasts
- `intraday-forecast.yml` (line 145-171): Intraday forecasts
- **Issue**: Both generate forecasts but for different horizons
- **Status**: ✅ **OK** - Different horizons (daily vs intraday)

### Conflicting Schedules

#### 1. **Intraday Ingestion vs Daily Refresh**
- `intraday-ingestion.yml`: Every 15 min during market hours (line 22)
- `daily-data-refresh.yml`: Daily at 6:00 AM UTC (line 20)
- **Issue**: Both may update same timeframes (m15, h1)
- **Risk**: ⚠️ **Medium** - May cause race conditions or duplicate work
- **Fix**: Ensure idempotency in backfill scripts (use UPSERT)

#### 2. **ML Orchestration Triggers**
- `ml-orchestration.yml`: Triggers after `daily-data-refresh` (line 30-33)
- `ml-orchestration.yml`: Also runs on schedule at 4:00 UTC (line 36)
- **Issue**: May run twice if both trigger
- **Risk**: ⚠️ **Low** - Concurrency group prevents duplicates (line 54-56)
- **Status**: ✅ **OK** - Concurrency handling works

### Overlapping Responsibilities

#### 1. **Data Quality Monitoring**
- `ml-orchestration.yml`: Model health includes data quality (line 353-365)
- `daily-data-refresh.yml`: Validation job (line 148-196)
- **Issue**: Both check data quality but at different times
- **Fix**: Clarify separation:
  - `daily-data-refresh`: Pre-insertion validation
  - `ml-orchestration`: Post-insertion monitoring

#### 2. **Options Processing**
- `ml-orchestration.yml`: Options processing job (line 153-208)
- **Status**: ✅ **OK** - Single source of truth

---

## 🎯 Critical Issues Summary

### Priority 1: Critical (Fix Immediately)

1. **Missing OHLC Validation Before ML Training**
   - **Workflows**: `ml-orchestration.yml`, `intraday-forecast.yml`
   - **Impact**: High - Invalid data may train models
   - **Fix**: Add OHLCValidator step before forecast generation

2. **No Pre-Insertion Validation**
   - **Workflow**: `daily-data-refresh.yml`
   - **Impact**: High - Bad data enters database
   - **Fix**: Validate data before backfill scripts insert

3. **Placeholder Data in Unified Validation**
   - **Workflow**: `ml-orchestration.yml` (line 277-285)
   - **Impact**: High - Not using real validation scores
   - **Fix**: Use `ValidationService` to fetch actual scores

### Priority 2: High (Fix Soon)

4. **Missing Outlier Detection**
   - **Workflows**: `intraday-ingestion.yml`, `daily-data-refresh.yml`
   - **Impact**: Medium - Outliers may contaminate data
   - **Fix**: Add Z-score analysis to validation steps

5. **Potential N+1 Queries**
   - **Workflow**: `ml-orchestration.yml` (line 274)
   - **Impact**: Medium - Performance degradation
   - **Fix**: Batch fetch validation scores

6. **No Gap Detection in Intraday Workflow**
   - **Workflow**: `intraday-ingestion.yml`
   - **Impact**: Medium - Missing data not detected
   - **Fix**: Add gap detection after ingestion

### Priority 3: Medium (Fix When Possible)

7. **Sequential Processing**
   - **Workflow**: `intraday-ingestion.yml` (line 164-180)
   - **Impact**: Low - Slower execution
   - **Fix**: Parallelize timeframe processing

8. **Inconsistent Validation Methods**
   - **Workflows**: Multiple
   - **Impact**: Low - Maintenance burden
   - **Fix**: Standardize validation approach

---

## 📋 Recommended Fixes

### Fix 1: Add OHLC Validation to ML Orchestration

```yaml
# Add to ml-orchestration.yml, ml-forecast job, before forecast generation
- name: Validate OHLC data quality
  run: |
    cd ml
    python -c "
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.data.data_validator import OHLCValidator
    from src.data.supabase_db import db
    from src.scripts.universe_utils import get_symbol_universe
    
    validator = OHLCValidator()
    universe = get_symbol_universe()
    symbols = universe.get('symbols', []) or ['SPY', 'AAPL']
    
    validation_errors = []
    for symbol in symbols[:10]:  # Check top 10 symbols
        try:
            df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=252)
            if df.empty:
                continue
            df, result = validator.validate(df, fix_issues=False)
            if not result.is_valid:
                validation_errors.append(f'{symbol}: {result.issues}')
        except Exception as e:
            validation_errors.append(f'{symbol}: {str(e)}')
    
    if validation_errors:
        print('❌ OHLC validation failed:')
        for error in validation_errors:
            print(f'  - {error}')
        exit(1)
    
    print('✅ OHLC validation passed for all symbols')
    "
```

### Fix 2: Use Real Validation Scores

```yaml
# Replace ml-orchestration.yml line 253-317 with:
- name: Run unified validation
  run: |
    cd ml
    python -c "
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    from src.services.validation_service import ValidationService
    
    service = ValidationService()
    SYMBOLS = ['AAPL', 'NVDA', 'MSFT', 'TSLA', 'META', 'AMD', 'CRWD', 'GOOGL', 'AMZN']
    
    print('=' * 60)
    print('UNIFIED VALIDATION REPORT')
    print('=' * 60)
    
    drift_alerts = []
    for symbol in SYMBOLS:
        try:
            # Fetch actual validation from database
            result = service.get_live_validation(symbol, 'BULLISH')
            
            status = result.get_status_emoji()
            print(f'{status} {symbol}: {result.unified_confidence:.1%} confidence')
            print(f'   Drift: {result.drift_severity} ({result.drift_magnitude:.0%})')
            
            if result.drift_detected:
                drift_alerts.append({
                    'symbol': symbol,
                    'severity': result.drift_severity,
                    'magnitude': result.drift_magnitude
                })
        except Exception as e:
            print(f'⚠️ {symbol}: Error - {e}')
    
    if drift_alerts:
        print(f'⚠️ DRIFT ALERTS: {len(drift_alerts)} symbols')
    else:
        print('✅ No drift alerts')
    
    print('=' * 60)
    "
```

### Fix 3: Add Pre-Insertion Validation

```yaml
# Add to daily-data-refresh.yml, before backfill step
- name: Validate data before ingestion
  run: |
    cd ml
    # This would validate sample data from Alpaca before bulk insert
    # Implementation depends on alpaca_backfill_ohlc_v2.py structure
    echo "⚠️ Pre-insertion validation not yet implemented"
    echo "Recommendation: Add validation in alpaca_backfill_ohlc_v2.py"
```

### Fix 4: Add OHLC Validation to Intraday Ingestion

```yaml
# Add to intraday-ingestion.yml, after fetch step
- name: Validate OHLC integrity
  run: |
    cd ml
    python -c "
    from src.data.data_validator import OHLCValidator
    from src.data.supabase_db import db
    
    validator = OHLCValidator()
    symbols = ['SPY', 'AAPL']  # Sample validation
    
    for symbol in symbols:
        for tf in ['m15', 'h1']:
            df = db.fetch_ohlc_bars(symbol, timeframe=tf, limit=100)
            if df.empty:
                continue
            df, result = validator.validate(df, fix_issues=False)
            if not result.is_valid:
                print(f'❌ {symbol}/{tf}: {result.issues}')
                # Don't fail - just warn
                print('::warning::OHLC validation issues detected')
            else:
                print(f'✅ {symbol}/{tf}: Valid')
    "
```

---

## 📊 Compliance Matrix

| Workflow | ML Standards | SQL Standards | Data Accuracy | Overall |
|----------|-------------|---------------|---------------|---------|
| `ml-orchestration.yml` | 8/10 | 6/10 | 6/10 | **6.7/10** |
| `intraday-ingestion.yml` | 6/10 | 5/10 | 4/10 | **5.0/10** |
| `daily-data-refresh.yml` | 4/10 | 4/10 | 3/10 | **3.7/10** |
| `intraday-forecast.yml` | 5/10 | 7/10 | 5/10 | **5.7/10** |
| `ci.yml` | N/A | N/A | N/A | N/A (Testing) |
| `test-ml.yml` | N/A | N/A | N/A | N/A (Testing) |

**Average Score**: **5.3/10** - Needs significant improvement

---

## ✅ Action Items Checklist

### Immediate (Priority 1)
- [ ] Add OHLC validation before ML training in `ml-orchestration.yml`
- [ ] Replace placeholder data with real validation scores in `ml-orchestration.yml`
- [ ] Add pre-insertion validation to `daily-data-refresh.yml`
- [ ] Add OHLC validation to `intraday-ingestion.yml`

### Short-term (Priority 2)
- [ ] Add outlier detection to all ingestion workflows
- [ ] Fix potential N+1 queries in `ml-orchestration.yml`
- [ ] Add gap detection to `intraday-ingestion.yml`
- [ ] Standardize validation methods across workflows

### Long-term (Priority 3)
- [ ] Parallelize sequential processing in `intraday-ingestion.yml`
- [ ] Add cross-source validation (optional enhancement)
- [ ] Document batch operation usage in scripts
- [ ] Create shared validation action for reuse

---

## 📚 References

- ML Pipeline Standards: `.cursor/rules/ml-pipeline-standards.mdc`
- SQL Optimization: `~/.cursor/rules/sql-optimization-patterns.mdc`
- Data Validation Strategy: `docs/DATA_VALIDATION_STRATEGY.md`
- ML Pipeline Workflow: `.cursor/skills/ml-pipeline-workflow.mdc`

---

**Report Generated**: January 23, 2026  
**Next Review**: Recommended after implementing Priority 1 fixes
