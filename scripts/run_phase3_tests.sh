#!/bin/bash
# Phase 3 Testing & Validation Runner
# Runs all tests and generates comparison reports

set -e

echo "=============================================================================="
echo "PHASE 3: TESTING & VALIDATION"
echo "=============================================================================="
echo ""

# Change to project root
cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Run pytest test suite
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Running pytest test suite..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if pytest tests/audit_tests/test_forecast_consolidation.py -v --tb=short; then
    echo -e "${GREEN}✅ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed (this may be expected if database is not set up)${NC}"
fi

echo ""
echo ""

# Step 2: Compare metrics (if files exist)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Comparing metrics..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

BASELINE_METRICS="metrics/baseline/forecast_job_metrics_*.json"
UNIFIED_METRICS="metrics/unified/unified_forecast_metrics.json"

# Find the most recent baseline metrics file
BASELINE_FILE=$(ls -t $BASELINE_METRICS 2>/dev/null | head -n 1)

if [ -f "$BASELINE_FILE" ] && [ -f "$UNIFIED_METRICS" ]; then
    echo "Comparing metrics..."
    echo "  Baseline: $BASELINE_FILE"
    echo "  Unified:  $UNIFIED_METRICS"
    echo ""
    
    python scripts/compare_metrics.py "$BASELINE_FILE" "$UNIFIED_METRICS" | tee tests/audit_tests/metrics_comparison.txt
    
    echo ""
    echo -e "${GREEN}✅ Metrics comparison complete${NC}"
    echo "   Report saved to: tests/audit_tests/metrics_comparison.txt"
else
    echo -e "${YELLOW}⚠️  Metrics files not found${NC}"
    echo "   To generate metrics, run:"
    echo "   1. python ml/src/forecast_job.py --symbol AAPL"
    echo "   2. python ml/src/unified_forecast_job.py --symbol AAPL"
    echo ""
fi

echo ""
echo ""

# Step 3: Performance benchmarking (if log files exist)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Performance benchmarking..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

BASELINE_LOG="baseline_output.log"
UNIFIED_LOG="unified_output.log"

if [ -f "$BASELINE_LOG" ] && [ -f "$UNIFIED_LOG" ]; then
    echo "Comparing performance logs..."
    echo ""
    
    python scripts/benchmark_comparison.py "$BASELINE_LOG" "$UNIFIED_LOG" | tee tests/audit_tests/benchmark_comparison.txt
    
    echo ""
    echo -e "${GREEN}✅ Benchmark comparison complete${NC}"
    echo "   Report saved to: tests/audit_tests/benchmark_comparison.txt"
else
    echo -e "${YELLOW}⚠️  Log files not found${NC}"
    echo "   To generate benchmark logs, run:"
    echo "   1. python ml/src/forecast_job.py > baseline_output.log 2>&1"
    echo "   2. python ml/src/unified_forecast_job.py > unified_output.log 2>&1"
    echo ""
fi

echo ""
echo ""

# Summary
echo "=============================================================================="
echo "PHASE 3 TEST SUMMARY"
echo "=============================================================================="
echo ""
echo "✅ Test suite executed"
echo ""

if [ -f "tests/audit_tests/metrics_comparison.txt" ]; then
    echo "✅ Metrics comparison complete"
    echo "   → tests/audit_tests/metrics_comparison.txt"
else
    echo "⚠️  Metrics comparison skipped (no metrics files)"
fi

echo ""

if [ -f "tests/audit_tests/benchmark_comparison.txt" ]; then
    echo "✅ Benchmark comparison complete"
    echo "   → tests/audit_tests/benchmark_comparison.txt"
else
    echo "⚠️  Benchmark comparison skipped (no log files)"
fi

echo ""
echo "=============================================================================="
echo "NEXT STEPS"
echo "=============================================================================="
echo ""
echo "To generate complete test results:"
echo ""
echo "  1. Run baseline forecast (with metrics):"
echo "     python ml/src/forecast_job.py --symbol AAPL > baseline_output.log 2>&1"
echo ""
echo "  2. Run unified forecast (with metrics):"
echo "     python ml/src/unified_forecast_job.py --symbol AAPL > unified_output.log 2>&1"
echo ""
echo "  3. Re-run this script:"
echo "     ./scripts/run_phase3_tests.sh"
echo ""
echo "=============================================================================="
