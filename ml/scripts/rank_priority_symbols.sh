#!/bin/bash

# Options Ranking Scheduled Job
# Ranks options for priority symbols (watchlist + popular stocks)
# Run this hourly during market hours via cron

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment
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
watchlist_symbols=$(python src/scripts/get_watchlist_symbols.py 2>/dev/null || echo "")

if [ -z "$watchlist_symbols" ]; then
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

# Combine watchlist and priority symbols, remove duplicates
all_symbols=()
for symbol in $watchlist_symbols; do
    all_symbols+=("$symbol")
done
for symbol in "${PRIORITY_SYMBOLS[@]}"; do
    all_symbols+=("$symbol")
done

# Remove duplicates using simpler method
unique_symbols=($(printf "%s\n" "${all_symbols[@]}" | sort -u))

echo "Ranking ${#unique_symbols[@]} symbols: ${unique_symbols[*]}"
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
