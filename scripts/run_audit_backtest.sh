#!/usr/bin/env bash
# Run the backtest audit script (same flow as frontend: backend backtest + yfinance OHLC).
# Optionally load .env from repo root so SUPABASE_URL / SUPABASE_ANON_KEY / VITE_API_URL are set.
#
# Examples:
#   ./scripts/run_audit_backtest.sh --symbol AAPL --timeframe 1D --preset supertrend_ai
#   ./scripts/run_audit_backtest.sh --symbol AAPL --timeframe 1h --preset supertrend_ai --start 2024-02-22 --end 2025-02-22
#   ./scripts/run_audit_backtest.sh --symbol AAPL --timeframe 1D --strategy-id <UUID> --output-dir ./my_audit
#   ./scripts/run_audit_backtest.sh --symbol AAPL --timeframe 1D --strategy-name "Supertrend RSI"

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.env"
  set +a
fi

# Default 1 year if not provided
python3 scripts/audit_backtest_data.py "$@"
