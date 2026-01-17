#!/bin/bash
# shellcheck shell=bash
# Rank options for all common watchlist symbols
# Includes 7-day underlying history ingestion before ranking

set -e

# Change to ml directory
cd "$(dirname "$0")/.."

# Activate virtual environment
# shellcheck source=../venv/bin/activate
# shellcheck disable=SC1091
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
echo "Options Ranking Job - ${#SYMBOLS[@]} symbols"
echo "=========================================="

# Step 1: Refresh 7-day underlying history for all symbols
echo ""
echo "Step 1: Refreshing 7-day underlying history..."
echo "------------------------------------------"

python -c "
import asyncio
import sys
sys.path.insert(0, '.')

from src.data.alpaca_underlying_history import fetch_underlying_history_batch, get_client
from src.data.supabase_db import db

SYMBOLS = $( printf '%s\n' "${SYMBOLS[@]}" | python -c "import sys; print([s.strip() for s in sys.stdin if s.strip()])" )

async def refresh_underlying_history():
    '''Refresh 7-day underlying metrics for all symbols.'''
    client = get_client()

    for symbol in SYMBOLS:
        try:
            print(f'Fetching 7-day history for {symbol}...')
            metrics = await client.fetch_7day_metrics(symbol, 'd1')

            if metrics.bars_count > 0:
                # Get symbol_id
                try:
                    symbol_id = db.get_symbol_id(symbol)
                except Exception:
                    print(f'  ⚠️  Symbol {symbol} not found in database')
                    continue

                # Fetch bars and upsert
                bars_df = await client.fetch_bars(symbol, 'd1', lookback_days=7)
                if not bars_df.empty:
                    bars = bars_df.to_dict('records')
                    metrics_dict = {
                        'ret_7d': metrics.return_7d,
                        'vol_7d': metrics.volatility_7d,
                        'drawdown_7d': metrics.drawdown_7d,
                        'gap_count': metrics.gap_count,
                    }
                    count = db.upsert_underlying_history(
                        symbol_id, 'd1', bars, metrics_dict, 'alpaca'
                    )
                    print(f'  ✅ {symbol}: {count} bars, ret={metrics.return_7d:.2f}%')
            else:
                print(f'  ⚠️  {symbol}: No bars available')

        except Exception as e:
            print(f'  ❌ {symbol}: Error - {e}')

asyncio.run(refresh_underlying_history())
print('Underlying history refresh complete.')
" || echo "⚠️  Underlying history refresh failed (continuing with ranking)"

# Step 2: Rank options for each symbol
echo ""
echo "Step 2: Ranking options..."
echo "------------------------------------------"

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
