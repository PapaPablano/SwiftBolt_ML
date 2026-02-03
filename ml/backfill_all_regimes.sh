#!/bin/bash
SYMBOLS="PG KO JNJ MRK MSFT AMGN BRK.B NVDA MU ALB"

echo "=== Backfilling 10 symbols across 6 regimes ==="

# 1. Full History
python scripts/backfill_ohlc_h4_alpaca.py --symbols $SYMBOLS --start 2020-01-01 --end 2026-02-02

# 2. Bear 2022
python scripts/backfill_ohlc_h4_alpaca.py --symbols $SYMBOLS --start 2022-01-01 --end 2022-12-31

# 3. Recovery 2023
python scripts/backfill_ohlc_h4_alpaca.py --symbols $SYMBOLS --start 2023-01-01 --end 2023-12-31

# 4. Bull 2024-2025
python scripts/backfill_ohlc_h4_alpaca.py --symbols $SYMBOLS --start 2024-01-01 --end 2025-12-31

# 5. Recent 2025-2026
python scripts/backfill_ohlc_h4_alpaca.py --symbols $SYMBOLS --start 2025-01-01 --end 2026-02-02

# 6. COVID 2020
python scripts/backfill_ohlc_h4_alpaca.py --symbols $SYMBOLS --start 2020-01-01 --end 2020-12-31

echo "=== COMPLETE: All regimes backfilled ==="
echo "Verify: SELECT symbol_id, COUNT(*) FROM ohlc_bars_h4_alpaca GROUP BY symbol_id;"
