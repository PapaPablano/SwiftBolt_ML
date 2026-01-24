# Forecast Consolidation Test Suite

This directory contains tests for validating the forecast consolidation effort.

## Test Files

- `test_forecast_consolidation.py` - Tests that unified forecast matches original

## Running Tests

```bash
# Run all tests
pytest tests/audit_tests/ -v

# Run specific test
pytest tests/audit_tests/test_forecast_consolidation.py::test_forecast_equivalence -v

# Run with coverage
pytest tests/audit_tests/ --cov=ml/src --cov-report=html
```

## Test Status

- **Phase 1**: Test infrastructure created ✅
- **Phase 2**: Will add full equivalence tests after unified_forecast_job.py is implemented
- **Phase 3**: Will add performance benchmarking tests

## Notes

- Tests use pytest for test discovery and execution
- Tests are designed to validate that consolidated code produces equivalent results
- Performance tests will compare processing times and cache hit rates
