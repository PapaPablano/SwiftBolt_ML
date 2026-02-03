#!/bin/bash
# Regime testing execution script.
#
# Usage:
#   ./run_regime_tests.sh          # Interactive: quick test → multi-regime → prompt for full
#   ./run_regime_tests.sh --full   # Non-interactive: run full regime tests only (20-30 min)
#   ./run_regime_tests.sh --quick  # Run only AAPL quick test, then exit

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/ml"

FULL_ONLY=0
QUICK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --full)  FULL_ONLY=1 ;;
    --quick) QUICK_ONLY=1 ;;
  esac
done

echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║           REGIME TESTING - EXECUTION SEQUENCE                          ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

if [[ "$FULL_ONLY" -eq 1 ]]; then
  echo "Running FULL regime tests (20-30 min). Results → regime_test_results.csv"
  echo "────────────────────────────────────────────────────────────────────────"
  python test_regimes_fixed.py
  echo ""
  echo "╔════════════════════════════════════════════════════════════════════════╗"
  echo "║                  REGIME TESTING COMPLETE!                              ║"
  echo "╠════════════════════════════════════════════════════════════════════════╣"
  echo "║  Results saved to: ml/regime_test_results.csv                         ║"
  echo "╚════════════════════════════════════════════════════════════════════════╝"
  exit 0
fi

# Step 1: Quick single stock test (2-3 minutes)
echo "STEP 1: Testing AAPL in crash_2022 regime..."
echo "────────────────────────────────────────────────────────────────────────"
python test_regimes_fixed.py --quick-test AAPL --regime crash_2022

[[ "$QUICK_ONLY" -eq 1 ]] && echo "Quick test done." && exit 0

echo ""
echo "────────────────────────────────────────────────────────────────────────"
read -p "Did AAPL test complete successfully? (y/n): " response

if [[ "$response" != "y" ]]; then
    echo "❌ Fix errors before continuing"
    exit 1
fi

echo ""
echo "✅ Single stock test passed!"
echo ""

# Step 2: Test one defensive stock (3 minutes)
echo "STEP 2: Testing PG (defensive) across all regimes..."
echo "────────────────────────────────────────────────────────────────────────"
python test_regimes_fixed.py --quick-test PG --regime crash_2022
python test_regimes_fixed.py --quick-test PG --regime recovery_2023
python test_regimes_fixed.py --quick-test PG --regime bull_2024

echo ""
echo "────────────────────────────────────────────────────────────────────────"
read -p "Did all 3 regime tests complete? (y/n): " response

if [[ "$response" != "y" ]]; then
    echo "❌ Fix errors before full run"
    exit 1
fi

echo ""
echo "✅ Multi-regime test passed!"
echo ""

# Step 3: Full regime testing (20-30 minutes)
echo "STEP 3: Running FULL regime testing on all stocks..."
echo "────────────────────────────────────────────────────────────────────────"
echo "This will take 20-30 minutes. Results will be saved to regime_test_results.csv"
echo ""
read -p "Ready to start full regime testing? (y/n): " response

if [[ "$response" == "y" ]]; then
    python test_regimes_fixed.py

    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════╗"
    echo "║                  REGIME TESTING COMPLETE!                              ║"
    echo "╠════════════════════════════════════════════════════════════════════════╣"
    echo "║  Results saved to: ml/regime_test_results.csv                         ║"
    echo "║  Next: review summary table and regime_test_results.csv               ║"
    echo "╚════════════════════════════════════════════════════════════════════════╝"
else
    echo "Skipping full run. Run full tests later with:"
    echo "  ./run_regime_tests.sh --full"
    echo "  # or: cd ml && python test_regimes_fixed.py"
fi
