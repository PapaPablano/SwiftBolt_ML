"""
Run walk-forward validation for a symbol/horizon and output metrics.

Example:
  python ml/scripts/run_walk_forward.py --symbol AAPL --horizon 1D --limit 1400
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.walk_forward_tester import WalkForwardBacktester  # noqa: E402
from src.data.supabase_db import SupabaseDatabase  # noqa: E402
from src.models.baseline_forecaster import BaselineForecaster  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_walk_forward(
    symbol: str = "AAPL",
    horizon: str = "1D",
    forecaster_type: str = "baseline",
    timeframe: str = "d1",
    train_window: int = 100,
    test_window: int = 20,
    step_size: int = 10,
    limit: int = 1400,
) -> dict:
    """
    Wrapper function for walk-forward validation.

    Args:
        symbol: Stock ticker (e.g., AAPL)
        horizon: Forecast horizon (1D, 1W, 1M, etc.)
        forecaster_type: Type of forecaster ('baseline', 'ml', etc.)
        timeframe: OHLC timeframe (d1, h4, h1, m15, etc.)
        train_window: Training window size in bars
        test_window: Test window size in bars
        step_size: Step size for walk-forward (bars)
        limit: Max bars to fetch

    Returns:
        Dictionary with metrics and results
    """
    try:
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=limit)

        if df.empty:
            return {"error": f"No OHLC data found for {symbol} ({timeframe})"}

        backtester = WalkForwardBacktester(horizon=horizon)
        forecaster = BaselineForecaster()

        metrics = backtester.backtest(df, forecaster, horizons=[horizon])
        payload = metrics_to_dict(metrics, symbol, horizon, timeframe)
        payload["run_at"] = datetime.now().isoformat()
        payload["params"] = {
            "train_window": train_window,
            "test_window": test_window,
            "step_size": step_size,
        }

        return payload
    except Exception as e:
        logger.error(f"Error in run_walk_forward: {e}", exc_info=True)
        return {"error": str(e)}


def metrics_to_dict(metrics, symbol: str, horizon: str, timeframe: str) -> dict:
    return {
        "symbol": symbol,
        "horizon": horizon,
        "timeframe": timeframe,
        "accuracy": metrics.accuracy,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1_score": metrics.f1_score,
        "win_rate": metrics.win_rate,
        "sharpe_ratio": metrics.sharpe_ratio,
        "sortino_ratio": metrics.sortino_ratio,
        "max_drawdown": metrics.max_drawdown,
        "profit_factor": metrics.profit_factor,
        "total_trades": metrics.total_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "avg_win_size": metrics.avg_win_size,
        "avg_loss_size": metrics.avg_loss_size,
        "start_date": metrics.start_date.isoformat(),
        "end_date": metrics.end_date.isoformat(),
        "test_periods": metrics.test_periods,
        "test_periods_list": metrics.test_periods_list,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run walk-forward validation.")
    parser.add_argument("--symbol", default="AAPL", help="Ticker symbol")
    parser.add_argument("--horizon", default="1D", help="Forecast horizon (1D/1W/1M)")
    parser.add_argument("--timeframe", default="d1", help="OHLC timeframe (default d1)")
    parser.add_argument("--limit", type=int, default=1400, help="Max bars to fetch")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars(args.symbol, timeframe=args.timeframe, limit=args.limit)

    if df.empty:
        logger.error("No OHLC data found for %s (%s)", args.symbol, args.timeframe)
        return 1

    backtester = WalkForwardBacktester(horizon=args.horizon)
    forecaster = BaselineForecaster()

    logger.info(
        "Running walk-forward: symbol=%s horizon=%s timeframe=%s bars=%d",
        args.symbol,
        args.horizon,
        args.timeframe,
        len(df),
    )

    metrics = backtester.backtest(df, forecaster, horizons=[args.horizon])
    payload = metrics_to_dict(metrics, args.symbol, args.horizon, args.timeframe)
    payload["run_at"] = datetime.now().isoformat()

    output = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
