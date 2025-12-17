#!/bin/bash
# Rank options for all common watchlist symbols

set -e

# Change to ml directory
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# List of symbols to rank
SYMBOLS=(
    "AAPL"
    "MSFT"
    "GOOGL"
    "AMZN"
    "NVDA"
    "TSLA"
    "META"
    "SPY"
    "QQQ"
    "CRWD"
    "PLTR"
    "AMD"
)

echo "=========================================="
echo "Ranking options for ${#SYMBOLS[@]} symbols"
echo "=========================================="

for symbol in "${SYMBOLS[@]}"; do
    echo ""
    echo "------------------------------------------"
    echo "Processing: $symbol"
    echo "------------------------------------------"
    python src/options_ranking_job.py --symbol "$symbol" || echo "⚠️  Failed to rank $symbol (may not have OHLC data)"
done

echo ""
echo "=========================================="
echo "Ranking complete!"
echo "=========================================="
