"""
CLI script to run model training for a symbol/timeframe.
Called by FastAPI endpoint.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
ml_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ml_dir))

from src.data.supabase_db import SupabaseDatabase
from src.training.ensemble_training_job import train_ensemble_for_symbol_timeframe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_model_training(
    symbol: str,
    timeframe: str = "d1",
    lookback_days: int = 90,
) -> dict:
    """
    Run model training for a symbol/timeframe.
    
    Args:
        symbol: Stock ticker symbol
        timeframe: Timeframe (d1, h1, etc.)
        lookback_days: Number of days of historical data to use
        
    Returns:
        Dictionary with training results
    """
    try:
        db = SupabaseDatabase()
        
        logger.info(f"Training model for {symbol} ({timeframe}) with {lookback_days} days lookback")
        
        result = train_ensemble_for_symbol_timeframe(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days,
        )
        
        if "error" in result:
            return {
                "error": result["error"],
                "symbol": symbol,
                "timeframe": timeframe,
            }
        
        # Format response for API
        # The training function returns: validation_accuracy, weights, models, etc.
        # We need to extract sample counts from the database or calculate them
        
        # Get sample counts from database if available
        try:
            symbol_id = db.get_symbol_id(symbol)
            if symbol_id:
                # Query latest training run for sample counts
                training_runs = (
                    db.client.table("training_runs")
                    .select("n_training_samples, n_validation_samples")
                    .eq("symbol_id", symbol_id)
                    .eq("timeframe", timeframe)
                    .order("run_date", desc=True)
                    .limit(1)
                    .execute()
                )
                if training_runs.data:
                    train_samples = training_runs.data[0].get("n_training_samples", 0)
                    validation_samples = training_runs.data[0].get("n_validation_samples", 0)
                else:
                    train_samples = 0
                    validation_samples = 0
            else:
                train_samples = 0
                validation_samples = 0
        except Exception:
            train_samples = 0
            validation_samples = 0
        
        # Extract train accuracy from model performances (average of all models)
        train_accuracy = 0.0
        if "models" in result and result["models"]:
            train_accuracies = [
                perf.get("train_accuracy", 0.0)
                for perf in result["models"].values()
                if isinstance(perf, dict) and "train_accuracy" in perf
            ]
            if train_accuracies:
                train_accuracy = sum(train_accuracies) / len(train_accuracies)
        
        # Extract model hash from models_path if available
        model_hash = "unknown"
        if "models_path" in result:
            import hashlib
            model_path = result["models_path"]
            model_hash = hashlib.md5(model_path.encode()).hexdigest()[:8]
        
        # Extract feature count from models if available
        feature_count = 0
        if "models" in result and result["models"]:
            # Get feature count from first model's performance data
            first_model = list(result["models"].values())[0] if result["models"] else {}
            if isinstance(first_model, dict):
                feature_count = first_model.get("n_features", 0)
        
        # Get timestamp
        from datetime import datetime
        trained_at = datetime.utcnow().isoformat()
        
        # Format response for API
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "lookbackDays": lookback_days,
            "status": "success",
            "trainingMetrics": {
                "trainAccuracy": train_accuracy,
                "validationAccuracy": result.get("validation_accuracy", 0.0),
                "testAccuracy": 0.0,  # Not returned by training function (no test set in current implementation)
                "trainSamples": train_samples,
                "validationSamples": validation_samples,
                "testSamples": 0,  # Not returned by training function (no test set in current implementation)
            },
            "modelInfo": {
                "modelHash": model_hash,
                "featureCount": feature_count,
                "trainedAt": trained_at,
            },
            "ensembleWeights": result.get("weights", {}),
            "featureImportance": {},  # Not returned by training function
        }
        
    except Exception as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbol": symbol,
            "timeframe": timeframe,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ML model for a symbol")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    parser.add_argument("--lookback-days", type=int, default=90, help="Lookback days for training")
    
    args = parser.parse_args()
    
    result = run_model_training(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_days=args.lookback_days,
    )
    
    print(json.dumps(result, indent=2))
