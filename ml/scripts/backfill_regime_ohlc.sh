#!/usr/bin/env bash
# Backfill daily OHLC (d1) from Alpaca to cover regime periods used by pipeline_audit and test_regimes_fixed.
#
# Regime periods that need coverage:
#   crash_2022:  2022-03-01 to 2022-10-31
#   recovery_2023: 2022-11-01 to 2023-12-31
#   bull_2024:   2024-01-01 to 2024-12-31
#
# This script backfills 2022-01-01 through 2024-02-01 so existing data (from ~2024-02-02) is not duplicated.
#
# Usage:
#   cd ml && ./scripts/backfill_regime_ohlc.sh
# Custom range: cd ml && python scripts/backfill_ohlc_d1_alpaca.py --start 2022-01-01 --end 2024-02-01
#
# Requires: ALPACA_API_KEY, ALPACA_API_SECRET, SUPABASE_URL, SUPABASE_KEY (e.g. in .env)

set -e
cd "$(dirname "$0")/.."
START="2022-01-01"
END="2024-02-01"

echo "Regime OHLC backfill: $START → $END (d1, Alpaca → ohlc_bars_v2)"
python scripts/backfill_ohlc_d1_alpaca.py --start "$START" --end "$END"
echo "Done. Run pipeline_audit.py --section 1 to verify regime coverage."
