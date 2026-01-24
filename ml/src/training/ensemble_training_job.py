"""
Ensemble Training Job - Main orchestration script.
Trains ensemble models for all symbols and timeframes.
"""

import logging
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix

from config.settings import settings
from src.data.supabase_db import SupabaseDatabase
from src.training.data_preparation import (
    collect_training_data,
    create_labels,
    prepare_train_validation_split,
    select_features_for_training,
)
from src.training.model_training import ModelTrainer
from src.training.weight_optimizer import EnsembleWeightOptimizer

logger = logging.getLogger(__name__)

# Models directory
MODELS_DIR = Path(__file__).parent.parent.parent / "trained_models"
MODELS_DIR.mkdir(exist_ok=True)

# Timeframe configurations
TIMEFRAME_CONFIGS = {
    "m15": {"bars": 500, "horizon": 5, "threshold": 0.002},
    "h1": {"bars": 500, "horizon": 5, "threshold": 0.003},
    "h4": {"bars": 300, "horizon": 3, "threshold": 0.005},
    "d1": {"bars": 500, "horizon": 5, "threshold": 0.009},  # Optimized for SPY (0.9%), NVDA will use 2.8% in symbol-specific override
}

# Consistent label order for confusion matrices
LABEL_ORDER = ["BEARISH", "NEUTRAL", "BULLISH"]


def _confusion_matrix_str(
    y_true: pd.Series | list,
    y_pred: pd.Series | list,
    *,
    labels: list[str] = LABEL_ORDER,
) -> str:
    """Return a readable confusion matrix string.

    Rows = true label, Columns = predicted label.
    """
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    header = " " * 12 + " ".join(f"{l:>8}" for l in labels)
    lines = [header]

    for i, row_label in enumerate(labels):
        row = " ".join(f"{int(cm[i, j]):>8}" for j in range(len(labels)))
        lines.append(f"{row_label:>10} {row}")

    return "\n".join(lines)


def _prediction_distribution_pct(preds: list[str] | pd.Series) -> Dict[str, float]:
    s = pd.Series(list(preds))
    return (s.value_counts(normalize=True) * 100).round(1).to_dict()


def _log_classifier_diagnostics(
    name: str,
    *,
    y_true: pd.Series,
    y_pred: list[str] | pd.Series,
) -> float:
    """Log accuracy, prediction distribution, and confusion matrix for a classifier."""
    acc = float(accuracy_score(y_true, y_pred))
    dist = _prediction_distribution_pct(y_pred)

    logger.info(f"  {name} accuracy: {acc:.1%}")
    logger.info(f"  {name} prediction distribution (%): {dist}")
    logger.info(
        "  %s confusion matrix (rows=true, cols=pred):\n%s",
        name,
        _confusion_matrix_str(y_true, y_pred),
    )

    return acc
