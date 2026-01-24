# Phase 3: Testing & Validation

This directory contains the test suite for validating the forecast consolidation effort.

## Test Suite Overview

### 1. Automated Tests (`test_forecast_consolidation.py`)

**Test Classes**:
- `TestForecastConsolidation` - Core functionality tests
- `TestPerformanceMetrics` - Performance measurement tests

**Test Coverage**:
- ✅ Unified processor basic operation
- ✅ All horizons processing (1D, 1W, 1M)
- ✅ Metrics collection and tracking
- ✅ Weight source precedence logging
- ✅ Feature cache behavior
- ✅ Error handling
- ✅ Database writes verification
- ✅ Processing time measurement
- ✅ Output structure validation

### 2. Comparison Scripts

**`compare_metrics.py`**:
- Compares baseline vs unified metrics
- Analyzes cache performance
- Measures processing time improvements
- Tracks weight source distribution
- Reports database write efficiency

**`benchmark_comparison.py`**:
- Parses log files for performance data
- Compares processing success rates
- Analyzes cache hit rates from logs
- Generates overall assessment score

### 3. Test Runner

**`run_phase3_tests.sh`**:
- Runs complete test suite
- Generates comparison reports
- Provides next steps guidance
- Creates summary of results

## Running Tests

### Quick Test (No Database Required)
```bash
# Run structure validation tests only
pytest tests/audit_tests/test_forecast_consolidation.py::test_unified_vs_original_structure -v
```

### Full Test Suite (Requires Database)
```bash
# Run all tests
pytest tests/audit_tests/test_forecast_consolidation.py -v
```

### Complete Phase 3 Validation
```bash
# Run everything including comparisons
./scripts/run_phase3_tests.sh
```

## Generating Baseline Data

### Step 1: Run Baseline Forecast
```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Single symbol (faster)
python ml/src/forecast_job.py --symbol AAPL > baseline_output.log 2>&1

# Full universe (complete)
python ml/src/forecast_job.py > baseline_output.log 2>&1
```

**Output**: `metrics/baseline/forecast_job_metrics_YYYYMMDD_HHMMSS.json`

### Step 2: Run Unified Forecast
```bash
# Single symbol (faster)
python ml/src/unified_forecast_job.py --symbol AAPL > unified_output.log 2>&1

# Full universe (complete)
python ml/src/unified_forecast_job.py > unified_output.log 2>&1
```

**Output**: `metrics/unified/unified_forecast_metrics.json`

### Step 3: Compare Results
```bash
# Compare metrics
python scripts/compare_metrics.py \
    metrics/baseline/forecast_job_metrics_*.json \
    metrics/unified/unified_forecast_metrics.json

# Compare performance logs
python scripts/benchmark_comparison.py \
    baseline_output.log \
    unified_output.log
```

## Expected Results

### Metrics Comparison
- **Cache Hit Rate**: Should improve from ~30% to 95%+
- **Processing Time**: Should reduce by 4-6x
- **DB Writes**: Should remain same or slightly reduced
- **Errors**: Should remain same or reduced

### Benchmark Comparison
- **Symbols Processed**: Should be equal
- **Cache Efficiency**: Should improve significantly
- **Error Rate**: Should remain same or improve
- **Overall Score**: 3/3 (Excellent)

## Test Status

### Phase 1 ✅
- [x] Test infrastructure created
- [x] Placeholder tests added

### Phase 2 ✅
- [x] Unified forecast job implemented
- [x] Test suite updated with real tests
- [x] Comparison scripts created

### Phase 3 ✅
- [x] Test suite complete
- [x] Comparison tools ready
- [x] Documentation complete

### Phase 4 (Next)
- [ ] Run tests with production data
- [ ] Validate equivalence
- [ ] Archive legacy code
- [ ] Deploy to production

## Troubleshooting

### Tests Fail with Database Errors
If you see `Symbol not found` or connection errors:
```bash
# Ensure database connection is configured
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"

# Or use .env file
cp .env.example .env
# Edit .env with your credentials
```

### Metrics Files Not Found
```bash
# Generate baseline metrics first
python ml/src/forecast_job.py --symbol AAPL

# Then generate unified metrics
python ml/src/unified_forecast_job.py --symbol AAPL

# Then run comparison
./scripts/run_phase3_tests.sh
```

### Redis Connection Errors
Redis is optional. To test without Redis:
```bash
# Unified forecast works without Redis
python ml/src/unified_forecast_job.py --symbol AAPL
# (Will use DB cache only)
```

To test with Redis:
```bash
# Start Redis locally
docker run -d -p 6379:6379 redis:7-alpine

# Run with Redis
python ml/src/unified_forecast_job.py \
    --redis-host localhost \
    --redis-port 6379 \
    --symbol AAPL
```

## Report Generation

After running tests, reports are saved to:
- `tests/audit_tests/metrics_comparison.txt`
- `tests/audit_tests/benchmark_comparison.txt`
- `tests/audit_tests/test_metrics.json` (temporary test metrics)

These can be included in the Phase 3 completion summary.

## Next Steps

1. ✅ Create test suite
2. ✅ Create comparison tools
3. ⏳ Run tests with production data
4. ⏳ Validate results
5. ⏳ Create final test report
6. ⏳ Proceed to Phase 4 (Deployment)

---

**Phase 3 Status**: ✅ Infrastructure Complete | ⏳ Validation Pending  
**Last Updated**: January 23, 2026
