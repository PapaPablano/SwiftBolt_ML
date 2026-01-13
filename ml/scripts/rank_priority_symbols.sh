#!/bin/bash
# shellcheck shell=bash

# Options Ranking Scheduled Job
# Ranks options for priority symbols (watchlist + popular stocks)
# Run this hourly during market hours via cron

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment
# shellcheck source=../../venv/bin/activate
# shellcheck disable=SC1091
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Error: Virtual environment not found at venv/bin/activate"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    exit 1
fi

echo "========================================"
echo "Options Ranking - Priority Symbols Job"
echo "Started at: $(date)"
echo "========================================"

# Track statistics
total_processed=0
total_failed=0

# Get dynamic watchlist symbols from database
echo "Fetching watchlist symbols from database..."
mapfile -t WATCHLIST_SYMBOLS < <(
    python src/scripts/get_watchlist_symbols.py 2>/dev/null || echo ""
)

if [ ${#WATCHLIST_SYMBOLS[@]} -eq 0 ]; then
    echo "Warning: No watchlist symbols found, using defaults only"
fi

# Always rank these popular/liquid stocks (even if not in watchlist)
PRIORITY_SYMBOLS=(
    "AAPL"   # Apple
    "MSFT"   # Microsoft
    "TSLA"   # Tesla
    "SPY"    # S&P 500 ETF
    "QQQ"    # Nasdaq ETF
    "NVDA"   # Nvidia
    "AMZN"   # Amazon
    "GOOGL"  # Google
    "META"   # Meta
    "AMD"    # AMD
)

# Build unified symbol set
unique_symbols=()
if [ ${#WATCHLIST_SYMBOLS[@]} -gt 0 ] || [ ${#PRIORITY_SYMBOLS[@]} -gt 0 ]; then
    mapfile -t unique_symbols < <(
        {
            printf '%s\n' "${WATCHLIST_SYMBOLS[@]}"
            printf '%s\n' "${PRIORITY_SYMBOLS[@]}"
        } | awk '!seen[$0]++'
    )
fi

echo "Ranking ${#unique_symbols[@]} symbols:"
printf '  %s\n' "${unique_symbols[@]}"
echo "----------------------------------------"

# Process each symbol
for symbol in "${unique_symbols[@]}"; do
    echo ""
    echo "Processing $symbol..."

    if python src/options_ranking_job.py --symbol "$symbol"; then
        echo "✅ $symbol completed successfully"
        ((total_processed++))
    else
        echo "❌ $symbol failed"
        ((total_failed++))
    fi

    # Small delay to avoid API rate limits
    sleep 2
done

echo ""
echo "========================================"
echo "Options Ranking Job Complete"
echo "Finished at: $(date)"
echo "Processed: $total_processed"
echo "Failed: $total_failed"
echo "========================================"

exit 0