def train_ensemble_for_symbol_timeframe(
    db: SupabaseDatabase,
    symbol: str,
    timeframe: str,
    lookback_days: int = 90,
) -> Dict:
    """
    Train complete ensemble for a symbol/timeframe combination.
    
    Args:
        db: Database connection
        symbol: Ticker (e.g., "AAPL")
        timeframe: Timeframe identifier (e.g., "m15", "h1", "d1")
        lookback_days: Historical data window
    
    Returns:
        Training results dictionary
    """
    
    logger.info("=" * 80)
    logger.info(f"Training ensemble for {symbol}/{timeframe}")
    logger.info(f"Lookback: {lookback_days} days")
    logger.info("=" * 80)
    
    try:
        # Get timeframe config
        config = TIMEFRAME_CONFIGS.get(timeframe, {"bars": 500, "horizon": 5, "threshold": 0.002})
        
        # Step 1: Collect data
        logger.info("Step 1: Collecting training data...")
        data_map = collect_training_data(
            db=db,
            symbols=[symbol],
            timeframes={timeframe: config["bars"]},
            lookback_days=lookback_days,
        )
        
        if timeframe not in data_map or symbol not in data_map[timeframe]:
            logger.error(f"No data for {symbol}/{timeframe}")
            return {"error": f"No data for {symbol}/{timeframe}", "success": False}
        
        df = data_map[timeframe][symbol]
        
        if len(df) < 100:
            logger.warning(f"Insufficient  {len(df)} rows")
            return {"error": f"Insufficient  {len(df)} rows", "success": False}
        
        logger.info(f"  Collected {len(df)} bars")
        
        # Step 2: Create labels
        logger.info("Step 2: Creating labels...")
        features_raw, labels = create_labels(
            df,
            prediction_horizon_bars=config["horizon"],
            threshold=config["threshold"],
        )
        
        # Step 3: Select features
        logger.info("Step 3: Selecting features...")
        features = select_features_for_training(features_raw)
        
        logger.info(f"  Features shape: {features.shape}")
        logger.info(f"  Label distribution: {labels.value_counts().to_dict()}")
        
        # Step 4: Train/validation split
        logger.info("Step 4: Creating time-ordered train/validation split...")
        train_features, valid_features, train_labels, valid_labels = (
            prepare_train_validation_split(features, labels, train_fraction=0.7)
        )

        # Step 4b: Baseline diagnostics (majority-class baseline)
        logger.info("Step 4b: Baseline diagnostics...")
        majority_label = valid_labels.value_counts().idxmax()
        baseline_preds = [majority_label] * len(valid_labels)
        logger.info(f"  Validation majority label: {majority_label}")
        baseline_accuracy = _log_classifier_diagnostics(
            "Baseline", y_true=valid_labels, y_pred=baseline_preds
        )

        # Step 5: Train models
        logger.info("Step 5: Training individual models...")
        trainer = ModelTrainer(symbol, timeframe)

        model_perfs = trainer.train_all_models(
            train_features,
            train_labels,
            valid_features,
            valid_labels,
        )

        # Step 5b: Per-model diagnostics
        logger.info("Step 5b: Per-model validation diagnostics...")
        model_predictions = trainer.get_model_predictions(valid_features)
        per_model_validation_accuracy: Dict[str, float] = {}

        for model_name, preds in model_predictions.items():
            # Prefer recomputing accuracy from predictions for consistency
            acc = _log_classifier_diagnostics(
                model_name.upper(),
                y_true=valid_labels,
                y_pred=preds,
            )
            per_model_validation_accuracy[model_name] = acc

            # Also print the metrics reported by the trainer (if present)
            if model_name in model_perfs and "valid_accuracy" in model_perfs[model_name]:
                logger.info(
                    "  %s reported valid_accuracy: %.1f%%",
                    model_name.upper(),
                    float(model_perfs[model_name]["valid_accuracy"]) * 100,
                )

        # Step 6: Optimize ensemble weights
        logger.info("Step 6: Optimizing ensemble weights...")

        optimizer = EnsembleWeightOptimizer(alpha=1.0)
        weights = optimizer.optimize_weights(model_predictions, valid_labels)
        
        # Step 7: Calculate ensemble performance
        logger.info("Step 7: Calculating ensemble performance...")
        
        # Get predictions for all models
        ensemble_preds = []
        for i in range(len(valid_features)):
            weighted_score = 0.0
            for model_name in weights.keys():
                if model_name in model_predictions:
                    pred = model_predictions[model_name][i]
                    weight = weights[model_name]
                    pred_val = {"BEARISH": -1, "NEUTRAL": 0, "BULLISH": 1}.get(pred, 0)
                    weighted_score += weight * pred_val
            
            # Convert score to label
            if weighted_score > 0.33:
                ensemble_preds.append("BULLISH")
            elif weighted_score < -0.33:
                ensemble_preds.append("BEARISH")
            else:
                ensemble_preds.append("NEUTRAL")
        
        ensemble_accuracy = sum(
            p == a for p, a in zip(ensemble_preds, valid_labels)
        ) / len(valid_labels)

        logger.info(f"  Ensemble Validation Accuracy: {ensemble_accuracy:.1%}")
        logger.info("Step 7b: Ensemble diagnostics...")
        _log_classifier_diagnostics(
            "ENSEMBLE",
            y_true=valid_labels,
            y_pred=ensemble_preds,
        )
        logger.info(
            "  Ensemble vs baseline delta: %+0.1f%%",
            (ensemble_accuracy - baseline_accuracy) * 100,
        )
        
        # Step 8: Save models to disk
        logger.info("Step 8: Saving models to disk...")
        
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        model_file = MODELS_DIR / f"{symbol}_{timeframe}_{timestamp}.pkl"
        
        artifact = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": timestamp,
            "models": trainer.models,
            "weights": weights,
            "performances": model_perfs,
            "ensemble_accuracy": ensemble_accuracy,
            "config": config,
            "n_features": len(features.columns),
            "feature_names": features.columns.tolist(),
        }
        
        with open(model_file, "wb") as f:
            pickle.dump(artifact, f)
        
        logger.info(f"  Saved to {model_file}")
        
        # Step 9: Store performance in database
        logger.info("Step 9: Recording performance metrics...")
        
        try:
            # Get symbol_id
            symbol_response = (
                db.client.table("symbols")
                .select("id")
                .eq("ticker", symbol.upper())
                .single()
                .execute()
            )
            symbol_id = symbol_response.data["id"]
            
            db.client.table("training_runs").insert({
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "run_date": datetime.utcnow().isoformat(),
                "lookback_days": lookback_days,
                "n_training_samples": len(train_features),
                "n_validation_samples": len(valid_features),
                "ensemble_validation_accuracy": float(ensemble_accuracy),
                "model_performances": model_perfs,
                "weights": weights,
                "models_artifact_path": str(model_file),
            }).execute()
            
            logger.info("  Metrics stored in database")
        except Exception as e:
            logger.warning(f"Failed to store metrics: {e}")
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "models": model_perfs,
            "weights": weights,
            "validation_accuracy": ensemble_accuracy,
            "baseline_accuracy": baseline_accuracy,
            "per_model_validation_accuracy": per_model_validation_accuracy,
            "models_path": str(model_file),
            "success": True,
        }
        
    except Exception as e:
        logger.error(
            f"Training failed for {symbol}/{timeframe}: {e}",
            exc_info=True
        )
        return {"error": str(e), "success": False}


