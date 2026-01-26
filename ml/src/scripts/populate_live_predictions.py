"""
Populate live_predictions table from forecast_evaluations.

This script:
1. Reads recent forecast evaluations
2. Calculates accuracy scores per symbol/timeframe
3. Writes to live_predictions table for use by ValidationService

The live_predictions table is used by ValidationService to get live_score
for unified validation.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add ml to path
ml_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ml_dir))

from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Map horizons to timeframes
# Note: timeframe enum supports: m15, h1, h4, d1, w1, m1
HORIZON_TO_TIMEFRAME = {
    '1D': 'd1',      # Daily
    '5D': 'd1',      # 5 trading days
    '10D': 'd1',     # 10 trading days
    '20D': 'd1',     # 20 trading days
    '1W': 'w1',      # Weekly
    '1M': 'w1',      # Monthly -> use weekly as closest match
    '2M': 'w1',      # 2 months -> use weekly
    '3M': 'w1',      # 3 months -> use weekly
    '4M': 'w1',      # 4 months -> use weekly
    '5M': 'w1',      # 5 months -> use weekly
    '6M': 'w1',      # 6 months -> use weekly
    '15m': 'm15',    # 15-minute (intraday)
    '1h': 'h1',      # 1-hour (intraday)
    '4h': 'h4',      # 4-hour (intraday)
}

# Map labels to signals
LABEL_TO_SIGNAL = {
    'bullish': 'BULLISH',
    'bearish': 'BEARISH',
    'neutral': 'NEUTRAL',
}


def populate_live_predictions(days_back: int = 30) -> dict:
    """
    Populate live_predictions from recent forecast_evaluations.
    
    Args:
        days_back: How many days of evaluations to consider
        
    Returns:
        Dict with stats about what was populated
    """
    logger.info(f"Populating live_predictions from last {days_back} days of evaluations")
    
    cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
    
    # Fetch recent evaluations
    result = (
        db.client.table("forecast_evaluations")
        .select("symbol, horizon, predicted_label, direction_correct, evaluation_date")
        .gte("evaluation_date", cutoff_date)
        .order("evaluation_date", desc=True)
        .execute()
    )
    
    evaluations = result.data or []
    logger.info(f"Found {len(evaluations)} evaluations")
    
    if not evaluations:
        logger.warning("No evaluations found - live_predictions will remain empty")
        return {"evaluations_found": 0, "predictions_written": 0}
    
    # Group by symbol + horizon and calculate accuracy
    from collections import defaultdict
    symbol_horizon_stats = defaultdict(lambda: {"correct": 0, "total": 0, "latest_date": None})
    
    for eval_data in evaluations:
        symbol = eval_data.get("symbol")
        horizon = eval_data.get("horizon")
        if not symbol or not horizon:
            continue
            
        key = (symbol, horizon)
        symbol_horizon_stats[key]["total"] += 1
        if eval_data.get("direction_correct"):
            symbol_horizon_stats[key]["correct"] += 1
        
        eval_date = eval_data.get("evaluation_date")
        if eval_date:
            if symbol_horizon_stats[key]["latest_date"] is None:
                symbol_horizon_stats[key]["latest_date"] = eval_date
            elif eval_date > symbol_horizon_stats[key]["latest_date"]:
                symbol_horizon_stats[key]["latest_date"] = eval_date
    
    # Get symbol IDs
    symbols_result = (
        db.client.table("symbols")
        .select("id, ticker")
        .execute()
    )
    symbol_map = {row["ticker"]: row["id"] for row in (symbols_result.data or [])}
    
    # Write to live_predictions
    predictions_written = 0
    predictions_skipped = 0
    
    for (symbol, horizon), stats in symbol_horizon_stats.items():
        if stats["total"] < 3:  # Need at least 3 evaluations for meaningful accuracy
            predictions_skipped += 1
            continue
        
        symbol_id = symbol_map.get(symbol)
        if not symbol_id:
            logger.warning(f"Symbol {symbol} not found in symbols table")
            predictions_skipped += 1
            continue
        
        timeframe = HORIZON_TO_TIMEFRAME.get(horizon)
        if not timeframe:
            logger.debug(f"No timeframe mapping for horizon {horizon}, skipping")
            predictions_skipped += 1
            continue
        
        # Calculate accuracy
        accuracy = stats["correct"] / stats["total"]
        
        # Get most recent predicted label for signal
        latest_eval = next(
            (e for e in evaluations 
             if e.get("symbol") == symbol and e.get("horizon") == horizon 
             and e.get("evaluation_date") == stats["latest_date"]),
            None
        )
        
        if not latest_eval:
            predictions_skipped += 1
            continue
        
        predicted_label = latest_eval.get("predicted_label", "neutral").lower()
        signal = LABEL_TO_SIGNAL.get(predicted_label, "NEUTRAL")
        
        # Prepare prediction data
        prediction_data = {
            "symbol_id": symbol_id,
            "timeframe": timeframe,
            "signal": signal,
            "accuracy_score": round(accuracy, 4),
            "metadata": {
                "horizon": horizon,
                "evaluations_count": stats["total"],
                "correct_count": stats["correct"],
                "latest_evaluation_date": stats["latest_date"],
            },
            "prediction_time": stats["latest_date"] or datetime.now().isoformat(),
        }
        
        try:
            # Upsert (update if exists, insert if not)
            # Use symbol_id + timeframe as unique key
            db.client.table("live_predictions").upsert(
                prediction_data,
                on_conflict="symbol_id,timeframe"
            ).execute()
            
            predictions_written += 1
            logger.debug(
                f"Wrote {symbol}/{timeframe}: {accuracy:.1%} accuracy "
                f"({stats['correct']}/{stats['total']} correct)"
            )
        except Exception as e:
            logger.error(f"Error writing live prediction for {symbol}/{timeframe}: {e}")
            predictions_skipped += 1
    
    logger.info(
        f"Populated live_predictions: {predictions_written} written, "
        f"{predictions_skipped} skipped"
    )
    
    return {
        "evaluations_found": len(evaluations),
        "predictions_written": predictions_written,
        "predictions_skipped": predictions_skipped,
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate live_predictions from evaluations")
    parser.add_argument(
        "--days-back",
        type=int,
        default=30,
        help="How many days of evaluations to consider (default: 30)"
    )
    
    args = parser.parse_args()
    
    try:
        stats = populate_live_predictions(days_back=args.days_back)
        print(f"\n✅ Successfully populated live_predictions")
        print(f"   Evaluations found: {stats['evaluations_found']}")
        print(f"   Predictions written: {stats['predictions_written']}")
        print(f"   Predictions skipped: {stats['predictions_skipped']}")
        
        if stats['predictions_written'] == 0:
            print("\n⚠️  No predictions written. This could mean:")
            print("   - No forecast evaluations exist yet")
            print("   - Evaluations are too old (need recent evaluations)")
            print("   - Need at least 3 evaluations per symbol/horizon")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error populating live_predictions: {e}", exc_info=True)
        sys.exit(1)
