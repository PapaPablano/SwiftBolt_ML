#!/usr/bin/env bash
#
# Wrapper: run sentiment backfill (7 days) then execute the given ML command.
# Use when you want backfill + command in one call (e.g. cron, manual runs).
#
# The benchmark and unified_forecast_job already run backfill automatically;
# use this script only for other ML commands that need fresh sentiment.
#
# Usage:
#   ./scripts/run_ml_with_sentiment_backfill.sh python -m src.unified_forecast_job
#   ./scripts/run_ml_with_sentiment_backfill.sh --symbols AAPL,NVDA python ml/benchmark_simplified_features.py --skip-sentiment-backfill
#
# Environment: SUPABASE_URL, SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set.
# Symbols: defaults to SWIFTBOLT_SYMBOLS if set, else AAPL,MSFT,NVDA,TSLA,SPY.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ML_DIR="$REPO_ROOT/ml"

SYMBOLS="${SWIFTBOLT_SYMBOLS:-AAPL,MSFT,NVDA,TSLA,SPY}"
DAYS=7

cd "$ML_DIR"
echo "Running sentiment backfill ($DAYS days) for $SYMBOLS..."
python backfill_sentiment.py --symbols "$SYMBOLS" --days "$DAYS" --delay 0.5 || echo "Backfill skipped or failed"
echo ""
echo "Running: $*"
exec "$@"