def train_all_timeframes_all_symbols(
    db: SupabaseDatabase,
    symbols: Optional[list] = None,
    timeframes: Optional[list] = None,
) -> Dict:
    """
    Full training pipeline: Train ensemble for all symbols × timeframes.
    
    Args:
        db: Database connection
        symbols: List of symbols to train (defaults to settings.symbols_to_process)
        timeframes: List of timeframes to train (defaults to all configured)
    
    Returns:
        Training results summary
    """
    
    logger.info("=" * 80)
    logger.info("FULL ENSEMBLE TRAINING RUN")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)
    
    if symbols is None:
        symbols = settings.symbols_to_process
    
    if timeframes is None:
        timeframes = list(TIMEFRAME_CONFIGS.keys())
    
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Timeframes: {timeframes}")
    
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbols": symbols,
        "timeframes": timeframes,
        "trained": {},
        "failed": {},
    }
    
    for symbol in symbols:
        results["trained"][symbol] = {}
        results["failed"][symbol] = {}
        
        for timeframe in timeframes:
            logger.info(f"\nTraining {symbol} / {timeframe}...")
            
            result = train_ensemble_for_symbol_timeframe(
                db, symbol, timeframe, lookback_days=90
            )
            
            if result.get("success", False):
                results["trained"][symbol][timeframe] = result
            else:
                results["failed"][symbol][timeframe] = result.get("error", "Unknown error")
    
    # Summary
    total_trained = sum(len(v) for v in results["trained"].values())
    total_failed = sum(len(v) for v in results["failed"].values())
    
    logger.info("\n" + "=" * 80)
    logger.info("TRAINING RUN COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Trained: {total_trained} configurations")
    logger.info(f"Failed: {total_failed} configurations")
    
    if total_failed > 0:
        logger.warning("Failed configurations:")
        for symbol, timeframes_dict in results["failed"].items():
            for tf, error in timeframes_dict.items():
                logger.warning(f"  {symbol}/{tf}: {error}")
    
    logger.info("=" * 80)
    
    return results


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Initialize database
    db = SupabaseDatabase()
    
    # Run full training
    results = train_all_timeframes_all_symbols(db)
    
    # Exit with error code if any failed
    if results["failed"]:
        sys.exit(1)
    
    sys.exit(0)
