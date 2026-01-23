#!/usr/bin/env python3
"""
CLI script to run walk-forward optimization for ML forecasters.
Returns JSON output for use by Edge Functions.

Usage:
    python run_walk_forward.py --symbol AAPL --horizon 1D --forecaster baseline

Forecasters:
    - baseline: BaselineForecaster (simple moving average)
    - enhanced: EnhancedForecaster (with technical indicators)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import SupabaseDatabase
from src.backtesting.walk_forward_tester import WalkForwardBacktester
from src.models.baseline_forecaster import BaselineForecaster
from src.models.enhanced_forecaster import EnhancedForecaster
from src.features.technical_indicators import add_technical_features

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs
logger = logging.getLogger(__name__)


def run_walk_forward(
    symbol: str,
    horizon: str = "1D",
    forecaster_type: str = "baseline",
    timeframe: str = "d1",
    train_window: int = None,
    test_window: int = None,
    step_size: int = None
) -> dict:
    """
    Run walk-forward optimization for a symbol/forecaster.
    
    Args:
        symbol: Stock ticker symbol
        horizon: Forecast horizon (1D, 1W, 1M, etc.)
        forecaster_type: Type of forecaster (baseline, enhanced)
        timeframe: Timeframe (d1, h1, etc.)
        train_window: Training window size (optional, uses horizon defaults)
        test_window: Test window size (optional, uses horizon defaults)
        step_size: Step size for rolling forward (optional, uses horizon defaults)
        
    Returns:
        Dictionary with walk-forward results
    """
    try:
        # Initialize database
        db = SupabaseDatabase()
        
        # Fetch OHLC bars
        df = db.fetch_ohlc_bars(symbol=symbol, timeframe=timeframe, limit=2000)
        
        if df.empty:
            return {
                "error": f"No OHLC data found for {symbol} ({timeframe})",
                "symbol": symbol,
                "horizon": horizon,
                "forecaster": forecaster_type
            }
        
        # Rename columns
        df = df.rename(columns={'ts': 'date'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # Add technical indicators if using enhanced forecaster
        if forecaster_type == "enhanced":
            df = add_technical_features(df)
        
        # Initialize forecaster
        if forecaster_type == "baseline":
            forecaster = BaselineForecaster()
        elif forecaster_type == "enhanced":
            forecaster = EnhancedForecaster()
        else:
            return {
                "error": f"Unknown forecaster type: {forecaster_type}",
                "symbol": symbol,
                "horizon": horizon,
                "forecaster": forecaster_type
            }
        
        # Initialize walk-forward backtester
        # Use horizon-optimized windows if not specified
        if train_window is None or test_window is None or step_size is None:
            backtester = WalkForwardBacktester(horizon=horizon)
        else:
            backtester = WalkForwardBacktester(
                train_window=train_window,
                test_window=test_window,
                step_size=step_size
            )
        
        # Validate data sufficiency before running backtest
        min_data_required = backtester.train_window + backtester.test_window
        if len(df) < min_data_required:
            return {
                "error": f"Insufficient data: {len(df)} bars (need at least {min_data_required} for train={backtester.train_window}, test={backtester.test_window})",
                "symbol": symbol,
                "horizon": horizon,
                "forecaster": forecaster_type
            }
        
        # Run walk-forward backtest
        try:
            metrics = backtester.backtest(df, forecaster, horizons=[horizon])
            
            # Use test periods list from backtester (now tracked during walk-forward loop)
            test_periods_list = getattr(metrics, 'test_periods_list', [])
            # Fallback: if not tracked, create dummy list
            if not test_periods_list:
                for i in range(metrics.test_periods):
                    test_periods_list.append({
                        "start": metrics.start_date.isoformat() if hasattr(metrics.start_date, 'isoformat') else str(metrics.start_date),
                        "end": metrics.end_date.isoformat() if hasattr(metrics.end_date, 'isoformat') else str(metrics.end_date)
                    })
        except ValueError as e:
            error_msg = str(e)
            if "No valid predictions generated" in error_msg:
                # Extract diagnostic info from error message if available
                # The improved error message from walk_forward_tester includes details
                return {
                    "error": error_msg,  # Use the detailed error message from walk_forward_tester
                    "symbol": symbol,
                    "horizon": horizon,
                    "forecaster": forecaster_type,
                    "data_bars": len(df),
                    "train_window": backtester.train_window,
                    "test_window": backtester.test_window,
                    "step_size": backtester.step_size
                }
            raise
        
        # Convert to JSON-serializable format
        return {
            "symbol": symbol.upper(),
            "horizon": horizon,
            "forecaster": forecaster_type,
            "timeframe": timeframe,
            "period": {
                "start": metrics.start_date.isoformat() if hasattr(metrics.start_date, 'isoformat') else str(metrics.start_date),
                "end": metrics.end_date.isoformat() if hasattr(metrics.end_date, 'isoformat') else str(metrics.end_date)
            },
            "windows": {
                "trainWindow": backtester.train_window,
                "testWindow": backtester.test_window,
                "stepSize": backtester.step_size,
                "testPeriods": test_periods_list
            },
            "metrics": {
                "accuracy": float(metrics.accuracy),
                "precision": float(metrics.precision),
                "recall": float(metrics.recall),
                "f1Score": float(metrics.f1_score),
                "sharpeRatio": float(metrics.sharpe_ratio),
                "sortinoRatio": float(metrics.sortino_ratio),
                "maxDrawdown": float(metrics.max_drawdown),
                "winRate": float(metrics.win_rate),
                "profitFactor": float(metrics.profit_factor),
                "totalTrades": int(metrics.total_trades),
                "winningTrades": int(metrics.winning_trades),
                "losingTrades": int(metrics.losing_trades),
                "avgWinSize": float(metrics.avg_win_size),
                "avgLossSize": float(metrics.avg_loss_size)
            },
            "barsUsed": len(df)
        }
        
    except Exception as e:
        logger.error(f"Error running walk-forward for {symbol}: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbol": symbol,
            "horizon": horizon,
            "forecaster": forecaster_type
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run walk-forward optimization for ML forecasters")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol")
    parser.add_argument("--horizon", default="1D", help="Forecast horizon (1D, 1W, 1M, etc.)")
    parser.add_argument("--forecaster", default="baseline", help="Forecaster type (baseline, enhanced)")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    parser.add_argument("--train-window", type=int, help="Training window size (optional)")
    parser.add_argument("--test-window", type=int, help="Test window size (optional)")
    parser.add_argument("--step-size", type=int, help="Step size (optional)")
    
    args = parser.parse_args()
    
    result = run_walk_forward(
        symbol=args.symbol,
        horizon=args.horizon,
        forecaster_type=args.forecaster,
        timeframe=args.timeframe,
        train_window=args.train_window,
        test_window=args.test_window,
        step_size=args.step_size
    )
    
    # Output JSON
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
