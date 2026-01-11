#!/bin/bash
# Backfill AAPL for all timeframes
# Run from: /Users/ericpeterson/SwiftBolt_ML/ml

set -e

echo "🔄 Starting AAPL backfill for all timeframes..."
echo ""

# Array of timeframes
timeframes=("m15" "h1" "h4" "d1" "w1")

for tf in "${timeframes[@]}"; do
    echo "📊 Backfilling $tf timeframe..."
    python src/scripts/alpaca_backfill_ohlc_v2.py --symbol AAPL --timeframe "$tf" --force
    echo "✅ Completed $tf"
    echo ""
    sleep 2  # Small delay between runs
done

echo "🎉 All timeframes backfilled!"
echo ""
echo "Run this to verify:"
echo "psql \$DATABASE_URL -c \"SELECT timeframe, MAX(ts) as newest_bar, COUNT(*) as bars FROM ohlc_bars_v2 WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL') GROUP BY timeframe ORDER BY timeframe;\""
