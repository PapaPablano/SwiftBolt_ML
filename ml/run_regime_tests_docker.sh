#!/bin/bash
# Run Regime Testing Inside Docker Container
# This script can be executed from the host or inside the container

set -e

echo "========================================"
echo "SwiftBolt ML - Regime Testing"
echo "========================================"
echo ""

# Check if we're inside Docker or running from host
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container..."
    PYTHON_CMD="/app/venv/bin/python"
    SCRIPT_PATH="/app/scripts/run_regime_testing.py"
else
    echo "Running from host..."
    ML_DIR="$(cd "$(dirname "$0")" && pwd)"
    # Prefer Docker if container has the script (image built with scripts/run_regime_testing.py)
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "swiftbolt-ml-backend"; then
        if docker exec swiftbolt-ml-backend test -f /app/scripts/run_regime_testing.py 2>/dev/null; then
            echo "Executing in Docker container..."
            docker exec swiftbolt-ml-backend /app/venv/bin/python /app/scripts/run_regime_testing.py "$@"
            exit 0
        fi
        echo "⚠️  run_regime_testing.py not in container (rebuild image to use Docker: docker-compose build backend)"
        echo "Running from host instead..."
    else
        echo "Docker container 'swiftbolt-ml-backend' not running; running from host."
    fi
    cd "$ML_DIR" && python test_regimes_FINAL.py "$@"
    exit 0
fi

# Parse arguments
OUTPUT_FILE="/app/results/regime_test_results_$(date +%Y%m%d_%H%M%S).csv"
REGIME=""
SYMBOL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --regime)
            REGIME="$2"
            shift 2
            ;;
        --symbol)
            SYMBOL="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --quick-test)
            SYMBOL="$2"
            REGIME="crash_2022"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--regime REGIME] [--symbol SYMBOL] [--output FILE] [--quick-test SYMBOL]"
            exit 1
            ;;
    esac
done

# Build command
CMD="$PYTHON_CMD $SCRIPT_PATH --output $OUTPUT_FILE"

if [ -n "$REGIME" ]; then
    CMD="$CMD --regime $REGIME"
fi

if [ -n "$SYMBOL" ]; then
    CMD="$CMD --symbol $SYMBOL"
fi

echo "Executing: $CMD"
echo ""

# Run the test
eval $CMD

echo ""
echo "========================================"
echo "✅ Regime testing complete!"
echo "Results saved to: $OUTPUT_FILE"
echo "========================================"
