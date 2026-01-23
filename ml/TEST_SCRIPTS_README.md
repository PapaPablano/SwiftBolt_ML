# FastAPI Test Scripts

These scripts allow you to test the FastAPI endpoints directly without running the SwiftUI app.

## Setup

Make sure the FastAPI server is running:
```bash
cd ml
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Test Walk-Forward Optimization

```bash
cd ml
python test_walk_forward.py --symbol AAPL --horizon 1D --forecaster baseline
```

Options:
- `--symbol`: Stock symbol (default: AAPL)
- `--horizon`: Forecast horizon - 1D, 1W, 1M, etc. (default: 1D)
- `--forecaster`: baseline or enhanced (default: baseline)
- `--timeframe`: d1, h1, etc. (default: d1)
- `--train-window`: Custom training window size (optional)
- `--test-window`: Custom test window size (optional)
- `--step-size`: Custom step size (optional)

## Test Backtest Strategy

```bash
cd ml
python test_backtest.py --symbol AAPL --strategy supertrend_ai --start-date 2025-01-22 --end-date 2026-01-22
```

Options:
- `--symbol`: Stock symbol (default: AAPL)
- `--strategy`: supertrend_ai, sma_crossover, or buy_and_hold (default: supertrend_ai)
- `--start-date`: Start date in YYYY-MM-DD format (default: 2025-01-22)
- `--end-date`: End date in YYYY-MM-DD format (default: 2026-01-22)
- `--timeframe`: d1, h1, etc. (default: d1)
- `--initial-capital`: Starting capital (default: 10000)

## Current Issues

### Walk-Forward Optimization
- **Status**: All 437 windows failing during training
- **Cause**: Training window (126 bars) too small to generate enough samples after 50-bar offset
- **Fix Applied**: Reduced minimum samples from 100 to 20 for walk-forward scenarios
- **Next Steps**: May need to increase training window size or reduce offset requirement

### Backtest Strategy
- **Status**: 0 trades generated, Sharpe ratio fixed (was invalid, now 0.0)
- **Cause**: Strategy function not finding matching rows or signal column mismatch
- **Fix Applied**: 
  - Fixed signal column name from 'signal' to 'supertrend_signal'
  - Improved date matching logic
  - Fixed Sharpe ratio calculation for edge cases (0 trades)
- **Next Steps**: Need to verify date matching works correctly

## Notes

- The server auto-reloads when you save Python files (no manual restart needed)
- Test scripts use a 5-minute timeout for long-running operations
- Check FastAPI logs for detailed error messages
